"""Repeat T-16/T-17 on the current fallback with actual lossless libass pixels."""
from pathlib import Path
import json
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.core.hashing import file_hash
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.ingest import ingest
from dc.captions import calibrate_caption
from dc.renderer import make_render_plan,render,lossless_caption_samples


def main():
    cfg=load_config()
    folder=ROOT/"work"/"job_current_caption"
    folder.mkdir(parents=True,exist_ok=True)
    source_path=folder/"synthetic_black.mp4"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=black:s=320x180:r=30:d=2","-c:v","libx264",source_path],timeout=30)
    source=ingest(source_path,folder,rights_class="own",rights_note="Generated black synthetic fixture")
    plan=make_render_plan(source,{"id":"c_current_caption","start":0,"end":2,"hook":{"headline_options":["RIGHT"]}},cfg,folder)
    plan["transcript"]={"words":[{"text":"RIGHT","start":.2,"end":1.6}]}
    rendered=render(plan,cfg,folder,folder/"clip.mp4")
    calibration=calibrate_caption(cfg)
    samples_dir=folder/"lossless"
    samples_dir.mkdir(exist_ok=True)
    samples=lossless_caption_samples(plan,cfg,folder,samples_dir,[.8])
    def pixels(name):
        with Image.open(samples[name][0]) as image:return np.asarray(image.convert("RGB"),dtype=np.int16)
    full,baseline,fill,no_glow=[pixels(name) for name in ("captions","baseline","active_fill","no_glow")]
    mask=np.max(np.abs(fill-baseline),axis=2)>2
    rows,cols=np.where(mask)
    halo_rows,halo_cols=np.where(np.max(np.abs(full-no_glow),axis=2)>2)
    changed=np.max(np.abs(full-baseline),axis=2)>2
    feed=cfg.regions["feed"]
    outside=int(changed[:feed["y"]].sum()+changed[feed["y"]+feed["h"]:].sum())
    measured={"fill_w":int(cols.max()-cols.min()+1),"fill_h":int(rows.max()-rows.min()+1),"center_x":float((cols.min()+cols.max())/2),"center_y":float((rows.min()+rows.max())/2),"halo_left_px":int(cols.min()-halo_cols.min()),"halo_right_px":int(halo_cols.max()-cols.max()),"outside_feed_pixels":outside}
    t16=abs(measured["fill_w"]-cfg.get("captions","target_word_w_RIGHT"))<=3 and abs(measured["fill_h"]-cfg.get("captions","target_cap_px"))<=3 and abs(measured["center_x"]-cfg.get("captions","center_x"))<=6 and abs(measured["center_y"]-cfg.get("captions","center_y_canvas"))<=6 and calibration["status"]=="calibrated"
    t17=40<=measured["halo_left_px"]<=50 and 40<=measured["halo_right_px"]<=50 and outside==0
    report={"schema_version":5,"test_ids":["T-16","T-17"],"command":[sys.executable,*sys.argv],"level":"V2 synthetic black fixture, not all moving backgrounds or human font equivalence","config_hash":cfg.hash(),"font_sha256":file_hash(ROOT/cfg.get("captions","font_file")),"calibration":calibration,"render":rendered,"measurement":measured,"checks":{"T-16":t16,"T-17":t17},"passed":t16 and t17,"lossless_samples":{name:[str(path.relative_to(ROOT)) for path in paths] for name,paths in samples.items()}}
    atomic_write_json(ROOT/"reports"/"supplied_media"/"current_caption.json",report)
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
