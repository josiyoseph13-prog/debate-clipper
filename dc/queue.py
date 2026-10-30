"""Sequential SQLite-backed batch worker with resumable request artifacts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .core.config import ROOT,load_preset
from .core.io import atomic_write_json,read_json
from .core.jobs import JobStore
from .core.process import ProcessCancelled
from .ops import batch_comfort,wait_for_power


def enqueue(source:Path,mode="review",preset="political_lens",rights_class="unknown",rights_note="",transcript=None)->str:
    from .cli import _job_id
    from .core.hashing import content_hash
    base_id=_job_id(source)
    job_id=base_id
    existing=read_json(ROOT/"work"/base_id/"job_request.json",{}) or {}
    existing_request=existing.get("request") if isinstance(existing,dict) else None
    requested_signature={"mode":mode,"preset":preset,"rights_class":rights_class,"rights_note":rights_note,"transcript":str(transcript) if transcript else None}
    if existing_request and any(existing_request.get(key)!=value for key,value in requested_signature.items()):
        job_id=f"{base_id}_{content_hash(requested_signature)[:8]}"
    folder=ROOT/"work"/job_id
    folder.mkdir(parents=True,exist_ok=True)
    request={"source":str(source.resolve()),"transcript":str(transcript) if transcript else None,"job":job_id,"preset":preset,"top":8,"mode":mode,"auto_threshold":90,"rights_class":rights_class,"rights_note":rights_note,"no_network":True,"force":False}
    atomic_write_json(folder/"job_request.json",{"schema_version":5,"request":request})
    JobStore(ROOT/"work"/"jobs.sqlite").upsert(job_id,"queued",json.dumps(request),"queued")
    return job_id


def worker()->dict:
    from .core.locking import exclusive_file
    with exclusive_file(ROOT/"work"/"worker.lock"):
        return _worker()


def _worker()->dict:
    from .cli import command_run
    store=JobStore(ROOT/"work"/"jobs.sqlite")
    completed,failed,cancelled=[],[],[]
    with store.connect() as db:
        rows=[dict(row) for row in db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY heartbeat")]
    for row in rows:
        request=(read_json(ROOT/"work"/row["job_id"]/"job_request.json",{}) or {}).get("request")
        if not request:
            store.upsert(row["job_id"],"failed",json.dumps({"error":"missing request artifact"}),"queue")
            failed.append(row["job_id"])
            continue
        config=load_preset(request["preset"])
        with batch_comfort(config):
            for attempt in range(int(config.get("ops","max_retries",default=1))+1):
                try:
                    wait_for_power(config,ROOT/"work"/row["job_id"]/"cancel.request")
                    code=command_run(argparse.Namespace(**request))
                    if code==130:
                        cancelled.append(row["job_id"])
                    elif code:
                        raise RuntimeError(f"Job returned {code}")
                    else:
                        completed.append(row["job_id"])
                    break
                except (ProcessCancelled,KeyboardInterrupt):
                    store.upsert(row["job_id"],"cancelled","{}","queue")
                    cancelled.append(row["job_id"])
                    break
                except (Exception,SystemExit) as exc:
                    store.upsert(row["job_id"],"failed",json.dumps({"error":str(exc),"attempt":attempt}),"queue")
                    if attempt==int(config.get("ops","max_retries",default=1)):
                        failed.append(row["job_id"])
    return {"schema_version":5,"completed":completed,"failed":failed,"cancelled":cancelled}
