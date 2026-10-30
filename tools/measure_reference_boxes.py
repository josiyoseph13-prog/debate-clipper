"""T-02 measured header/hook bounds against the supplied complete screenshot."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.chrome import render_chrome
from dc.core.config import load_config
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json


def element_boxes(pixels):
    # Independently selected reference search windows, not renderer manifests.
    windows={"logo":(80,110,272,315),"wordmark":(270,145,674,242),"handle":(285,242,625,301),"badge":(666,145,756,242),"hook":(100,320,980,516)}
    boxes={}
    for name,(left,top,right,bottom) in windows.items():
        crop=pixels[top:bottom,left:right].astype(np.int16)
        if name=="badge":mask=(crop[:,:,1]>150)&(crop[:,:,2]>150)&(crop[:,:,1]-crop[:,:,0]>30)
        elif name=="handle":mask=np.min(crop,axis=2)<220
        else:mask=np.min(crop,axis=2)<175
        rows,cols=np.where(mask)
        boxes[name]=[int(cols.min()+left),int(rows.min()+top),int(cols.max()+left+1),int(rows.max()+top+1)] if len(rows) else None
    return boxes


def main():
    reference=ROOT/"reference image"/"Screenshot 2026-10-03 070914.png"
    cfg=load_config()
    destination=ROOT/"reports"/"supplied_media"
    with Image.open(reference) as image:
        # Complete portrait inside black player bars: independently inspected.
        clean=image.crop((75,65,616,1027)).resize((cfg.canvas["w"],cfg.canvas["h"]),Image.Resampling.LANCZOS).convert("RGB")
    chrome,manifest=render_chrome(cfg,"Why We Need to Abolish the Department of Education 🎓",destination/"bbox_chrome.png")
    expected=element_boxes(np.asarray(clean))
    actual=element_boxes(np.asarray(chrome.convert("RGB")))
    results={}
    for name,box in expected.items():
        measured=actual[name]
        deltas=[b-a for a,b in zip(box,measured)] if box and measured else None
        results[name]={"reference_bbox":box,"rendered_bbox":measured,"edge_deltas_px":deltas,"max_absolute_delta_px":max(map(abs,deltas)) if deltas else None,"passed":bool(deltas) and max(map(abs,deltas))<=10}
    sheet=Image.new("RGB",(cfg.canvas["w"]*2,chrome.height),"white")
    sheet.paste(clean.crop((0,0,cfg.canvas["w"],chrome.height)),(0,0))
    sheet.paste(chrome.convert("RGB"),(cfg.canvas["w"],0))
    draw=ImageDraw.Draw(sheet)
    for name in expected:
        if expected[name]:draw.rectangle(expected[name],outline="blue",width=2)
        if actual[name]:
            x0,y0,x1,y1=actual[name]
            draw.rectangle((x0+cfg.canvas["w"],y0,x1+cfg.canvas["w"],y1),outline="red",width=2)
    sheet.save(destination/"bbox_comparison.png")
    report={"schema_version":5,"test_id":"T-02 bbox portion","command":[sys.executable,*sys.argv],"reference":str(reference.relative_to(ROOT)),"reference_sha256":file_hash(reference),"player_video_crop":[75,65,541,962],"normalization":"uniform screenshot-to-video scale, rounded raster dimensions; screenshot precision only","config_hash":cfg.hash(),"results":results,"passed":all(row["passed"] for row in results.values()),"manifest":manifest,"ssim_gate":"not claimed: screenshots/player scaling and missing original wordmark prevent a clean same-content full-frame equivalence claim","human_acceptance":"open"}
    atomic_write_json(destination/"reference_bbox.json",report)
    print({name:row["max_absolute_delta_px"] for name,row in results.items()})
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
