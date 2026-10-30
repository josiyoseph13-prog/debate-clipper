"""Read all supplied references and build unlabelled golden-test records."""
from pathlib import Path
import json
import sys
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool


def main():
    report=ROOT/"reports"/"supplied_media"
    report.mkdir(parents=True,exist_ok=True)
    rows=[]
    for category in ("reference image","reference videos","golden accuracy video"):
        for index,path in enumerate(sorted((ROOT/category).rglob("*"))):
            if not path.is_file():continue
            if path.suffix.lower() in {".png",".jpg",".jpeg",".webp"}:
                with Image.open(path) as opened:
                    rows.append({"category":category,"path":str(path.relative_to(ROOT)),"sha256":file_hash(path),"size":list(opened.size),"use":"visual authority only; not an output overlay"})
                continue
            if path.suffix.lower() not in {".mp4",".mkv",".mov",".webm"}:continue
            probe=json.loads(run_process([require_tool("ffprobe"),"-v","error","-show_format","-show_streams","-of","json",path],timeout=30))
            duration=float(probe["format"]["duration"])
            video=next(row for row in probe["streams"] if row["codec_type"]=="video")
            digest=file_hash(path)
            media_id=digest[:16]
            target=report/media_id
            target.mkdir(exist_ok=True)
            fractions=(.02,.10,.22,.38,.55,.70,.85,.97) if category=="reference videos" else (.05,.5,.95)
            times=[round(duration*fraction,3) for fraction in fractions]
            sheet=Image.new("RGB",(540*4,1020*((len(times)+3)//4)),"#dddddd")
            draw=ImageDraw.Draw(sheet)
            for sample,t in enumerate(times):
                image_path=target/f"frame_{sample}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(t),"-i",path,"-frames:v","1",image_path],timeout=60)
                with Image.open(image_path) as opened:
                    image=opened.convert("RGB")
                    image.thumbnail((540,960))
                    x,y=(sample%4)*540,(sample//4)*1020
                    sheet.paste(image,(x,y+35))
                    draw.text((x+10,y+8),f"{path.name} | {t:.3f}s",fill="black")
            sheet_path=target/"contact_sheet.jpg"
            sheet.save(sheet_path,quality=93)
            row={"category":category,"path":str(path.relative_to(ROOT)),"media_id":media_id,"sha256":digest,"duration_s":duration,"width":video["width"],"height":video["height"],"fps":video["avg_frame_rate"],"has_audio":any(row["codec_type"]=="audio" for row in probe["streams"]),"contact_sheet":str(sheet_path.relative_to(ROOT)),"sample_times":times,"rights_class":"unknown","human_labels_supplied":False,"use":"style comparison; do not transfer crop/timing/line breaks" if category=="reference videos" else "accuracy test media only; labels must be independently supplied"}
            rows.append(row)
            if category=="golden accuracy video":
                atomic_write_json(target/"labels_template.json",{"schema_version":5,"media_id":media_id,"source_sha256":digest,"rights":{"class":"unknown","note":"","attested_by":"","evidence_url":""},"source_kind":"unconfirmed: raw long source or edited short?","raters":[],"blind_would_post_spans":[],"rated_candidates":[],"framing_windows":[],"hand_timed_words":[],"name_occurrences":[],"diarization_excerpts":[],"status":"awaiting_real_labels","frame_probe":row})
            print(path.name,video["width"],video["height"],duration,flush=True)
    logo=ROOT/"dd12b684ebfbbd0a60845e8ecdb5c13e~tplv-tiktokx-cropcenter_1080_1080.jpg"
    with Image.open(logo) as image:logo_info={"path":str(logo.relative_to(ROOT)),"sha256":file_hash(logo),"size":list(image.size),"mode":image.mode,"separate_horizontal_wordmark":False,"transparent":False,"user_attestation":"Real Political Lens logo supplied by user"}
    atomic_write_json(report/"inventory.json",{"schema_version":5,"logo":logo_info,"media":rows,"labels_or_rights_not_inferred":True})


if __name__=="__main__":main()
