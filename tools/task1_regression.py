"""Replay a saved pre-Task-1 export and compare decoded stream hashes."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import AppConfig
from dc.core.hashing import file_hash
from dc.core.io import read_json,atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.renderer import render


def main():
    baseline=ROOT/"exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_02_but-my-question-is-how-can-christian-teaching-on-love_3m10s-3m38s_c_3b29c90cfa17_a17ccb77"
    original=next(baseline.glob("02_*.mp4"))
    config=AppConfig(read_json(baseline/"renderer_config.json")["config"])
    plan=copy.deepcopy(read_json(baseline/"render_plan.json"))
    # Export bundles deliberately omit the full transcript. Replay with the
    # original job transcript; otherwise the renderer receives no caption words.
    plan["transcript"]=read_json(ROOT/"work/job_863e97df620d/transcript.json")
    destination=ROOT/"reports/fix3/regression"
    destination.mkdir(parents=True,exist_ok=True)
    for key,name in (("captions_ass","captions.ass"),("caption_plan","captions_plan.json"),("chrome_png","chrome.png"),("craft_png","craft.png"),("extras_png","extras.png")):
        plan[key]=str(destination/name)
    output=destination/"unchanged_preset.mp4"
    render(plan,config,destination,output)
    def stream_hash(video,stream):
        text=run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-i",video,"-map",stream,"-f","framemd5","-"],timeout=120,output_limit=4000000)
        rows="\n".join(line for line in text.splitlines() if not line.startswith("#"))
        return hashlib.sha256(rows.encode()).hexdigest()
    result={"baseline":str(original.relative_to(ROOT)),"replay":str(output.relative_to(ROOT)),"baseline_file_sha256":file_hash(original),"replay_file_sha256":file_hash(output),"feature_disabled":config.get("framing","face_landmarker") is None,"streams":{}}
    for stream in ("0:v:0","0:a:0"):
        a,b=stream_hash(original,stream),stream_hash(output,stream)
        result["streams"][stream]={"baseline_sha256":a,"replay_sha256":b,"identical":a==b}
    result["passed"]=result["feature_disabled"] and all(row["identical"] for row in result["streams"].values())
    atomic_write_json(destination/"result.json",result)
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
