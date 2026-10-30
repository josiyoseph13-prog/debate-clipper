"""Check the original logo and V5's full-chrome encoded fidelity gate."""
import argparse
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import read_json,atomic_write_json
from dc.core.hashing import file_hash,content_hash
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.renderer import make_render_plan,render


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reuse-render",action="store_true",help="Inspect the existing recorded composition without rendering again")
    args=parser.parse_args()
    folder=ROOT/"work"/"job_supplied_logo"
    folder.mkdir(parents=True,exist_ok=True)
    config=load_config()
    source=read_json(ROOT/"work"/"job_verify_v5"/"source.json")
    transcript=read_json(ROOT/"work"/"job_verify_v5"/"transcript.json")
    plan=make_render_plan(source,{"id":"c_real_logo","start":1.22,"end":5.22,"hook":{"headline_options":["Political Lens logo check"]}},config,folder)
    plan["transcript"]=transcript
    plan["plan_hash"]=content_hash({key:value for key,value in plan.items() if key!="plan_hash"})
    if not args.reuse_render:atomic_write_json(folder/"render_plan.json",plan)
    previous=read_json(ROOT/"reports"/"supplied_media"/"logo_render.json",{}) or {}
    if args.reuse_render and previous.get("config_hash")!=config.hash():
        raise ValueError("Brand configuration changed; a fresh render is required")
    result=previous["render"] if args.reuse_render else render(plan,config,folder,folder/"clip.mp4")
    if args.reuse_render and result["output_sha256"] != file_hash(folder/"clip.mp4"):
        raise ValueError("Recorded render hash does not match the existing file")
    frame=folder/"decoded_frame.png"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss","1","-i",folder/"clip.mp4","-frames:v","1",frame],timeout=60)
    logo=config.get("header","logo")
    box=(logo["x"],logo["y"],logo["x"]+logo["d"],logo["y"]+logo["d"])
    with Image.open(folder/"chrome.png") as image:
        chrome=np.asarray(image.convert("RGB"),dtype=float)
        original_region=image.crop(box).convert("RGB")
    with Image.open(ROOT/logo["file"]) as image:
        artwork=image.convert("RGBA")
    artwork.thumbnail((logo["d"],logo["d"]),Image.Resampling.LANCZOS)
    mask=Image.new("L",artwork.size,0)
    ImageDraw.Draw(mask).ellipse((0,0,artwork.width-1,artwork.height-1),fill=255)
    expected_artwork=Image.new("RGBA",artwork.size,"white")
    expected_artwork.paste(artwork,(0,0),mask)
    identity=np.array_equal(np.asarray(original_region),np.asarray(expected_artwork.convert("RGB")))
    fps=float(plan["frame_rate"]["target_cfr"])
    count=int(config.get("qa","chrome_samples",default=12))
    indices=sorted(set(round(index*(plan["trim"]["duration"]*fps-1)/max(1,count-1)) for index in range(count)))
    expression="+".join(f"eq(n\\,{index})" for index in indices)
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",folder/"clip.mp4","-vf",f"select={expression}","-fps_mode","vfr","-frames:v",str(count),folder/"chrome_sample_%02d.png"],timeout=60)
    samples=[]
    for number in range(1,len(indices)+1):
        path=folder/f"chrome_sample_{number:02d}.png"
        if not path.is_file():raise RuntimeError("Requested chrome sample is missing")
        with Image.open(path) as image:
            pixels=np.asarray(image.convert("RGB"),dtype=float)
            encoded=np.asarray(image.crop(box).convert("RGB"),dtype=float)
        samples.append({"frame":path.name,"chrome_mae":float(np.abs(pixels[:chrome.shape[0]]-chrome).mean()),"logo_region_mae":float(np.abs(encoded-np.asarray(original_region,dtype=float)).mean())})
    threshold=float(config.get("qa","chrome_mae",default=2.5))
    report={"schema_version":5,"test_id":"T-12 / Part13.3 chrome integrity; original supplied-artwork identity","source_id":source["source_id"],"source_rights_class":source["rights_class"],"source_interval":[1.22,5.22],"render":result,"logo":read_json(folder/"chrome.json")["logo"],"original_artwork_pixels_equal":identity,"samples":samples,"chrome_mae_threshold":threshold,"passed":identity and len(samples)>=count and max(row["chrome_mae"] for row in samples)<=threshold,"logo_region_metric":"Diagnostic only: V5 applies MAE2.5 to the whole chrome, not an invented per-logo gate. YUV420 and encoding alter fine colour edges.","supersedes_per_logo_gate":previous.get("threshold"),"decoded_frame":str(frame.relative_to(ROOT)),"human_look_review":"pending","command":[sys.executable,*sys.argv],"config_hash":config.hash()}
    atomic_write_json(ROOT/"reports"/"supplied_media"/"logo_render.json",report)
    print(report)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
