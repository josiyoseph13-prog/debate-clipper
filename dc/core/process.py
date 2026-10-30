from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterable


class ProcessError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, output: str):
        self.args_list = args
        self.returncode = returncode
        self.output = output
        super().__init__(f"Command failed ({returncode}): {' '.join(args)}\n{output[-6000:]}")


class ProcessCancelled(RuntimeError):
    pass


_job_context: ContextVar = ContextVar("process_job_context", default=None)


def check_cancelled() -> None:
    """Cooperative cancellation for CPU loops as well as child processes."""
    context = _job_context.get()
    if context and (context[0] / "cancel.request").exists():
        raise ProcessCancelled(f"Job {context[2]} cancelled")


@contextmanager
def job_processes(job_dir: Path, store, job_id: str):
    token = _job_context.set((job_dir, store, job_id))
    try:
        check_cancelled()
        yield
    finally:
        _job_context.reset(token)


def terminate_tree(process) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=5)


def run_process(args: Iterable[str | Path], cwd: Path | None = None, timeout: float | None = None, output_limit: int = 200_000, env: dict[str, str] | None = None) -> str:
    check_cancelled()
    command = [os.fspath(arg) for arg in args]
    if not command or any("\x00" in arg for arg in command):
        raise ValueError("Invalid subprocess arguments")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    context = _job_context.get()
    if os.name == "nt" and context:
        creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    # A disk-backed spool avoids retaining unbounded child output in RAM and
    # cannot deadlock on a full stdout/stderr pipe.
    with tempfile.TemporaryFile(dir=cwd) as log:
        process = subprocess.Popen(command, cwd=cwd, shell=False, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=os.name != "nt", creationflags=creationflags)
        record=None
        if context:
            try:
                from .recovery import register_child
                record=register_child(process,context[0],command)
            except Exception:
                terminate_tree(process)
                raise
        started = time.monotonic()
        heartbeat = started
        try:
            while True:
                if context:
                    job_dir, store, job_id = context
                    if (job_dir / "cancel.request").exists():
                        raise ProcessCancelled(f"Job {job_id} cancelled")
                    if time.monotonic() - heartbeat >= 5:
                        store.heartbeat(job_id)
                        heartbeat = time.monotonic()
                if timeout is not None and time.monotonic() - started >= timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    process.wait(timeout=.25)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException as exc:
            terminate_tree(process)
            if isinstance(exc, subprocess.TimeoutExpired):
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - output_limit))
                output = log.read().decode("utf-8", errors="replace")
                raise ProcessError(command, -signal.SIGTERM, output + f"\nprocess timed out after {timeout}s") from exc
            raise
        finally:
            if record:record.unlink(missing_ok=True)
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - output_limit))
        output = log.read().decode("utf-8", errors="replace")
    if process.returncode:
        raise ProcessError(command, process.returncode, output)
    return output


def transform_video_stream(decode_args, encode_args, frame_bytes: int, transform, cwd: Path, timeout: float) -> int:
    """Bounded-memory binary decode → warp → encode with both trees owned here.

    Stderr is drained to disk; each iteration holds one decoded frame and one
    transformed frame. A watchdog terminates blocked pipe reads/writes on
    timeout or cancellation, including KeyboardInterrupt cleanup.
    """
    context = _job_context.get()
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    if os.name == "nt" and context:
        flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    stop = threading.Event()
    reason = []
    children = []
    records = []
    count = 0
    with tempfile.TemporaryFile(dir=cwd) as decoder_log, tempfile.TemporaryFile(dir=cwd) as encoder_log:
        def watch():
            started = time.monotonic()
            heartbeat = started
            while not stop.wait(.25):
                if context and (context[0] / "cancel.request").exists():
                    reason.append(ProcessCancelled(f"Job {context[2]} cancelled"))
                elif time.monotonic() - started > timeout:
                    reason.append(TimeoutError("Video stream timed out"))
                if reason:
                    for child in children:
                        terminate_tree(child)
                    return
                if context and time.monotonic() - heartbeat > 5:
                    context[1].heartbeat(context[2])
                    heartbeat = time.monotonic()
        try:
            decoder = subprocess.Popen([os.fspath(arg) for arg in decode_args], cwd=cwd, shell=False, stdout=subprocess.PIPE, stderr=decoder_log, start_new_session=os.name != "nt", creationflags=flags)
            children.append(decoder)
            if context:
                from .recovery import register_child
                records.append(register_child(decoder,context[0],decode_args))
            encoder = subprocess.Popen([os.fspath(arg) for arg in encode_args], cwd=cwd, shell=False, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=encoder_log, start_new_session=os.name != "nt", creationflags=flags)
            children.append(encoder)
            if context:records.append(register_child(encoder,context[0],encode_args))
            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            while True:
                raw = decoder.stdout.read(frame_bytes)
                if not raw:
                    break
                if len(raw) != frame_bytes:
                    raise RuntimeError("Truncated rawvideo frame")
                encoder.stdin.write(transform(raw, count))
                count += 1
            encoder.stdin.close()
            decoder.stdout.close()
            decoder.wait(timeout=10)
            encoder.wait(timeout=max(10, timeout))
            if reason:
                raise reason[0]
            for child, log, command in ((decoder, decoder_log, decode_args), (encoder, encoder_log, encode_args)):
                if child.returncode:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 6000))
                    raise ProcessError([os.fspath(arg) for arg in command], child.returncode, log.read().decode("utf-8", "replace"))
        except BaseException:
            for child in children:
                terminate_tree(child)
            if reason:
                raise reason[0]
            raise
        finally:
            stop.set()
            if 'watcher' in locals():
                watcher.join(timeout=5)
            for child in children:
                for pipe in (child.stdout, child.stdin):
                    if pipe:
                        pipe.close()
            for record in records:
                if record:record.unlink(missing_ok=True)
    return count
