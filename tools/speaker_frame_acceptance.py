"""Real-source Speaker Frame exports and before/after evidence; no fake turns."""
from __future__ import annotations
import copy
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from argparse import Namespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from dc.core.config import load_config
from dc.core.io import read_json,atomic_write_json,atomic_copy
from dc.core.decisions import record_decision
from dc.core.hashing import file_hash
from dc.cli import command_render
from dc.studio.server import create_app
from fastapi.testclient import TestClient
from tools.capture_fix3_frames import capture


def main():
    folder=ROOT/"reports/speaker_frame"
    folder.mkdir(parents=True,exist_ok=True)
    job=ROOT/"work/job_speaker_frame_acceptance"
    job.mkdir(parents=True,exist_ok=True)
    original=ROOT/"work/job_863e97df620d"
    source=read_json(original/"source.json")
    source["path"]=str(ROOT/"input/yFFPgN_u6aY.mp4")
    atomic_write_json(job/"source.json",source)
    for name in ("transcript.json","turns.json","shots.json"):
        atomic_copy(original/name,job/name)
    atomic_write_json(job/"job_config.json",{"preset":"political_lens","config":load_config().json()})
    base=next(row for row in read_json(original/"candidates.json")["candidates"] if row["id"]=="c_8d2ea1dcd350")
    layouts=sys.argv[1:] or ["single","stacked","blended","auto"]
    candidates=[{**copy.deepcopy(base),"id":f"c_sf_{layout}"} for layout in ["single","stacked","blended","auto"]]
    atomic_write_json(job/"candidates.json",{"schema_version":5,"candidates":candidates})
    boxes=[{"id":"A","name":"Answering speaker","x":160,"y":100,"w":560,"h":850},{"id":"B","name":"Questioner","x":1140,"y":100,"w":560,"h":850}]
    previous=read_json(folder/"acceptance.json",{}) or {}
    results=[r for r in previous.get("results",[]) if r["layout"] not in layouts]
    for layout in layouts:
        candidate=f"c_sf_{layout}"
        spec={"enabled":True,"layout":layout,"selected":"B" if layout=="single" else "A","boxes":boxes,"blend":{"width":.12,"position":.5,"direction":"horizontal","swap":False},"voice_map":{},"overrides":[],"shots":[],"frame_t":0}
        record_decision(ROOT,{"schema_version":5,"time":datetime.now(timezone.utc).isoformat(),"job_id":job.name,"candidate_id":candidate,"action":"save","speaker_frame":spec})
        code=command_render(Namespace(job=job.name,candidate=candidate,headline=None,layout="auto",variants=1,preset="political_lens",crop=None,debug_overlay=False,accept_review=True))
        report=read_json(job/"export_report.json")
        plan=read_json(job/"render_plan.json")
        stage=folder/("blend" if layout=="blended" else layout)
        stage.mkdir(parents=True,exist_ok=True)
        atomic_write_json(stage/"export_report.json",report)
        atomic_write_json(stage/"render_plan.json",plan)
        output=stage/f"speaker_frame_{layout}.mp4"
        atomic_copy(job/f"{candidate}.mp4",output)
        before=capture(Path(source["path"]),stage/"before","source",start=base["start"],clip_duration=base["duration"])
        after=capture(output,stage/"after",layout)
        sheet=Image.new("RGB",(1080,6*690),"white");draw=ImageDraw.Draw(sheet)
        for index,(a,b) in enumerate(zip(before,after)):
            for col,(label,path) in enumerate((("Source",a),(layout,b))):
                image=Image.open(path).convert("RGB");image.thumbnail((540,640));sheet.paste(image,(col*540,index*690+30));draw.text((col*540+8,index*690+8),f"{label} sample {index+1}",fill="black")
        sheet.save(stage/"before_after.png")
        sf=next((row for row in report["checks"] if row["name"]=="speaker_frame"),None)
        results.append({"layout":layout,"returncode":code,"status":report["status"],"output":str(output.relative_to(ROOT)),"sha256":file_hash(output),"export":report.get("export"),"speaker_frame":sf,"real_voice_turns":"Not measured; pipeline voice labels are unknown. Auto shows both and warns; no fabricated voice mapping used."})
    app,token=create_app();client=TestClient(app,base_url="http://127.0.0.1")
    response=client.post("/api/speaker-frame/open",json={"job_id":job.name,"candidate_id":"c_sf_stacked"},headers={"Origin":"http://127.0.0.1","X-DC-Token":token})
    if response.status_code!=200:
        raise RuntimeError(f"Editor open failed: {response.text}")
    atomic_write_json(folder/"editor_seed.json",response.json())
    atomic_write_json(folder/"acceptance.json",{"schema_version":5,"job_id":job.name,"source":"input/yFFPgN_u6aY.mp4","source_range":[base["start"],base["end"]],"results":results,"editor_open_status":response.status_code})
    print(json.dumps({"results":[{"layout":r["layout"],"status":r["status"],"output":r["output"],"speaker_frame":r["speaker_frame"]} for r in results],"editor_open_status":response.status_code},indent=2))
    return 0 if all(r["returncode"]==0 for r in results) else 1


if __name__=="__main__":
    raise SystemExit(main())
