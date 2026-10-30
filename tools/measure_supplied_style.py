"""Measure supplied style samples; never copy reference media into exports."""
from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import file_hash
from dc.core.io import read_json, atomic_write_json, atomic_write_bytes


def bbox(mask):
    rows,columns=np.where(mask)
    return [int(columns.min()),int(rows.min()),int(columns.max()+1),int(rows.max()+1)] if len(rows) else None


def caption_mask(pixels):
    """Find the dominant lime text row near the reference's caption band."""
    h,w=pixels.shape[:2]
    accent=np.array([180,248,61])
    mask=np.max(np.abs(pixels.astype(np.int16)-accent),axis=2)<30
    mask[:round(h*.43)]=False
    mask[round(h*.70):]=False
    mask[:,:round(w*.08)]=False
    mask[:,round(w*.92):]=False
    counts=mask.sum(axis=1)
    bands=[]
    start=None
    for row,active in enumerate(counts>=8):
        if active and start is None:start=row
        if start is not None and (not active or row==h-1):
            end=row if not active else row+1
            if end-start>=8:bands.append((int(counts[start:end].sum()),start,end))
            start=None
    if not bands:return np.zeros(mask.shape,dtype=bool)
    _,top,bottom=max(bands)
    mask[:top]=False
    mask[bottom:]=False
    return mask


def frame_metrics(path):
    with Image.open(path) as image:pixels=np.asarray(image.convert("RGB"))
    h,w=pixels.shape[:2]
    # A wide row with photo detail locates the white-chrome/feed transitions.
    nonwhite=np.mean(np.min(pixels,axis=2)<230,axis=1)
    candidates=np.where((nonwhite>.72)&(np.arange(h)>h*.15)&(np.arange(h)<h*.4))[0]
    start=int(candidates[0]) if len(candidates) else None
    bottom_candidates=np.where((nonwhite<.02)&(np.arange(h)>h*.80))[0]
    bottom=int(bottom_candidates[0]) if len(bottom_candidates) else None
    green=caption_mask(pixels)
    box=bbox(green)
    return {"file":str(path.relative_to(ROOT)),"sha256":file_hash(path),"size":[w,h],"feed_top_row_estimate":start,"bottom_white_row_estimate":bottom,"accent_fill_bbox":box,"accent_fill_pixels":int(green.sum()),"accent_rgb_median":np.median(pixels[green],axis=0).round(1).tolist() if green.any() else None,"method":"white/photo row transitions and near-lime fill; sampled heuristic, not human accuracy labels"}


def font_mask(path,text,width,height):
    font=ImageFont.truetype(str(path),120)
    box=font.getbbox(text)
    image=Image.new("L",(box[2]-box[0]+4,box[3]-box[1]+4))
    ImageDraw.Draw(image).text((2-box[0],2-box[1]),text,font=font,fill=255)
    box=image.getbbox()
    ink=image.crop(box)
    natural_ratio=ink.width/ink.height
    # Normalize ink bounds for a glyph-shape comparison, not font identity proof.
    normalized=np.asarray(ink.resize((width,height),Image.Resampling.LANCZOS))>=160
    return normalized,natural_ratio


def compare_fonts(destination):
    samples=[("RIGHT",ROOT/"reference image"/"Screenshot 2026-10-03 070914.png"),
             ("HAVE",destination/"e6eb160b15cff47a"/"frame_0.png"),
             ("THE",destination/"7291182ecd9e49fd"/"frame_1.png"),
             ("TWO",destination/"7291182ecd9e49fd"/"frame_0.png"),
             ("CRENSHAW",destination/"9ec2bc47bfa58fad"/"frame_3.png"),
             ("FUN",destination/"f320be19c3f64c9e"/"frame_2.png")]
    fonts=["Poppins-ExtraBold.ttf","Montserrat-Black.ttf","Montserrat-ExtraBold.ttf","Inter-Bold.ttf","Anton-Regular.ttf","BebasNeue-Regular.ttf"]
    records=[]
    sheet=Image.new("RGB",(780,110*(len(fonts)+1)*len(samples)),"#eeeeee")
    draw=ImageDraw.Draw(sheet)
    for sample_index,(text,path) in enumerate(samples):
        with Image.open(path) as image:pixels=np.asarray(image.convert("RGB"))
        if text=="RIGHT":
            # This screenshot includes the player outside a 541×962 video.
            pixels=pixels[65:1027,75:616]
        mask=caption_mask(pixels)
        box=bbox(mask)
        if box is None:raise ValueError(f"No reference fill for {text}")
        left,top,right,bottom=box
        observed=mask[top:bottom,left:right]
        row0=sample_index*(len(fonts)+1)*110
        tile=Image.fromarray(np.uint8(observed)*255).convert("RGB")
        tile.thumbnail((480,75))
        sheet.paste(tile,(260,row0+20))
        draw.text((8,row0+20),f"Reference: {text}\n{right-left}x{bottom-top}",fill="black")
        for index,name in enumerate(fonts):
            font=ROOT/"assets"/"fonts"/name
            if not font.is_file():continue
            predicted,ratio=font_mask(font,text,right-left,bottom-top)
            best=0.0
            for dy in range(-2,3):
                for dx in range(-2,3):
                    padded=np.pad(predicted,2)
                    shifted=padded[2+dy:2+dy+observed.shape[0],2+dx:2+dx+observed.shape[1]]
                    union=np.logical_or(observed,shifted).sum()
                    best=max(best,float(np.logical_and(observed,shifted).sum()/max(1,union)))
            records.append({"text":text,"reference":str(path.relative_to(ROOT)),"reference_sha256":file_hash(path),"reference_fill_bbox":box,"font":name,"font_sha256":file_hash(font),"normalized_glyph_iou":round(best,5),"natural_aspect_ratio":round(ratio,5),"reference_aspect_ratio":round(observed.shape[1]/observed.shape[0],5)})
            row=row0+(index+1)*110
            image=Image.fromarray(np.uint8(predicted)*255).convert("RGB")
            image.thumbnail((480,75))
            sheet.paste(image,(260,row+20))
            draw.text((8,row+20),f"{name}\nshape IoU {best:.3f}",fill="black")
    sheet.save(destination/"font_comparison.png")
    ranking=sorted([{"font":name,"mean_normalized_glyph_iou":round(float(np.mean([row["normalized_glyph_iou"] for row in records if row["font"]==name])),5)} for name in fonts if any(row["font"]==name for row in records)],key=lambda row:row["mean_normalized_glyph_iou"],reverse=True)
    return {"samples":records,"ranking":ranking,"method":"near-lime reference fill vs Pillow font fill; normalized ink bounds, ±2px alignment; best among these candidates only, not exact CapCut font identification","comparison_image":"reports/supplied_media/font_comparison.png"}


