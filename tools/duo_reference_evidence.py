"""Small study sheets, local ASR, and decoded geometry; never person identity."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from dc.core.io import read_json,atomic_write_json
from dc.asr import transcribe_file


def main():
    inventory=read_json(ROOT/"reports/duo_style/inventory.json")["references"]
    seen=set()
    for ref in inventory:
        if ref["sha256"] in seen:continue
        seen.add(ref["sha256"])
        folder=ROOT/ref["frames"]
        files=sorted(folder.glob("frame_*.jpg"))
        for start in range(0,len(files),64):
            subset=files[start:start+64]
            image=Image.new("RGB",(8*108,((len(subset)+7)//8)*132),"white")
            draw=ImageDraw.Draw(image)
            for i,file in enumerate(subset):
                # All supplied edits use a central square window at these rows.
                tile=Image.open(file).convert("RGB").crop((0,215,432,660)).resize((108,112))
                x=(i%8)*108;y=(i//8)*132
                image.paste(tile,(x,y+20));draw.text((x+3,y+2),f"{(start+i)*.5:.1f}s",fill="black")
            image.save(folder/f"compact_{start//64+1:02d}.jpg")
        if "--asr" in sys.argv:
            output=folder/"transcript.json"
            if not output.exists():
                transcribe_file(ROOT/ref["path"],output,"whisper_base",no_network=True,glossary={"terms":[],"aliases":{}})
            data=read_json(output)
            print(json.dumps({"id":ref["id"],"segments":[{k:r[k] for k in ("start","end","text")} for r in data["segments"]],"accuracy":"Not measured"}),flush=True)


if __name__=="__main__":main()
