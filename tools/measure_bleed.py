"""Measure real-footage bottom-boundary bleed at CRF 18, 20 and 23."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import read_json,atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.renderer import make_render_plan,render


def main():
    job=ROOT/"work"/"job_verify_v5"
    source=read_json(job/"source.json")
    transcript=read_json(job/"transcript.json")
    rows=[]
    for crf in (18,20,23):
        work=job/"bleed"/str(crf)
        work.mkdir(parents=True,exist_ok=True)
        cfg=load_config(overrides={"output":{"crf":crf,"preset":"medium"}})
        plan=make_render_plan(source,{"id":"c_bleed","start":1.22,"end":3.22,"hook":{"headline_options":["Boundary measurement"]}},cfg,work)
        plan["transcript"]=transcript
        render(plan,cfg,work,work/"clip.mp4")
        boundary=cfg.regions["bottom_white"]["y"]
        profiles=[]
        extent=-1
        for index,t in enumerate((0,.5,1,1.5)):
            target=work/f"sample{index}.png"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(t),"-i",work/"clip.mp4","-frames:v","1",target],timeout=60)
            with Image.open(target) as frame:pixels=np.asarray(frame.convert("RGB"),dtype=float)
            errors=255-pixels[boundary:boundary+12].min(axis=2)
            profile=[{"distance_px":distance,"mean_error":float(row.mean()),"p99_error":float(np.percentile(row,99)),"pixels_over_5":int((row>5).sum())} for distance,row in enumerate(errors)]
            detected=[row["distance_px"] for row in profile if row["p99_error"]>5]
            extent=max(extent,max(detected,default=-1))
            profiles.append({"time":t,"rows":profile})
        guard=int(cfg.get("qa","bottom_guard_px",default=4))
        rows.append({"crf":crf,"samples":profiles,"last_affected_row_distance":extent,"required_guard_px":extent+1,"configured_guard_px":guard,"guard_passed":guard>=extent+1})
    report={"schema_version":5,"test_id":"T-14 bleed extension","command":"python tools/measure_bleed.py","media_id":source["source_id"],"source_interval":[1.22,3.22],"method":"decoded RGB row profile; affected when p99 white deviation exceeds 5","profiles":rows,"passed":all(row["guard_passed"] for row in rows),"whole_source_verified":False,"top_boundary_profile_measured":False}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"bleed.json",report)
    print({"passed":report["passed"],"guards":[{key:row[key] for key in ("crf","last_affected_row_distance","required_guard_px","guard_passed")} for row in rows]})


if __name__=="__main__":main()
