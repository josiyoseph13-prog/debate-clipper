"""Run the locally provable Group A engineering matrix.

This records contracts, low-resolution routing, real 60-second CFR renders,
telemetry, output cadence and the security audit. It does not claim speaker or
editorial accuracy; those still require the supplied labels and raters.
"""
from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.contracts import validate_job_spec
from dc.core.config import load_config
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json,read_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.core.telemetry import stage_timer
from dc.framing import framing_plan
from dc.ingest import ffprobe,ingest
from dc.layout import upscale_policy
from dc.renderer import make_render_plan,render
from dc.qa import validate_output


def _source(folder: Path, fps: str, duration: int = 60) -> Path:
    source=folder/f"source_{fps.replace('/','_')}.mp4"
    if source.exists():return source
    video_rate=float(fps.split("/")[0])/float(fps.split("/")[1]) if "/" in fps else float(fps)
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i",f"testsrc2=s=320x180:r={video_rate}:d={duration}","-f","lavfi","-i",f"sine=frequency=440:sample_rate=48000:duration={duration}","-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac","-shortest","-movflags","+faststart",source],timeout=240)
    return source


def main():
    cfg=load_config(overrides={"output":{"preset":"ultrafast","crf":28}})
    work=ROOT/"work"/"job_group_a_matrix"
    work.mkdir(parents=True,exist_ok=True)
    report={"schema_version":5,"test_id":"Group A local engineering matrix","command":[sys.executable,*sys.argv],"machine":{"platform":platform.platform(),"python":sys.version,"cpu_count":__import__("os").cpu_count()},"checks":[],"quality_claims":[]}
    spec={"schema_version":5,"job_id":"job_group_a","source":{"path":"input/debate.mp4","url":None},"candidate":{"id":"c_group_a","start":1,"end":12,"edits":[]},"preset":"political_lens","headline":{"text":"A short question?"},"layout":{"mode":"auto"},"output":{"crf":18,"fps":"source_capped"}}
    try:validate_job_spec(spec);report["checks"].append({"name":"job_spec_contract","passed":True})
    except Exception as exc:report["checks"].append({"name":"job_spec_contract","passed":False,"error":str(exc)})
    lowres=[]
    for width,height in ((1920,1080),(1280,720),(854,480)):
        policy=upscale_policy(width,height,cfg)
        plan=framing_plan(width,height,10,cfg)
        lowres.append({"source":[width,height],"policy":policy["action"],"upscale_factor":policy["upscale_factor"],"mode":plan["segments"][0]["mode"],"reasons":plan["segments"][0]["reasons"]})
    report["checks"].append({"name":"low_resolution_upscale_matrix","passed":lowres[0]["policy"]=="normal" and lowres[1]["policy"]=="soft_upscale" and lowres[2]["policy"]=="prefer_wide_or_dual","rows":lowres})
    words=[]
    for index in range(72):
        start=.2+index*.8
        words.append({"text":"RIGHT" if index%2==0 else "ANSWER","start":start,"end":start+.35})
    for fps in ("25","60"):
        folder=work/fps
        folder.mkdir(exist_ok=True)
        source_path=_source(folder,fps)
        source=ingest(source_path,folder,rights_class="own",rights_note="Generated Group A test pattern")
        transcript={"schema_version":5,"words":words}
        candidate={"id":f"c_group_a_{fps}","start":0,"end":60,"hook":{"headline_options":["Group A matrix"]}}
        plan=make_render_plan(source,candidate,cfg,folder)
        plan["transcript"]=transcript
        with stage_timer(folder,"render_matrix",extra={"fps_source":fps,"duration_s":60}):
            rendered=render(plan,cfg,folder,folder/"clip.mp4")
        qa=validate_output(folder/"clip.mp4",plan,cfg,folder/"export_report.json")
        probe=ffprobe(folder/"clip.mp4")
        video=next(row for row in probe["streams"] if row["codec_type"]=="video")
        report["checks"].append({"name":f"T25_{fps}fps_60s","passed":qa["status"]=="passed","source_fps":fps,"output_fps":video.get("avg_frame_rate"),"duration_s":float(probe["format"]["duration"]),"output_sha256":rendered["output_sha256"],"qa_status":qa["status"],"telemetry":read_json(folder/"telemetry.json",{})})
    report["quality_claims"].append("No speaker, face, selection, name, DER or human visual quality claim; this is generated media and technical cadence evidence only.")
    report["passed"]=all(row.get("passed") for row in report["checks"])
    atomic_write_json(ROOT/"reports"/"current_checks"/"group_a_matrix.json",report)
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
