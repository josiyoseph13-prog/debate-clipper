"""Exercise the real PowerShell Studio launcher and native localhost HTTP."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,atomic_write_bytes
from dc.core.logging import redact
from dc.core.process import terminate_tree


def main():
    if os.name!="nt":raise SystemExit("Use native Windows Python for this acceptance check")
    import psutil
    command=["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"run.ps1")]
    rows=[]
    token=None
    with tempfile.TemporaryFile() as log:
        child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        owned=[]
        try:
            deadline=time.monotonic()+45
            page=None
            while time.monotonic()<deadline:
                if child.poll() is not None:raise RuntimeError("Studio launcher exited before HTTP became ready")
                try:
                    with urlopen("http://127.0.0.1:8765/",timeout=1) as response:
                        page=response.read().decode("utf-8")
                        csp=response.headers.get("Content-Security-Policy","")
                    break
                except (URLError,TimeoutError):time.sleep(.1)
            if page is None:raise TimeoutError("Native Studio did not become ready")
            token_match=re.search(r"data-token='([^']+)'",page)
            token=token_match[1] if token_match else None
            rows.append({"name":"actual_studio_html","passed":bool(token) and "<title>Debate Clipper</title>" in page and "Debate Clipper" in page})
            rows.append({"name":"content_security_policy","value":csp,"passed":"default-src 'self'" in csp})
            owner=psutil.Process(child.pid)
            owned=[{"pid":process.pid,"started":process.create_time()} for process in [owner,*owner.children(recursive=True)]]
            pids={row["pid"] for row in owned}
            listeners=[{"pid":row.pid,"ip":row.laddr.ip,"port":row.laddr.port} for row in psutil.net_connections(kind="tcp") if row.status==psutil.CONN_LISTEN and row.pid in pids]
            rows.append({"name":"owned_localhost_listener","value":listeners,"passed":bool(listeners) and all(row["ip"]=="127.0.0.1" and row["port"]==8765 for row in listeners)})
            with urlopen("http://127.0.0.1:8765/api/jobs",timeout=10) as response:
                payload=json.loads(response.read())
                rows.append({"name":"actual_queue_http","status":response.status,"passed":response.status==200 and isinstance(payload,(dict,list))})
            for name,headers in (("tokenless_mutation",{"Origin":"http://127.0.0.1:8765"}),("cross_origin_mutation",{"Origin":"http://other.example","X-DC-Token":token or ""})):
                request=Request("http://127.0.0.1:8765/api/jobs/job_does_not_exist/cancel",data=b"{}",headers={"Content-Type":"application/json",**headers},method="POST")
                try:
                    with urlopen(request,timeout=10) as response:status=response.status
                except HTTPError as exc:status=exc.code
                rows.append({"name":name,"status":status,"passed":status==403})
        finally:
            terminate_tree(child)
            log.seek(0)
            output=log.read().decode("utf-8",errors="replace")
            if token:output=output.replace(token,"[REDACTED]")
            atomic_write_bytes(ROOT/"reports"/"native_windows"/"studio_launcher.txt",redact(output).encode("utf-8"))
    survivors=[]
    for row in owned:
        try:
            process=psutil.Process(row["pid"])
            if abs(process.create_time()-row["started"])<.01:survivors.append(process.pid)
        except psutil.NoSuchProcess:pass
    rows.append({"name":"launcher_tree_stopped","value":survivors,"passed":not survivors})
    report={"schema_version":5,"test_ids":["T-23 native HTTP","Part4.4 native launcher","Part12.14 automated scope"],"native_windows":True,"command":command,"checks":rows,"passed":all(row["passed"] for row in rows),"run_script_sha256":file_hash(ROOT/"run.ps1"),"raw_output":"reports/native_windows/studio_launcher.txt","human_acceptance":"Open: actual clicking, phone use, manual-step timing and watching final exports"}
    atomic_write_json(ROOT/"reports"/"native_windows"/"studio.json",report)
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
