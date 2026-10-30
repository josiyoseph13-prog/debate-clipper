"""T-36 kill the real CLI controller mid-Whisper inference, then dc resume."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,read_json,atomic_copy
from dc.core.security import validate_id
from dc.core.jobs import JobStore
from dc.core.process import run_process,terminate_tree
from dc.core.tools import require_tool


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-id",default=str(time.time_ns()),help="Fresh ID for real inference, never reuse a completed transcript")
    options=parser.parse_args()
    validate_id("job_native_asr_crash_"+options.run_id)
    if os.name!="nt":raise SystemExit("Use the actual native Windows ASR verification profile")
    tools=ROOT/"work"/"native_windows"/"tools"/"ffmpeg-9.0.2-essentials_build"/"bin"
    os.environ.update({"FFMPEG_PATH":str(tools/"ffmpeg.exe"),"FFPROBE_PATH":str(tools/"ffprobe.exe"),"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8","HF_HUB_OFFLINE":"1"})
    destination=ROOT/"reports"/"native_windows"
    destination.mkdir(parents=True,exist_ok=True)
    for name in ("asr_recovery.json","asr_crash_controller.txt","asr_resume.txt","asr_baseline.txt"):
        path=destination/name
        if path.is_file():atomic_copy(path,path.with_name(path.stem+"."+file_hash(path)[:16]+path.suffix))
    fixture=ROOT/"work"/"native_windows"/"asr_source.mkv"
    if not fixture.exists():
        run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss","60","-i",ROOT/"input"/"xmp4EdJvPfo.mp4","-t","120","-c","copy","-avoid_negative_ts","make_zero",fixture],timeout=120)
    crash_id="job_native_asr_crash_"+options.run_id
    baseline_id="job_native_asr_baseline_"+options.run_id
    def args(job):return [sys.executable,"-m","dc","run","--source",str(fixture),"--job",job,"--preset","verification_asr","--mode","review","--top","1","--no-network"]
    work=ROOT/"work"/crash_id
    work.mkdir(parents=True,exist_ok=True)
    if (work/"transcript.json").exists():raise RuntimeError("Crash fixture already complete; choose a fresh fixture rather than claiming an ASR cache hit is inference")
    started=args(crash_id)
    children=[]
    with (destination/"asr_crash_controller.txt").open("wb") as log:
        controller=subprocess.Popen(started,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        try:
            for _ in range(2400):
                progress=read_json(work/"asr_progress.json",{}) or {}
                children=[read_json(path) for path in work.glob("child_*.json")]
                if progress.get("stage")=="inference" and progress.get("segments_processed",0)>0 and children:break
                if controller.poll() is not None:raise RuntimeError("Controller completed before live inference was observed")
                time.sleep(.05)
            else:raise RuntimeError("No live real ASR inference within120s")
            before={"progress":progress,"registered_children":children,"transcript_visible":(work/"transcript.json").exists()}
            controller.kill()
            controller.wait(timeout=10)
            resumed=[sys.executable,"-m","dc","resume","--job",crash_id]
            output=run_process(resumed,cwd=ROOT,timeout=900,output_limit=2_000_000)
            (destination/"asr_resume.txt").write_text(output,encoding="utf-8")
        finally:
            if controller.poll() is None:terminate_tree(controller)
    baseline=args(baseline_id)
    output=run_process(baseline,cwd=ROOT,timeout=900,output_limit=2_000_000)
    (destination/"asr_baseline.txt").write_text(output,encoding="utf-8")
    survivors=[]
    for record in children:
        try:
            child=psutil.Process(record["pid"])
            if abs(child.create_time()-record["started"])<.01:survivors.append(child.pid)
        except psutil.NoSuchProcess:pass
    names=("transcript.json","debate_graph.json","candidates.json")
    recovered_hashes={name:file_hash(work/name) for name in names}
    baseline_hashes={name:file_hash(ROOT/"work"/baseline_id/name) for name in names}
    transcript=read_json(work/"transcript.json")
    state=JobStore(ROOT/"work"/"jobs.sqlite").get(crash_id)["state"]
    result={"schema_version":5,"test_id":"T-36 ASR half","commands":[started,resumed,baseline],"native_windows":True,"fixture_sha256":file_hash(fixture),"parent_source_sha256":file_hash(ROOT/"input"/"xmp4EdJvPfo.mp4"),"fixture_note":"Real-source120s stream-copy excerpt requested at60s; exact file/hash used for both runs, not human accuracy labels","rights_class":"unknown","model_sha256":transcript["model_sha256"],"before_kill":before,"recovered_hashes":recovered_hashes,"uninterrupted_hashes":baseline_hashes,"deterministic":recovered_hashes==baseline_hashes,"state":state,"surviving_owned_children":survivors,"speech_coverage":transcript["speech_coverage"],"review_flags":transcript["review_flags"],"word_accuracy_verified":False,"export_partials":[str(path) for path in (ROOT/"exports").rglob("*.part")],"passed":not before["transcript_visible"] and recovered_hashes==baseline_hashes and state=="awaiting_review" and not survivors}
    result["passed"]=result["passed"] and not result["export_partials"]
    result["code_hashes"]={name:file_hash(ROOT/name) for name in ("dc/asr.py","dc/audio.py","dc/cli.py","dc/pipeline.py","dc/core/checkpoints.py","dc/selection.py","tools/measure_asr_recovery.py")}
    atomic_write_json(destination/"asr_recovery.json",result)
    print(result,flush=True)
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
