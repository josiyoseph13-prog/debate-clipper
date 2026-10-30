"""Run actual Windows tools/core/render/QA/cancel; do not infer human acceptance."""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import file_hash,content_hash
from dc.core.io import atomic_write_bytes,atomic_write_json,read_json,atomic_copy
from dc.core.jobs import JobStore
from dc.core.process import run_process,ProcessError,terminate_tree
from tools.verify_v5 import verification_inputs


def main():
    if os.name!="nt":raise SystemExit("Run with native Windows Python; Linux execution is not Windows evidence")
    tools=ROOT/"work"/"native_windows"/"tools"/"ffmpeg-9.0.2-essentials_build"/"bin"
    os.environ["FFMPEG_PATH"]=str(tools/"ffmpeg.exe")
    os.environ["FFPROBE_PATH"]=str(tools/"ffprobe.exe")
    os.environ["PYTHONUTF8"]="1"
    os.environ["PYTHONIOENCODING"]="utf-8"
    destination=ROOT/"reports"/"native_windows"
    destination.mkdir(parents=True,exist_ok=True)
    for path in list(destination.iterdir()):
        if path.is_file() and path.name in {"summary.json","pytest.txt","doctor.txt","cancel_render.txt"}:
            atomic_copy(path,path.with_name(path.stem+"."+file_hash(path)[:16]+path.suffix))
    report={"schema_version":5,"command":[sys.executable,*sys.argv],"platform":platform.platform(),"python":sys.version,"native_windows":True,"root":str(ROOT),"path_contains_spaces":" " in str(ROOT),"requirements_lock_sha256":file_hash(ROOT/"requirements.lock"),"ffmpeg_sha256":file_hash(tools/"ffmpeg.exe"),"ffprobe_sha256":file_hash(tools/"ffprobe.exe"),"config_hash":load_config().hash(),"commands":[],"human_acceptance":"open: user must use Studio, watch three exports, and check phone/overnight behavior"}
    report["code_hashes_at_start"]={str(path.relative_to(ROOT)):file_hash(path) for path in (ROOT/"dc").rglob("*") if path.is_file() and path.suffix in {".py",".js",".css"}}
    report["verification_inputs_at_start"]=verification_inputs()
    def record(name,args,timeout=600):
        began=time.monotonic()
        try:
            output=run_process(args,cwd=ROOT,timeout=timeout,output_limit=2_000_000)
            code=0
        except ProcessError as exc:code,output=exc.returncode,exc.output
        path=destination/f"{name}.txt"
        atomic_write_bytes(path,output.encode("utf-8"))
        row={"name":name,"argv":[str(arg) for arg in args],"cwd":str(ROOT),"exit_code":code,"elapsed_s":round(time.monotonic()-began,3),"raw_output":str(path.relative_to(ROOT)),"raw_sha256":file_hash(path)}
        report["commands"].append(row)
        atomic_write_json(destination/"summary.json",report)
        print(json.dumps(row),flush=True)
        return code,output
    record("ffmpeg_version",[tools/"ffmpeg.exe","-version"])
    record("dependencies",[sys.executable,"-m","pip","check"])
    record("compile",[sys.executable,"-m","compileall","-q","dc","tools","tests"])
    record("pytest",[sys.executable,"-m","pytest","-q"])
    record("doctor",[sys.executable,"-m","dc","doctor"])

    from dc.ingest import ingest
    from dc.layout import crop_rect
    from dc.renderer import make_render_plan,render
    from dc.qa import validate_output
    from dc.chrome import emoji_image
    from dc.ops import batch_comfort,wait_for_power
    import psutil
    cfg=load_config()
    job_id="job_native_windows_acceptance"
    work=ROOT/"work"/job_id
    work.mkdir(parents=True,exist_ok=True)
    source=ingest(ROOT/"input"/"xmp4EdJvPfo.mp4",work,rights_class="unknown",rights_note="User-supplied source; no rights attestation")
    transcript=read_json(ROOT/"work"/"job_verify_v5"/"transcript.json")
    atomic_write_json(work/"transcript.json",transcript)
    atomic_write_json(work/"job_config.json",{"schema_version":5,"preset":"political_lens","config":cfg.json()})
    candidate=next(row for row in read_json(ROOT/"work"/"job_verify_v5"/"candidates.json")["candidates"] if row["id"]=="c_3c6c100b3289")
    candidate={**candidate,"id":"c_native_windows"}
    rect=crop_rect(source["width"],source["height"],cfg)
    plan=make_render_plan(source,candidate,cfg,work,mode="manual",manual_regions=[rect])
    plan["framing"]["path"]=[{"t":0,**rect,"x":rect["x"]-10},{"t":plan["trim"]["duration"],**rect,"x":rect["x"]+10}]
    plan.update({"transcript":transcript,"captions_ass":str(work/"captions.ass"),"caption_plan":str(work/"captions_plan.json"),"chrome_png":str(work/"chrome.png")})
    plan["plan_hash"]=content_hash({key:value for key,value in plan.items() if key!="plan_hash"})
    atomic_write_json(work/"render_plan.json",plan)
    rendered=render(plan,cfg,work,work/"clip.mp4")
    qa=validate_output(work/"clip.mp4",plan,cfg,work/"export_report.json")
    report["real_render"]={"test_ids":["T-12","T-18"],"source_sha256":source["fingerprint"]["sha256"],"rights_class":source["rights_class"],"manual_moving_path":True,"automatic_speaker_accuracy_claimed":False,"render":rendered,"qa":qa}
    glyph=emoji_image("🎓",60,cfg)
    glyph.save(work/"emoji.png")
    report["emoji"]={"test_id":"T-22","non_tofu":True,"pixel_artifact":str((work/"emoji.png").relative_to(ROOT))}
    kernel=ctypes.windll.kernel32
    with batch_comfort(cfg):during=int(kernel.SetThreadExecutionState(0x80000001))
    after=int(kernel.SetThreadExecutionState(0x80000000))
    battery=psutil.sensors_battery()
    wait_for_power(cfg)
    report["comfort"]={"awake_state_during":during,"awake_state_after":after,"awake_released":bool(during&1) and not bool(after&1),"battery":battery._asdict() if battery else None,"battery_pause_human_gate":"Actual low-battery overnight scenario not induced"}
    # Cancellation rebuilds the plan/chrome/ASS before launching FFmpeg. Keep
    # that attempt in its own job so it cannot overwrite passing render evidence.
    cancel_job="job_native_windows_cancel_acceptance"
    cancel_work=ROOT/"work"/cancel_job
    cancel_work.mkdir(parents=True,exist_ok=True)
    for name in ("source.json","transcript.json","job_config.json"):
        atomic_copy(work/name,cancel_work/name)
    atomic_write_json(cancel_work/"candidates.json",{"schema_version":5,"candidates":[candidate]})
    (cancel_work/"cancel.request").unlink(missing_ok=True)
    args=[sys.executable,"-m","dc","render","--job",cancel_job,"--candidate",candidate["id"]]
    children=[]
    with (destination/"cancel_render.txt").open("wb") as log:
        child=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        try:
            for _ in range(600):
                children=[read_json(path) for path in cancel_work.glob("child_*.json")]
                if children:break
                if child.poll() is not None:break
                time.sleep(.05)
            if not children:raise RuntimeError("Native render had no registered live child")
            priorities=[]
            for row in children:
                try:priorities.append(int(psutil.Process(row["pid"]).nice()))
                except psutil.NoSuchProcess:pass
            record("cancel_request",[sys.executable,"-m","dc","cancel","--job",cancel_job],30)
            code=child.wait(timeout=30)
        finally:
            if child.poll() is None:terminate_tree(child)
    survivors=[]
    for row in children:
        try:
            process=psutil.Process(row["pid"])
            if abs(process.create_time()-row["started"])<.01:survivors.append(process.pid)
        except psutil.NoSuchProcess:pass
    state=JobStore(ROOT/"work"/"jobs.sqlite").get(cancel_job)["state"]
    report["cancel"]={"test_id":"T-15","job_id":cancel_job,"returncode":code,"state":state,"surviving_owned_children":survivors,"passed":code==130 and state=="cancelled" and not survivors,"child_priorities":priorities,"below_normal_measured":bool(priorities) and all(value==int(psutil.BELOW_NORMAL_PRIORITY_CLASS) for value in priorities)}
    report["code_hashes"]={str(path.relative_to(ROOT)):file_hash(path) for path in (ROOT/"dc").rglob("*") if path.is_file() and path.suffix in {".py",".js",".css"}}
    report["code_changed_during_checks"]=report["code_hashes_at_start"]!=report["code_hashes"]
    report["verification_inputs"]=verification_inputs()
    report["verification_inputs_changed_during_checks"]=report["verification_inputs_at_start"]!=report["verification_inputs"]
    report["status"]="passed_automated_scope" if not report["code_changed_during_checks"] and not report["verification_inputs_changed_during_checks"] and all(row["exit_code"]==0 for row in report["commands"]) and qa["status"]=="passed" and report["cancel"]["passed"] and report["comfort"]["awake_released"] else "failed"
    atomic_write_json(destination/"summary.json",report)
    print({"status":report["status"],"qa":qa["status"],"cancel":report["cancel"]},flush=True)
    return 0 if report["status"]=="passed_automated_scope" else 1


if __name__=="__main__":raise SystemExit(main())
