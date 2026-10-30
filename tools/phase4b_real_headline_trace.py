"""Run the mandatory Phase 4B real Studio headline trace against a real clip."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc.core.process import run_process, terminate_tree

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def start_server(port):
    child = subprocess.Popen(
        [sys.executable, "-m", "dc", "studio", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
    )
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).close()
            return child
        except OSError:
            time.sleep(.1)
    terminate_tree(child)
    raise RuntimeError("Studio did not start")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "edit"
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    first = start_server(port)
    try:
        before = run_process(["node", "tools/phase4b_real_headline_trace.cjs", base, mode], cwd=ROOT, timeout=180)
    finally:
        terminate_tree(first)
    if mode == "baseline":
        print(json.dumps({"before_fix": json.loads(before)}))
        return
    second = start_server(port)
    try:
        after_restart = run_process(["node", "tools/phase4b_real_headline_trace.cjs", base, "restart"], cwd=ROOT, timeout=90)
    finally:
        terminate_tree(second)
    result = {"before_fix": "not run: current code already contained the prior attempted fix", "real_test": json.loads(before), "after_server_restart": json.loads(after_restart)}
    output = ROOT / "reports" / "phase4b_real_headline_trace.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
