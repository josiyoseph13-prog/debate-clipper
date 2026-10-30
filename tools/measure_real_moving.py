"""T-18 exercise a disclosed manual moving path on supplied real footage."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import content_hash
from dc.core.io import read_json,atomic_write_json
from dc.renderer import make_render_plan,render
from dc.layout import crop_rect
from dc.qa import validate_output
from dc.ingest import ingest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--static",action="store_true")
    parser.add_argument("--report-dir",type=Path,default=ROOT/"reports"/"verification_v5")
    args=parser.parse_args()
    job=ROOT/"work"/"job_verify_v5"
    folder=ROOT/"work"/("job_current_static" if args.static else "job_current_moving")
    folder.mkdir(parents=True,exist_ok=True)
    source=ingest(ROOT/"input"/"xmp4EdJvPfo.mp4",folder,rights_class="unknown",rights_note="Supplied real source; no rights attestation")
    transcript=read_json(job/"transcript.json")
    candidate=next(row for row in read_json(job/"candidates.json")["candidates"] if row["id"]=="c_3c6c100b3289")
    config=load_config()
    rect=crop_rect(source["width"],source["height"],config)
    plan=make_render_plan(source,candidate,config,folder,mode="auto" if args.static else "manual",manual_regions=None if args.static else [rect])
    if not args.static:
        plan["framing"]["path"]=[{"t":0,**rect,"x":rect["x"]-15},{"t":plan["trim"]["duration"],**rect,"x":rect["x"]+15}]
    plan.update({"transcript":transcript,"captions_ass":str(folder/"captions.ass"),"caption_plan":str(folder/"captions_plan.json"),"chrome_png":str(folder/"chrome.png"),"manual_test_path":not args.static})
    plan["plan_hash"]=content_hash({key:value for key,value in plan.items() if key!="plan_hash"})
    atomic_write_json(folder/"render_plan.json",plan)
    rendered=render(plan,config,folder,folder/"clip.mp4")
    report=validate_output(folder/"clip.mp4",plan,config,folder/"export_report.json")
    atomic_write_json(args.report_dir/("real_static.json" if args.static else "real_moving.json"),{"schema_version":5,"test_id":"T-12" if args.static else "T-18","command":[sys.executable,*sys.argv],"media_id":source["source_id"],"source_sha256":source["fingerprint"]["sha256"],"rights_class":source["rights_class"],"manual_test_path":not args.static,"automatic_framing_quality_verified":False,"render":rendered,"qa":report})
    print({"status":report["status"],"failed_checks":[row["name"] for row in report["checks"] if not row["passed"]]})
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":raise SystemExit(main())
