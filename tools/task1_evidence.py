"""Collect Task 1 evidence from real render reports without inventing passes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
import numpy as np
from dc.core.io import read_json,atomic_write_json
from dc.core.hashing import file_hash
from tools.capture_fix3_frames import capture
from tools.measure_supplied_style import frame_metrics,bbox

IDS=("c_a9ef26901548","c_3b29c90cfa17","c_9ecc907d1157")
OLD=("clip_01_okay-so-what-if-you-make-fun-of-a-white-person_7m55s-8m23s_c_a9ef26901548_f6f886c6","clip_02_but-my-question-is-how-can-christian-teaching-on-love_3m10s-3m38s_c_3b29c90cfa17_a17ccb77","clip_03_all-that-matters-to-god-is-not-black-or-white-or-republi_5m21s-5m53s_c_9ecc907d1157_c86ca937")
EXPORTS=ROOT/"exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a"
DEST=ROOT/"reports/fix3"


def output_report(candidate):
    text=(DEST/f"task1_verified_{candidate}.txt").read_text(encoding="utf-8")
    return json.loads(text[text.index('\n{\n')+1:])


def ink_boxes(path):
    p=np.asarray(Image.open(path).convert("RGB"))
    boxes={}
    windows={"logo":(75,110,275,315),"wordmark":(270,145,673,240),"handle":(290,240,640,300),"badge":(673,155,735,235),"headline":(0,330,1080,505)}
    for key,(x,y,r,b) in windows.items():
        tile=p[y:b,x:r]
        mask=np.min(tile,axis=2)<180
        if key=="badge":
            mask=(tile[:,:,0]<140)&(tile[:,:,1]>150)&(tile[:,:,2]>150)
        box=bbox(mask)
        boxes[key]=[box[0]+x,box[1]+y,box[2]+x,box[3]+y] if box else None
    return boxes


def main():
    references=sorted((DEST/"reference").glob("*.png"))
    result={"reference_geometry":[frame_metrics(p) for p in references],"reference_ink_boxes":ink_boxes(references[2]),"clips":[]}
    for index,(candidate,old_name) in enumerate(zip(IDS,OLD),1):
        report=output_report(candidate)
        export_dir=Path(report["qa"]["export"]["export_dir"])
        video=next(p for p in export_dir.glob(f"{index:02d}_*.mp4"))
        before_video=next(p for p in (EXPORTS/old_name).glob(f"{index:02d}_*.mp4"))
        before=capture(before_video,DEST/"before",f"original_{index:02d}")
        after=capture(video,DEST/"after",f"verified_{index:02d}")
        # All six sampled times are visible on the comparison sheet.
        sheet=Image.new("RGB",(1080,6*690),"white")
        draw=ImageDraw.Draw(sheet)
        for row in range(6):
            for col,(label,path) in enumerate((("REFERENCE",references[row]),("BEFORE",before[row]),("AFTER",after[row]))):
                image=Image.open(path).convert("RGB")
                image.thumbnail((360,640))
                sheet.paste(image,(col*360,row*690+30))
                draw.text((col*360+10,row*690+8),f"{label} sample {row+1}",fill="black")
        comparison=DEST/"compare"/f"clip_{index:02d}_reference_before_after.png"
        sheet.save(comparison)
        framing=next(c["value"] for c in report["qa"]["checks"] if c["name"]=="framing_quality")
        config=read_json(export_dir/"renderer_config.json")["config"]
        footer=config["regions"]["bottom_white"]["y"]
        footer_pixels=[]
        for path in after:
            p=np.asarray(Image.open(path).convert("RGB"))
            footer_pixels.append(int((np.min(p[footer+6:],axis=2)<230).sum()))
        result["clips"].append({"candidate_id":candidate,"video":str(video.relative_to(ROOT)),"sha256":file_hash(video),"qa_status":report["qa"]["status"],"framing":framing,"after_frames":[str(p.relative_to(ROOT)) for p in after],"comparison":str(comparison.relative_to(ROOT)),"configured_regions":config["regions"],"output_ink_boxes":ink_boxes(after[2]),"output_geometry":[frame_metrics(p) for p in after],"footer_dark_pixel_counts":footer_pixels,"filename_burn_in":"No filename visible in the six decoded frames; footer dark-pixel counts recorded. This is sampled visual evidence, not OCR of every frame.","wordmark_fallback":not (ROOT/"assets/wordmark.png").exists()})
    atomic_write_json(DEST/"task1_evidence.json",result)
    print(json.dumps({"clips":[{k:r[k] for k in ("video","qa_status","comparison","output_ink_boxes","footer_dark_pixel_counts")} for r in result["clips"]],"reference_geometry":result["reference_geometry"],"reference_ink_boxes":result["reference_ink_boxes"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
