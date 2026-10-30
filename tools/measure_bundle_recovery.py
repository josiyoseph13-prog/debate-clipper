"""Kill real export workers at recorded barriers; recover complete real bundles.

Uses an existing QA-passed real export. Barriers only hold a worker at a known
transaction boundary; the video, cover, sidecars, metadata and hashes are real.
This is export/recovery evidence, not new render or human quality evidence.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.bundles import write_complete_bundle,recover_export_bundles,_complete
from dc.core.config import AppConfig,load_config
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,read_json
from dc.core.jobs import JobStore
from dc.core.process import job_processes,run_process,terminate_tree
from dc.core.recovery import recover_children,register_child
from dc.core.security import validate_id


def fixture(export):
    plan=read_json(export/"render_plan.json")
    candidate=read_json(export/"candidate.json")
    qa=read_json(export/"export_report.json")
    clip=export/"clip.mp4"
    if not plan or not candidate or not qa or qa.get("status")!="passed" or file_hash(clip)!=qa.get("output_sha256"):
        raise ValueError("Fixture must be an actual unchanged QA-passed export")
    source=plan["source"]
    # Old Linux evidence is a valid fixture on Windows, but interop must refer
    # to the real native source rather than a nonexistent Linux drive path.
    path=source["path"]
    if os.name=="nt" and path.startswith("/mnt/d/"):
        source["path"]="D:/"+path[len("/mnt/d/"):]
    transcript=read_json(ROOT/"work"/"job_verify_v5"/"transcript.json")
    for name in ("captions.ass","chrome.png","craft.png","extras.png"):
        if (export/name).is_file():plan[name.replace(".","_")]=str(export/name)
    settings=read_json(export/"renderer_config.json",{}) or {}
    config=AppConfig(settings["config"],load_config().path) if settings.get("config") else load_config()
    return clip,plan,transcript,source,candidate,qa,config


def worker(args):
    import dc.core.bundles as bundles
    import dc.exports as exports
    job=ROOT/"work"/args.job
    target=ROOT/"exports"/args.target
    clip,plan,transcript,source,candidate,qa,config=fixture(args.source_export)
    def barrier(phase):
        atomic_write_json(job/"kill_barrier.json",{"schema_version":5,"phase":phase,"pid":os.getpid()})
        while True:time.sleep(.05)
    original_sidecars=exports.write_sidecars
    def sidecars(*values,**options):
        result=original_sidecars(*values,**options)
        if args.phase=="building":barrier("building_after_real_sidecars_before_metadata")
        return result
    original_write=bundles.atomic_write_json
    def journal(path,value):
        original_write(path,value)
        if args.phase=="previous_moved" and value.get("phase")=="previous_moved":barrier("previous_moved_durable_journal")
    exports.write_sidecars=sidecars
    bundles.atomic_write_json=journal
    def build(stage):
        result=exports._build_export_bundle(stage,clip,plan,transcript,source,candidate,qa,config,final_dir=target)
        atomic_write_json(stage/"acceptance_generation.json",{"schema_version":5,"generation":args.generation,"fixture_only":True})
        return result
    with job_processes(job,JobStore(ROOT/"work"/"jobs.sqlite"),args.job):
        write_complete_bundle(job,target,build)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-export",type=Path,default=ROOT/"exports"/"c_3c6c100b3289")
    parser.add_argument("--worker",action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--target")
    parser.add_argument("--phase",default="none")
    parser.add_argument("--generation",default="new")
    args=parser.parse_args()
    if args.worker:
        validate_id(args.job);validate_id(args.target)
        worker(args)
        return 0
    clip,plan,transcript,source,candidate,qa,config=fixture(args.source_export)
    stamp=str(time.time_ns())
    job_id="job_bundle_recovery_"+stamp
    target_id="c_bundle_recovery_"+stamp
    job=ROOT/"work"/job_id
    job.mkdir(parents=True)
    target=ROOT/"exports"/target_id
    commands=[]
    def command(phase="none",generation="new"):
        result=[sys.executable,str(Path(__file__).resolve()),"--worker","--source-export",str(args.source_export.resolve()),"--job",job_id,"--target",target_id,"--phase",phase,"--generation",generation]
        commands.append(result)
        return result
    run_process(command(generation="previous"),cwd=ROOT,timeout=300)
    previous=read_json(target/"bundle_manifest.json")["files"]
    def kill(phase):
        (job/"kill_barrier.json").unlink(missing_ok=True)
        with (job/f"worker_{phase}.txt").open("wb") as log:
            child=subprocess.Popen(command(phase),cwd=ROOT,stdout=log,stderr=log,start_new_session=os.name!="nt",creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0)
            owned=register_child(child,job,commands[-1])
            try:
                deadline=time.monotonic()+300
                while not (job/"kill_barrier.json").exists():
                    if child.poll() is not None:raise RuntimeError(f"Export worker exited before barrier: {child.returncode}")
                    if time.monotonic()>deadline:raise TimeoutError("Export barrier was not reached")
                    time.sleep(.02)
                barrier_record=read_json(job/"kill_barrier.json")
                # Native venv Python can be a launcher with a second Python
                # process below it. Kill the owned tree, not just the launcher.
                terminate_tree(child)
                code=child.wait(timeout=10)
            finally:
                if child.poll() is None:terminate_tree(child)
                owned.unlink(missing_ok=True)
        orphans=recover_children(job)
        journal=read_json(job/f"bundle_transaction_{target_id}.json")
        recovery=recover_export_bundles(job,ROOT/"exports")
        return {"barrier":barrier_record,"killed_returncode":code,"journal_phase_at_kill":journal["phase"],"recovery":recovery,"terminated_owned_orphans":orphans}
    building=kill("building")
    building["previous_hashes_preserved"]=read_json(target/"bundle_manifest.json")["files"]==previous and _complete(target)
    promotion=kill("previous_moved")
    recovered=read_json(target/"bundle_manifest.json")["files"]
    promotion["complete_after_recovery"]=_complete(target)
    promotion["new_generation"]=read_json(target/"acceptance_generation.json")["generation"]
    run_process(command(),cwd=ROOT,timeout=300)
    baseline=read_json(target/"bundle_manifest.json")["files"]
    partials=[str(path.relative_to(target)) for path in target.rglob("*") if path.is_file() and path.name.endswith(".part")]
    report={"schema_version":5,"test_ids":["T-36 export handoff","Part25.2","Part13.4"],"command":[sys.executable,*sys.argv],"native_windows":os.name=="nt","job_id":job_id,"target_id":target_id,"source_export":str(args.source_export),"fixture_sha256":file_hash(clip),"source_sha256":source.get("sha256",source.get("fingerprint",{}).get("sha256")),"rights_class":source.get("rights_class","unknown"),"commands":commands,"building":building,"promotion":promotion,"recovered_file_hashes":recovered,"uninterrupted_file_hashes":baseline,"all_file_hashes_identical":recovered==baseline,"export_partials":partials,"fault_injection":"Recorded worker barriers after real sidecars and after the durable previous_moved journal; actual OS process-tree kills, no mocked video/FFmpeg", "render_quality_scope":"Existing recorded QA-passed real export, not a new render or human acceptance"}
    report["passed"]=building["previous_hashes_preserved"] and promotion["complete_after_recovery"] and promotion["new_generation"]=="new" and recovered==baseline and not partials
    report["code_hashes"]={name:file_hash(ROOT/name) for name in ("dc/core/bundles.py","dc/exports.py","tools/measure_bundle_recovery.py")}
    destination=ROOT/"reports"/("native_windows" if os.name=="nt" else "verification_v5")/"bundle_recovery.json"
    atomic_write_json(destination,report)
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
