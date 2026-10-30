"""Real browser fixture; all decisions live in a temporary root."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.io import atomic_write_json,atomic_write_bytes
from dc.core.process import run_process,terminate_tree


def main():
    with tempfile.TemporaryDirectory(prefix="studio_browser_") as folder:
        fixture=Path(folder)
        job=fixture/"work"/"job_browser"
        job.mkdir(parents=True)
        text="<img src=x onerror=window.__xss=1>"
        atomic_write_json(job/"candidates.json",{"schema_version":5,"candidates":[{"id":"c_browser","start":0,"end":10,"duration":10,"text":text,"score":75,"archetype":"A7","hook":{"headline_options":["Browser fixture"]},"components":{},"claims":[]}]})
        atomic_write_json(job/"source.json",{"path":str(fixture/"fixture.mp4"),"duration":10,"width":1920,"height":1080,"rights_class":"own","meta":{"title":text}})
        atomic_write_json(job/"transcript.json",{"segments":[{"start":0,"end":10,"text":text,"words":[{"text":text,"start":0,"end":10}]}]})
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0))
            port=listener.getsockname()[1]
        code="from pathlib import Path;import uvicorn;import dc.studio.server as server;server.ROOT=Path(__import__('sys').argv[1]);app,token=server.create_app();uvicorn.run(app,host='127.0.0.1',port=int(__import__('sys').argv[2]),log_level='error')"
        with tempfile.TemporaryFile() as log:
            child=subprocess.Popen([sys.executable,"-c",code,str(fixture),str(port)],cwd=ROOT,stdout=log,stderr=log,start_new_session=os.name!="nt",creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
            try:
                url=f"http://127.0.0.1:{port}"
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(url+"/api/health",timeout=1):break
                    except OSError:time.sleep(.1)
                output=run_process(["node","tools/studio_browser.cjs",url],cwd=ROOT,timeout=90)
                atomic_write_bytes(ROOT/"reports"/"verification_v5"/"browser.txt",output.encode())
                print(output)
            finally:terminate_tree(child)


if __name__=="__main__":main()
