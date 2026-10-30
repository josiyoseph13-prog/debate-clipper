"""Identify only positively owned children left behind by a crashed job."""
import os
from pathlib import Path
import signal
import subprocess

from .hashing import content_hash
from .io import atomic_write_json,read_json


def register_child(process,job_dir:Path,command)->Path|None:
    import psutil
    try:
        child=psutil.Process(process.pid)
        started,command_hash=child.create_time(),content_hash(child.cmdline())
    except psutil.NoSuchProcess:return None
    owner=psutil.Process()
    path=job_dir/f"child_{process.pid}.json"
    atomic_write_json(path,{"schema_version":5,"pid":process.pid,"started":started,"command_hash":command_hash,"owner_pid":os.getpid(),"owner_started":owner.create_time()})
    return path


def recover_children(job_dir:Path)->list[int]:
    import psutil
    recovered=[]
    for path in job_dir.glob("child_*.json"):
        record=read_json(path,{}) or {}
        try:
            owner=psutil.Process(record["owner_pid"])
            owner_alive=abs(owner.create_time()-record["owner_started"])<.01 and owner.is_running() and owner.status()!=psutil.STATUS_ZOMBIE
        except (KeyError,psutil.NoSuchProcess):owner_alive=False
        if owner_alive:continue
        try:
            child=psutil.Process(record["pid"])
            if abs(child.create_time()-record["started"])>.01 or content_hash(child.cmdline())!=record["command_hash"]:
                continue
            if os.name=="nt":
                subprocess.run(["taskkill","/PID",str(child.pid),"/T","/F"],shell=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            elif os.getpgid(child.pid)==child.pid:
                os.killpg(child.pid,signal.SIGTERM)
            else:
                for descendant in child.children(recursive=True):descendant.terminate()
                child.terminate()
            try:child.wait(timeout=3)
            except psutil.TimeoutExpired:
                if os.name!="nt" and os.getpgid(child.pid)==child.pid:os.killpg(child.pid,signal.SIGKILL)
                else:child.kill()
                child.wait(timeout=5)
            recovered.append(child.pid)
        except (KeyError,psutil.NoSuchProcess,ProcessLookupError):pass
        finally:path.unlink(missing_ok=True)
    return recovered
