"""Reproducible half-second reference frames and evidence; no identity inference."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from dc.core.tools import require_tool
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,read_json

DEST=ROOT/"reports/duo_style"


def probe(path):
    return json.loads(subprocess.check_output([require_tool("ffprobe"),"-v","error","-show_streams","-show_format","-of","json",str(path)]))


def sheet(files,times,path,columns=8,thumb=(162,288)):
    rows=(len(files)+columns-1)//columns
    image=Image.new("RGB",(columns*thumb[0],rows*(thumb[1]+24)),"white")
    draw=ImageDraw.Draw(image)
    for index,(file,t) in enumerate(zip(files,times)):
        tile=Image.open(file).convert("RGB");tile.thumbnail(thumb)
        x=(index%columns)*thumb[0];y=(index//columns)*(thumb[1]+24)
        image.paste(tile,(x,y+24));draw.text((x+4,y+4),f"{t:.2f}s",fill="black")
    image.save(path)


def extract():
    frames=DEST/"frames";frames.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for source in sorted((ROOT/"reference videos/duo style").glob("*.mp4"),key=lambda p:int(p.stem.split("(")[1].split(")")[0])):
        data=probe(source);video=next(s for s in data["streams"] if s["codec_type"]=="video")
        duration=float(data["format"]["duration"]);ident=f"reference_{source.stem.split('(')[1].split(')')[0]}"
        folder=frames/ident;folder.mkdir(exist_ok=True)
        if not (folder/"frame_00001.jpg").exists():
            subprocess.run([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",str(source),"-vf","fps=2,scale=432:-2","-q:v","3",str(folder/"frame_%05d.jpg")],check=True,timeout=600)
        files=sorted(folder.glob("frame_*.jpg"));times=[index*.5 for index in range(len(files))]
        for page in range(0,len(files),64):
            sheet(files[page:page+64],times[page:page+64],folder/f"contact_{page//64+1:02d}.jpg")
        indices=sorted({round(index*(len(files)-1)/15) for index in range(16)})
        sheet([files[i] for i in indices],[times[i] for i in indices],frames/f"{ident}_overview.jpg",columns=8,thumb=(216,384))
        audio=folder/"audio.wav"
        if not audio.exists():
            subprocess.run([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",str(source),"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(audio)],check=True,timeout=120)
        inventory.append({"id":ident,"path":source.relative_to(ROOT).as_posix(),"sha256":file_hash(source),"duration":duration,"width":video["width"],"height":video["height"],"frame_rate":video["avg_frame_rate"],"sample_step":.5,"frame_count":len(files),"frames":folder.relative_to(ROOT).as_posix(),"overview":(frames/f"{ident}_overview.jpg").relative_to(ROOT).as_posix()})
        print(json.dumps(inventory[-1]),flush=True)
    atomic_write_json(DEST/"inventory.json",{"references":inventory,"method":"all nine supplied videos; decoded every 0.5 seconds, 432px-wide JPEG study copies; original hashes retained"})


if __name__=="__main__":
    extract()
