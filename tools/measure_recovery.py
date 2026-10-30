"""T-36 render-crash exercise with real FFmpeg and identity-checked resume."""
from pathlib import Path
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,atomic_write_bytes,read_json
from dc.core.process import run_process,terminate_tree
from dc.core.tools import require_tool
from dc.ingest import ingest
from dc.renderer import make_render_plan,render


def main():
    job_id="job_crash_acceptance"
    work=ROOT/"work"/job_id
    work.mkdir(parents=True,exist_ok=True)
    source_path=work/"source.mp4"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=640x360:r=25:d=8","-f","lavfi","-i","sine=frequency=500:sample_rate=48000:duration=8","-c:v","libx264","-c:a","aac","-shortest",source_path],timeout=60)
    config=load_config(overrides={"output":{"preset":"ultrafast"}})
    source=ingest(source_path,work,rights_class="own",rights_note="Generated synthetic acceptance fixture")
    candidate={"id":"c_crash_acceptance","start":0,"end":8,"duration":8,"text":"Recovery fixture.","hook":{"headline_options":["Recovery fixture"]},"integrity_flags":[],"edits":[],"claims":[]}
    transcript={"language":"en","segments":[{"start":.12,"end":7.65,"text":"Recovery fixture.","words":[{"text":"Recovery","start":.12,"end":3.4},{"text":"fixture.","start":4,"end":7.65}]}]}
    atomic_write_json(work/"transcript.json",transcript)
    atomic_write_json(work/"candidates.json",{"schema_version":5,"candidates":[candidate]})
    atomic_write_json(work/"job_config.json",{"schema_version":5,"preset":"political_lens","config":config.json(),"config_hash":config.hash()})
    expected=work/"expected"
    expected.mkdir(exist_ok=True)
    plan=make_render_plan(source,candidate,config,expected)
    plan["transcript"]=transcript
    render(plan,config,expected,expected/"clip.mp4")
    hashes={name:file_hash(expected/name) for name in ("chrome.png","captions.ass","framing.json")}
    args=[sys.executable,"-m","dc","render","--job",job_id,"--candidate",candidate["id"]]
    log_path=ROOT/"reports"/"verification_v5"/"crash_render.txt"
    with log_path.open("wb") as log:
        process=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=log,start_new_session=os.name!="nt",creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
        killed=False
        try:
            for _ in range(600):
                owned=list(work.glob("child_*.json"))
                if owned and (work/"render.graph").is_file() and (work/"captions.ass").is_file():
                    # Kill the controller only: exercise orphan recovery itself.
                    process.kill()
                    process.wait(timeout=5)
                    killed=True
                    break
                if process.poll() is not None:break
                time.sleep(.05)
            if not killed:raise RuntimeError("Failed to interrupt a live render")
        finally:
            if process.poll() is None:terminate_tree(process)
    resume=[sys.executable,"-m","dc","resume","--job",job_id,"--candidate",candidate["id"]]
    output=run_process(resume,cwd=ROOT,timeout=300,output_limit=500000)
    atomic_write_bytes(ROOT/"reports"/"verification_v5"/"crash_resume.txt",output.encode())
    actual={name:file_hash(work/name) for name in hashes}
    report=read_json(work/"export_report.json",{})
    partials=list((ROOT/"exports"/candidate["id"]).glob("*.part"))
    result={"schema_version":5,"test_id":"T-36","commands":[args,resume],"controller_killed":killed,"resume_qa":report.get("status"),"deterministic_artifacts":actual==hashes,"expected_hashes":hashes,"resumed_hashes":actual,"export_partials":list(map(str,partials)),"asr_crash_verified":False,"passed_render_recovery":killed and actual==hashes and not partials and report.get("status")!="failed"}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"recovery.json",result)
    print(result)
    return 0 if result["passed_render_recovery"] else 1


if __name__=="__main__":raise SystemExit(main())
