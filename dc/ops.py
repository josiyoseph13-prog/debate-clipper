from __future__ import annotations

import json
import shutil
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from contextlib import contextmanager
import os

from .core.config import ROOT, load_config
from .core.hashing import content_hash


def disk_guard(source: Path, root: Path, multiplier: float = 3.0) -> dict[str, Any]:
    usage = shutil.disk_usage(root)
    required = int(source.stat().st_size * float(multiplier))
    result = {"free_bytes": usage.free, "required_bytes": required, "multiplier": multiplier, "passed": usage.free >= required}
    if not result["passed"]:
        raise RuntimeError(f"Insufficient free disk: {usage.free} < {required}")
    return result


def cleanup_work(root: Path, retention_days: int = 14) -> list[str]:
    """Remove only expired job folders under work; exports are never touched."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(retention_days))
    removed = []
    work = root / "work"
    if not work.exists():
        return removed
    for folder in work.iterdir():
        if not folder.is_dir() or folder.is_symlink() or not folder.name.startswith("job_") or folder.resolve().parent != work.resolve():
            continue
        from .core.jobs import JobStore
        store_path=work/"jobs.sqlite"
        record=JobStore(store_path).get(folder.name) if store_path.exists() else None
        if record and record["state"] in {"queued","running","rendering","awaiting_review"}:
            continue
        modified = datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            import shutil

            shutil.rmtree(folder)
            removed.append(folder.name)
    return removed


def bench(output: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_config()
    measurements = {"config_load_s": time.perf_counter() - started}
    synthetic = {"segments": [{"start": index * 2.0, "end": index * 2.0 + 1.5, "text": "Why does this matter? Because the answer is part of the record.", "words": [{"start": index * 2.0, "end": index * 2.0 + 1.5, "text": "Why does this matter? Because the answer is part of the record."}]} for index in range(20)]}
    source = {"source_id": "bench", "duration": 40.0, "width": 1920, "height": 1080, "rights_class": "permission", "meta": {}}
    from .framing import framing_plan
    from .layout import validate_layout
    from .selection import select_candidates

    started_stage = time.perf_counter(); validate_layout(config); measurements["layout_validation_s"] = time.perf_counter() - started_stage
    started_stage = time.perf_counter(); graph, candidates = select_candidates(synthetic, source, config, top=8); measurements["selection_s"] = time.perf_counter() - started_stage
    started_stage = time.perf_counter(); framing_plan(source["width"], source["height"], 30, config); measurements["framing_plan_s"] = time.perf_counter() - started_stage
    result = {"schema_version": 5, "command": "dc bench", "settings": {"config_hash": config.hash(), "python": __import__("sys").version.split()[0], "synthetic_segments": len(synthetic["segments"])}, "measurements": measurements, "candidate_count": len(candidates), "status": "measured"}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def bench_render(job_id:str,candidate_id:str,output:Path)->dict:
    from .cli import _load_job
    from .renderer import make_render_plan,render
    from .core.config import AppConfig
    from .core.io import atomic_write_json
    import threading
    import platform
    job,source,transcript,artifact=_load_job(job_id)
    candidate=next(row for row in artifact["candidates"] if row["id"]==candidate_id)
    config=load_config()
    results={"schema_version":5,"command":f"dc bench --job {job_id} --candidate {candidate_id}","media_id":source["source_id"],"machine":{"platform":platform.platform(),"python":__import__("sys").version,"cpu_count":os.cpu_count()},"settings":{"config_hash":config.hash()},"profiles":{}}
    for method in ("ass_layers","fast_glow"):
        folder=job/"bench"/method
        folder.mkdir(parents=True,exist_ok=True)
        data=config.json()
        data["captions"]["glow"]["method"]=method
        cfg=AppConfig(data,config.path)
        plan=make_render_plan(source,candidate,cfg,folder)
        plan["transcript"]=transcript
        usage={"peak_rss_bytes":None,"peak_cpu_percent":None}
        stop=threading.Event()
        def monitor():
            try:
                import psutil
                process=psutil.Process()
                while not stop.wait(.1):
                    children=[process]+process.children(recursive=True)
                    rss=sum(child.memory_info().rss for child in children if child.is_running())
                    cpu=sum(child.cpu_percent() for child in children if child.is_running())
                    usage["peak_rss_bytes"]=max(usage["peak_rss_bytes"] or 0,rss)
                    usage["peak_cpu_percent"]=max(usage["peak_cpu_percent"] or 0,cpu)
            except (ImportError,ProcessLookupError): pass
        thread=threading.Thread(target=monitor,daemon=True)
        thread.start()
        began=time.perf_counter()
        try:
            rendered=render(plan,cfg,folder,folder/"clip.mp4")
            elapsed=time.perf_counter()-began
            results["profiles"][method]={"wall_seconds":elapsed,"render_rtf":elapsed/plan["trim"]["duration"],**usage,"output":rendered["output"]}
        finally:
            stop.set()
            thread.join(timeout=5)
    results["fast_glow_default_enabled"]=False
    results["reason"]="Alternative remains opt-in pending equivalent lossless halo/colour measurement"
    atomic_write_json(output,results)
    return results


def diag(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in (ROOT / "reports").glob("*.json"):
            archive.write(path, f"reports/{path.name}")
        events = ROOT / "work" / "events.jsonl"
        if events.exists():
            from .core.logging import redact
            lines=[]
            for line in events.read_text(encoding="utf-8").splitlines():
                try:
                    lines.append(json.dumps(redact(json.loads(line)),ensure_ascii=False))
                except json.JSONDecodeError:
                    continue
            archive.writestr("work/events.jsonl","\n".join(lines))
        config = ROOT / "config" / "political_lens.json"
        archive.writestr("config_hash.txt", content_hash(config.read_bytes()))
    return output


@contextmanager
def batch_comfort(config):
    awake=False
    try:
        if os.name=="nt" and config.get("ops","prevent_sleep",default=True):
            import ctypes
            awake=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
        yield
    finally:
        if awake:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def wait_for_power(config, cancel_path:Path|None=None):
    try:
        import psutil
    except ImportError:
        return
    while True:
        battery=psutil.sensors_battery()
        if not battery or battery.power_plugged or battery.percent>=config.get("ops","battery_pause_percent",default=20):
            return
        if cancel_path and cancel_path.exists():
            from .core.process import ProcessCancelled
            raise ProcessCancelled("Cancelled while waiting for power")
        time.sleep(5)