def main():
    destination=ROOT/"reports"/"supplied_media"
    inventory=read_json(destination/"inventory.json")
    measurements=[]
    for media in inventory["media"]:
        if media["category"]=="reference image":
            metrics=frame_metrics(ROOT/media["path"])
            metrics["player_ui_present"]=True
            metrics["absolute_layout_gate_eligible"]=False
            measurements.append({"media":media,"frames":[metrics]})
        elif media["category"]=="reference videos":
            frames=[frame_metrics(destination/media["media_id"]/f"frame_{index}.png") for index in range(len(media["sample_times"]))]
            measurements.append({"media":media,"frames":frames})
    fonts=compare_fonts(destination)
    config=load_config()
    report={"schema_version":5,"command":[sys.executable,*sys.argv],"test_ids":["T-02 reference measurement preparation","T-16 font comparison preparation"],"reference_images_inspected":5,"reference_videos_sampled":6,"reference_video_frames_measured":sum(len(row["frames"]) for row in measurements if row["media"]["category"]=="reference videos"),"measurements":measurements,"font_comparison":fonts,"configured_font":config.get("captions","font_file"),"reference_used_as_overlay":False,"accuracy_gate":"cannot be proven yet: no independent labels/raters","exact_font_identity":"unknown"}
    atomic_write_json(destination/"style_measurements.json",report)
    lines=["# Political Lens supplied reference study","","All five images and eight samples from each of the six videos were inspected.","Screenshots contain player controls, clipping, scaling and shadows; those are not output design elements.","The clean video samples are the better colour/placement evidence. This is a sampled style study, not full video timing or accuracy acceptance.","","## Shared design","","- White brand/header and footer, circular supplied emblem, grey/red condensed wordmark, grey handle and cyan badge.","- Editorial headline above the footage; footage crop changes with the speaker and source.","- Heavy ALL-CAPS captions, white inactive words, lime active word, dark outline/shadow; normally one to three words, sometimes two lines for long phrases.","- Caption position is near the feed middle. It changes across the edits; copy neither a fixed crop nor one video's line breaks/timing.","- The newer videos have a larger-looking caption fill than the older single-word RIGHT screenshot. The V5 44px calibration is retained as the measured default; exact font identity is unknown.","- The reference platform-style check differs deliberately from the configured brand_check; account verification has not been attested.","","## Measured samples","","| Reference | Samples | Feed-top estimates | Bottom-white estimates | Accent RGB median range |","|---|---:|---|---|---|"]
    for row in measurements:
        frames=row["frames"]
        colours=[frame["accent_rgb_median"] for frame in frames if frame["accent_rgb_median"]]
        lines.append(f"| {row['media']['path']} | {len(frames)} | {sorted(set(frame['feed_top_row_estimate'] for frame in frames if frame['feed_top_row_estimate'] is not None))} | {sorted(set(frame['bottom_white_row_estimate'] for frame in frames if frame['bottom_white_row_estimate'] is not None))} | {colours} |")
    lines.extend(["","All row/fill estimates are reproducible colour heuristics. Trees, pop animation and compressed edges can bias them; they are not annotated truth or a passed T-02 bbox/SSIM gate.","","## Font comparison","","Six named words were compared across the screenshot and five clean-video samples. Shapes are normalized to the observed ink bounds; scores rank the tested candidates, not the unknown CapCut font.",""])
    lines.extend(f"- {row['font']}: mean normalized glyph IoU {row['mean_normalized_glyph_iou']}" for row in fonts["ranking"])
    lines.extend(["","See `font_comparison.png` and `style_measurements.json` for crops, font/source hashes and every result. No reference frame is pasted into the output.","","## Remaining differences","","The supplied JPG is small and opaque, the separate horizontal wordmark is missing, the badge glyph is intentionally different, and exact CapCut font/pop/glow equivalence has not been proven. Human look review and text-masked SSIM remain open."])
    atomic_write_bytes(destination/"reference_study.md",("\n".join(lines)+"\n").encode("utf-8"))
    print({"frames":report["reference_video_frames_measured"],"fonts":fonts["ranking"]})


if __name__=="__main__":main()
