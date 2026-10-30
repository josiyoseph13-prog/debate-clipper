"""T-14 real and high-contrast generated top/bottom boundary profiles."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import content_hash,file_hash
from dc.core.io import atomic_write_json,read_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.ingest import ingest
from dc.renderer import make_render_plan,render


def main():
    import numpy as np
    from PIL import Image
    work=ROOT/"work"/"job_current_bleed"
    work.mkdir(parents=True,exist_ok=True)
    pattern=work/"pattern.mp4"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=640x360:r=30:d=2","-an","-c:v","libx264","-crf","0",pattern],timeout=60)
    inputs=[("real_start",ROOT/"input"/"xmp4EdJvPfo.mp4",1.22),
            ("real_middle",ROOT/"input"/"xmp4EdJvPfo.mp4",181.0),
            ("real_late",ROOT/"input"/"xmp4EdJvPfo.mp4",901.0),
            ("generated_pattern",pattern,0.0)]
    transcript=read_json(ROOT/"work"/"job_verify_v5"/"transcript.json")
    records=[]
    for name,path,start in inputs:
        source_work=work/name
        source_work.mkdir(exist_ok=True)
        source=ingest(path,source_work,rights_class="own" if path==pattern else "unknown",rights_note="Generated test pattern" if path==pattern else "User supplied; no rights attestation")
        for crf in (18,20,23):
            folder=source_work/str(crf)
            folder.mkdir(exist_ok=True)
            cfg=load_config(overrides={"output":{"crf":crf,"preset":"medium"}})
            plan=make_render_plan(source,{"id":"c_bleed_"+name,"start":start,"end":start+2,"hook":{"headline_options":["Boundary measurement"]}},cfg,folder)
            plan["transcript"]=transcript if path!=pattern else {"words":[]}
            plan["plan_hash"]=content_hash({key:value for key,value in plan.items() if key!="plan_hash"})
            atomic_write_json(folder/"render_plan.json",plan)
            render(plan,cfg,folder,folder/"clip.mp4")
            with Image.open(folder/"chrome.png") as image:chrome=np.asarray(image.convert("RGB"),dtype=np.int16)
            top=cfg.regions["feed"]["y"]
            bottom=cfg.regions["bottom_white"]["y"]
            extent={"top":-1,"bottom":-1}
            samples=[]
            for index,time in enumerate((0,.3,.6,.9,1.2,1.7)):
                output=folder/f"sample_{index}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(time),"-i",folder/"clip.mp4","-frames:v","1",output],timeout=60)
                with Image.open(output) as image:pixels=np.asarray(image.convert("RGB"),dtype=np.int16)
                profiles={}
                for side,errors in (("top",np.max(np.abs(pixels[top-12:top]-chrome[top-12:top]),axis=2)[::-1]),("bottom",255-pixels[bottom:bottom+12].min(axis=2))):
                    profiles[side]=[{"distance_px":distance,"mean_error":float(row.mean()),"p99_error":float(np.percentile(row,99)),"pixels_over_5":int((row>5).sum())} for distance,row in enumerate(errors)]
                    extent[side]=max(extent[side],max((row["distance_px"] for row in profiles[side] if row["p99_error"]>5),default=-1))
                samples.append({"time":time,"chrome_mae":float(np.abs(pixels[:top]-chrome).mean()),"profiles":profiles})
            guard=int(cfg.get("qa","bottom_guard_px",default=4))
            record={"input":name,"source_sha256":source["fingerprint"]["sha256"],"rights_class":source["rights_class"],"interval":[start,start+2],"crf":crf,"config_hash":cfg.hash(),"plan_hash":plan["plan_hash"],"output_sha256":file_hash(folder/"clip.mp4"),"samples":samples,"top_last_affected_distance":extent["top"],"bottom_last_affected_distance":extent["bottom"],"bottom_required_guard_px":extent["bottom"]+1,"bottom_configured_guard_px":guard,"bottom_guard_passed":guard>=extent["bottom"]+1,"chrome_passed":all(row["chrome_mae"]<=2.5 for row in samples)}
            records.append(record)
            print(json.dumps({key:record[key] for key in ("input","crf","top_last_affected_distance","bottom_last_affected_distance","bottom_guard_passed","chrome_passed")}),flush=True)
    result={"schema_version":5,"test_id":"T-14 boundary bleed extension","command":[sys.executable,*sys.argv],"code_hashes":{name:file_hash(ROOT/name) for name in ("dc/renderer.py","dc/chrome.py","tools/measure_current_bleed.py")},"method":"Decoded RGB row profiles; affected at p99 deviation>5, distance0 directly adjacent to feed. Whole chrome retains its unchanged MAE<=2.5 gate; bottom4px guard retains its original threshold.","profiles":records,"top_boundary_profile_measured":True,"whole_source_verified":False,"remaining_scope":"Three sampled real intervals plus one generated pattern, not a universal codec/content guarantee. Top distance is measured, not silently excluded from the full-chrome gate.","passed":all(row["bottom_guard_passed"] and row["chrome_passed"] for row in records)}
    atomic_write_json(ROOT/"reports"/"current_checks"/"bleed.json",result)
    print({"passed":result["passed"]},flush=True)
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
