"""T-14 colour patches through the real moving-camera composition/encode."""
from pathlib import Path
import sys
import numpy as np
import cv2
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import content_hash
from dc.core.io import atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.ingest import ingest
from dc.renderer import make_render_plan,render


def main():
    work=ROOT/"work"/"job_colour_acceptance"
    work.mkdir(parents=True,exist_ok=True)
    cfg=load_config(overrides={"output":{"preset":"ultrafast"}})
    feed=cfg.regions["feed"]
    width,height=feed["w"]+160,feed["h"]
    pixels=np.full((height,width,3),128,dtype=np.uint8)
    colours=[(200,32,32),(32,200,32),(32,32,200),(200,200,32),(32,200,200),(200,32,200),(64,64,64),(200,200,200)]
    boxes=[]
    for index,colour in enumerate(colours):
        x,y=160+(index%4)*220,200+(index//4)*300
        pixels[y:y+180,x:x+180]=colour
        boxes.append((x+40,y+40,100,100))
    Image.fromarray(pixels).save(work/"patches.png")
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-loop","1","-framerate","25","-i","patches.png","-t","1","-c:v","ffv1","-pix_fmt","bgr0","source.mkv"],cwd=work,timeout=60)
    source=ingest(work/"source.mkv",work,rights_class="own",rights_note="Generated synthetic colour fixture")
    plan=make_render_plan(source,{"id":"c_colour","start":0,"end":1,"hook":{"headline_options":["Colour fixture"]}},cfg,work,mode="single")
    rect={"x":40,"y":0,"w":feed["w"],"h":feed["h"]}
    plan["framing"].update({"segments":[{"t0":0,"t1":1,"mode":"SINGLE","regions":[rect]}],"path":[{"t":0,**rect},{"t":1,**rect,"x":47.5}]})
    plan["transcript"]={"words":[]}
    plan["plan_hash"]=content_hash(plan)
    render(plan,cfg,work,work/"clip.mp4")
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i","clip.mp4","-frames:v","1","encoded.png"],cwd=work,timeout=60)
    actual=np.asarray(Image.open(work/"encoded.png").convert("RGB"))
    rows=[]
    for colour,(x,y,w,h) in zip(colours,boxes):
        measured=actual[feed["y"]+y:feed["y"]+y+h,x-40:x-40+w].mean(axis=(0,1))
        rgb=np.array([[colour,measured]],dtype=np.float32)/255
        labs=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)[0]
        error=float(np.linalg.norm(labs[0]-labs[1]))
        rows.append({"source_rgb":colour,"encoded_rgb":measured.tolist(),"delta_e_76":error})
    report={"schema_version":5,"test_id":"T-14 colour extension","command":"python tools/measure_colour.py","method":"CIE Lab Delta E76 on decoded patch interiors","path":"real moving warp, lossless feed, final H264/BT709 encode","patches":rows,"threshold":3,"passed":max(row["delta_e_76"] for row in rows)<=3}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"colour.json",report)
    print(report)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
