"""Independent framing-only check using a different supplied reference video."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.audio import rms_windows,energy_activity
from dc.core.config import load_config
from dc.core.hashing import file_hash
from dc.core.io import atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.ingest import ingest,ffprobe
from dc.framing import framing_quality
from dc.renderer import make_render_plan,render
from dc.vision import analyze_window,directed_framing,caption_exclusions,measure_rendered_faces
from tools.capture_fix3_frames import capture
from tools.measure_supplied_style import frame_metrics


def main():
    original=ROOT/"reference videos/political lens87.mp4"
    folder=ROOT/"reports/fix3/different_video"
    folder.mkdir(parents=True,exist_ok=True)
    reference_frames=capture(original,folder,"reference",clip_duration=12)
    metrics=frame_metrics(reference_frames[0])
    top,bottom=metrics["feed_top_row_estimate"],metrics["bottom_white_row_estimate"]
    if top is None or bottom is None:
        raise ValueError("Could not measure reference video-window bounds")
    width=metrics["size"][0]
    height=(bottom-top)//2*2
    source_path=folder/"reference_video_window.mkv"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",original,"-t","12","-vf",f"crop={width}:{height}:0:{top}","-c:v","ffv1","-c:a","pcm_s16le",source_path],timeout=120)
    source=ingest(source_path,folder,rights_class="unknown",rights_note="Supplied reference used for local framing verification; rights not verified")
    config=load_config()
    source["sha256"]=source["fingerprint"]["sha256"]
    analysis=analyze_window(source,0,12,{"words":[]},config,folder/"tracking.json")
    wav=folder/"audio_activity.wav"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",source_path,"-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",wav],timeout=60)
    activity=energy_activity(rms_windows(wav))
    for row in analysis["observations"]:
        row["speech"]=any(span["start"]<=row["t"]<=span["end"] for span in activity["active_spans"])
    analysis["audio_evidence"]={"engine":"rms_activity","speech_verified":False,"note":"Energy activity is not diarization or a labeled speech-accuracy check"}
    directed=directed_framing(analysis,source,12,config,{})
    if directed is None:
        raise ValueError("No unambiguous moving-mouth evidence in the other video")
    plan=make_render_plan(source,{"id":"c_task1_other","start":0,"end":12},config,folder,headline="Different-video framing check")
    plan.update({"framing":directed,"transcript":{"words":[]},"captions_ass":str(folder/"captions.ass"),"caption_plan":str(folder/"captions_plan.json"),"chrome_png":str(folder/"chrome.png"),"face_observations":[{"t":row["t"],"track":row["track"],"source_box":row["source_box"]} for row in analysis["observations"]],"caption_exclusions":caption_exclusions(analysis,source,config,directed)})
    output=folder/"different_video_framing.mp4"
    render(plan,config,folder,output)
    measured=measure_rendered_faces(output,plan,config)
    quality=framing_quality(plan)
    frames=capture(output,folder,"after")
    passed=quality["passed"] and measured["face_in_safe_area"]["inside"]==measured["face_in_safe_area"]["samples"]
    result={"input":str(original.relative_to(ROOT)),"input_sha256":file_hash(original),"extraction_box":[0,top,width,height],"output":str(output.relative_to(ROOT)),"output_sha256":file_hash(output),"scope":"Framing-only render of measured video window from a different finished reference; original burned captions retained. Full raw-source/caption QA not claimed.","audio_activity":activity,"face_measurements":measured,"camera":quality,"probe":ffprobe(output),"frames":[str(p.relative_to(ROOT)) for p in frames],"passed":passed}
    atomic_write_json(folder/"result.json",result)
    print(json.dumps({key:result[key] for key in ("input","output","scope","face_measurements","camera","passed")},indent=2))
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())
