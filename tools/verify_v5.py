"""Record repeatable local checks with raw output and exact arguments."""
from __future__ import annotations
import json
import argparse
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,atomic_write_bytes,atomic_copy
from dc.core.process import ProcessError,run_process
from dc.core.tools import find_tool


def verification_inputs():
    paths=[]
    for name in ("dc","tests","tools","config"):
        paths.extend(path for path in (ROOT/name).rglob("*") if path.is_file() and path.suffix in {".py",".js",".css",".html",".json",".ps1"} and path.name!="caption_calibration.json")
    paths.extend(path for path in (ROOT/"assets"/"fonts").iterdir() if path.is_file() and path.suffix in {".ttf",".otf"})
    paths.extend(ROOT/name for name in ("requirements.lock","requirements-asr-windows.lock","assets/models/registry.json","pytest.ini","setup.ps1","run.ps1"))
    return {str(path.relative_to(ROOT)):file_hash(path) for path in sorted(set(paths)) if path.is_file()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--skip-real-validation",action="store_true",help="For non-render changes after a recorded real validation")
    parser.add_argument("--report-dir",type=Path,default=ROOT/"reports"/"verification_v5")
    parser.add_argument("--real-output",type=Path,default=ROOT/"work"/"job_verify_v5"/"c_3c6c100b3289.mp4")
    parser.add_argument("--real-plan",type=Path,help="Defaults to render_plan.json beside the selected output")
    parser.add_argument("--asr-lock",action="store_true",help="Resolve and hash-check all native ASR wheels, ignoring installed packages")
    parser.add_argument("--only",help="Comma-separated checks to rerun; others require unchanged code and hash-verified prior logs")
    args=parser.parse_args()
    skip_real=args.skip_real_validation
    from dc.core.io import read_json
    destination=args.report_dir.resolve()
    if not destination.is_relative_to(ROOT/"reports"):raise ValueError("Verification reports must stay under reports")
    destination.mkdir(parents=True,exist_ok=True)
    previous=read_json(destination/"summary.json",{}) or {}
    only=set(args.only.split(",")) if args.only else None
    current_hashes={str(path.relative_to(ROOT)):file_hash(path) for path in (ROOT/"dc").rglob("*") if path.is_file() and path.suffix in {".py",".js",".css"}}
    inputs_at_start=verification_inputs()
    if only and (previous.get("code_hashes")!=current_hashes or previous.get("verification_inputs")!=inputs_at_start):
        raise ValueError("Selective verification requires unchanged application, tests, tools, config, fonts and dependency locks")
    for path in list(destination.iterdir()):
        if path.is_file() and (path.name=="summary.json" or path.suffix==".txt") and not re.search(r"\.[0-9a-f]{16}\.",path.name):
            atomic_copy(path,path.with_name(path.stem+"."+file_hash(path)[:16]+path.suffix))
    commands=[("compile",[sys.executable,"-m","compileall","-q","dc","tools","tests"]),
              ("pytest",[sys.executable,"-m","pytest","-q"]),
              ("unittest",[sys.executable,"-m","unittest","discover","-s","tests","-p","test*.py","-v"]),
              ("doctor",[sys.executable,"-m","dc","doctor"]),
              ("dependencies",[sys.executable,"-m","pip","check"]),
              ("lock_install",[sys.executable,"-m","pip","install","--dry-run","--require-hashes","-r","requirements.lock"]),
              ("studio_js",["node","--check","dc/studio/static/studio.js"])]
    if args.asr_lock:
        commands.append(("asr_lock_install",[sys.executable,"-m","pip","install","--dry-run","--ignore-installed","--only-binary=:all:","--require-hashes","-r","requirements-asr-windows.lock"]))
    real_output=args.real_output.resolve()
    real_plan=(args.real_plan or real_output.parent/"render_plan.json").resolve()
    if not args.skip_real_validation and real_output.is_file() and real_plan.is_file():
        commands.append(("real_validate",[sys.executable,"-m","dc","validate","--output",str(real_output),"--plan",str(real_plan)]))
    elif not args.skip_real_validation:
        raise ValueError("Real validation requires the selected output and plan")
    records=[]
    if only:
        available={name for name,_ in commands}
        if not only<=available:raise ValueError("Unknown selected verification check")
        for name,_ in commands:
            if name in only:continue
            prior=next((row for row in previous.get("commands",[]) if row["name"]==name),None)
            if not prior or prior["exit_code"]!=0 or file_hash(ROOT/prior["raw_output"])!=prior["sha256"]:
                raise ValueError(f"No intact passing evidence for {name}")
            records.append({**prior,"reused_unchanged_code_and_verified_log":True})
        commands=[row for row in commands if row[0] in only]
    for name,args in commands:
        began=time.monotonic()
        code=0
        try:output=run_process(args,cwd=ROOT,timeout=600,output_limit=2_000_000)
        except ProcessError as exc:code,output=exc.returncode,exc.output
        log=destination/(name+".txt")
        atomic_write_bytes(log,output.encode("utf-8"))
        records.append({"name":name,"args":args,"cwd":str(ROOT),"exit_code":code,"elapsed_s":round(time.monotonic()-began,3),"raw_output":str(log.relative_to(ROOT)),"sha256":file_hash(log)})
        print(json.dumps(records[-1]),flush=True)
    if skip_real:
        prior=next((row for row in previous.get("commands",[]) if row["name"]=="real_validate"),None)
        if prior and file_hash(ROOT/prior["raw_output"])==prior["sha256"]:
            records.append({**prior,"reused_evidence_after_non_render_changes":True})
    findings=[]
    patterns={"shell execution":r"shell\s*=\s*True","unsafe DOM":r"innerHTML|\beval\(|document\.write","geometry literals":r"\b(?:524|1216|1136|1740)\b"}
    for path in (ROOT/"dc").rglob("*"):
        if not path.is_file() or path.suffix not in {".py",".js",".html"}:continue
        text=path.read_text(encoding="utf-8")
        for name,pattern in patterns.items():
            if name=="unsafe DOM" and "studio" not in path.parts:continue
            if name=="geometry literals" and ("config" in path.parts or path.name=="layout.py"):continue
            for number,line in enumerate(text.splitlines(),1):
                if re.search(pattern,line):findings.append({"gate":name,"path":str(path.relative_to(ROOT)),"line":number,"text":line})
    atomic_write_json(destination/"security_scan.json",{"schema_version":5,"patterns":patterns,"findings":findings,"status":"passed" if not findings else "failed"})
    if (destination/"real_validate.txt").is_file():
        atomic_write_json(destination/"real_qa.json",json.loads((destination/"real_validate.txt").read_text(encoding="utf-8")))
    from dc.core.io import read_json
    source=read_json(real_output.parent/"source.json",{}) or {}
    publish=read_json(ROOT/"exports"/"c_3c6c100b3289"/"publish_dry_run.json",{}) or {}
    atomic_write_json(destination/"real_source.json",source)
    atomic_write_json(destination/"publish_gate.json",publish)
    final_hashes={str(path.relative_to(ROOT)):file_hash(path) for path in (ROOT/"dc").rglob("*") if path.is_file() and path.suffix in {".py",".js",".css"}}
    changed=current_hashes!=final_hashes
    inputs_at_end=verification_inputs()
    inputs_changed=inputs_at_start!=inputs_at_end
    report={"schema_version":5,"date":"2026-10-05","python":sys.version,"commands":records,"security_findings":findings,"requirements_lock_sha256":file_hash(ROOT/"requirements.lock"),"code_hashes_at_start":current_hashes,"code_hashes":final_hashes,"code_changed_during_checks":changed,"verification_inputs_at_start":inputs_at_start,"verification_inputs":inputs_at_end,"verification_inputs_changed_during_checks":inputs_changed,"status":"passed" if not changed and not inputs_changed and not findings and all(item["exit_code"]==0 for item in records) else "failed"}
    atomic_write_json(destination/"summary.json",report)
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":raise SystemExit(main())
