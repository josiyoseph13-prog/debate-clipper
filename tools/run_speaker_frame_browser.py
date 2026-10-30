"""Launch an owned native Studio instance and exercise the real opt-in editor."""
from pathlib import Path
import subprocess
import sys
import time
import shutil
import httpx
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/"reports/speaker_frame/ui"
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/"server.log").open("w",encoding="utf-8") as log:
        server=subprocess.Popen([sys.executable,"-m","dc","studio","--port","8879"],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Test Studio stopped before it was ready")
                try:
                    if httpx.get("http://127.0.0.1:8879/api/health",timeout=1).status_code==200:
                        break
                except httpx.HTTPError:
                    time.sleep(.2)
            return subprocess.run([shutil.which("node"),"tools/speaker_frame_browser.cjs","http://127.0.0.1:8879"],cwd=ROOT,timeout=240).returncode
        finally:
            server.terminate()
            try:server.wait(timeout=15)
            except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=="__main__":
    raise SystemExit(main())
