"""T-15 cancel an actual CLI render and inspect all owned child processes."""
from pathlib import Path
import os
import subprocess
import sys
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.io import atomic_copy,atomic_write_json,read_json,atomic_write_bytes
from dc.core.jobs import JobStore
from dc.core.process import run_process,terminate_tree


def main():
    original=ROOT/"work"/"job_crash_acceptance"
    job_id="job_cancel_acceptance"
    work=ROOT/"work"/job_id
    work.mkdir(parents=True,exist_ok=True)
    for name in ("source.json","transcript.json","job_config.json"):
        atomic_copy(original/name,work/name)
    candidate=(read_json(original/"candidates.json"))["candidates"][0]
    candidate["id"]="c_cancel_acceptance"
    atomic_write_json(work/"candidates.json",{"schema_version":5,"candidates":[candidate]})
    (work/"cancel.request").unlink(missing_ok=True)
    args=[sys.executable,"-m","dc","render","--job",job_id,"--candidate",candidate["id"]]
    children=[]
    with (ROOT/"reports"/"verification_v5"/"cancel_render.txt").open("wb") as log:
        child=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=log,start_new_session=os.name!="nt",creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
        try:
            for _ in range(600):
                records=[read_json(path,{}) for path in work.glob("child_*.json")]
                if records and (work/"render.graph").is_file():
                    children=records
                    break
                if child.poll() is not None:break
                time.sleep(.05)
            if not children:raise RuntimeError("No live rendering child found")
            cancelled=run_process([sys.executable,"-m","dc","cancel","--job",job_id],cwd=ROOT,timeout=15)
            atomic_write_bytes(ROOT/"reports"/"verification_v5"/"cancel_request.txt",cancelled.encode())
            code=child.wait(timeout=15)
        finally:
            if child.poll() is None:terminate_tree(child)
    survivors=[]
    for record in children:
        try:
            process=psutil.Process(record["pid"])
            if abs(process.create_time()-record["started"])<.01 and process.status()!=psutil.STATUS_ZOMBIE:survivors.append(process.pid)
        except psutil.NoSuchProcess:pass
    state=JobStore(ROOT/"work"/"jobs.sqlite").get(job_id)["state"]
    result={"schema_version":5,"test_id":"T-15","command":args,"returncode":code,"state":state,"owned_child_survivors":survivors,"passed":code==130 and state=="cancelled" and not survivors}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"cancel.json",result)
    print(result)
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
