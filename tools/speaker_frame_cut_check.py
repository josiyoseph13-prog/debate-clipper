"""Camera-cut and off-screen checks with real imagery, deliberately joined shots."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.core.process import run_process
from dc.core.tools import require_tool
from dc.ingest import ingest
from dc.vision import analyze_window
from dc.speaker_frame import build_framing
from dc.renderer import make_render_plan,render
from tools.capture_fix3_frames import capture


def main():
    folder=ROOT/"reports/speaker_frame/camera_offscreen"
    folder.mkdir(parents=True,exist_ok=True)
    source=folder/"two_real_views.mkv"
    graph="[0:v]split[l][r];[l]trim=start=0:end=2,setpts=PTS-STARTPTS,crop=960:1080:0:0[left];[r]trim=start=2:end=4,setpts=PTS-STARTPTS,crop=960:1080:960:0[right];[left][right]concat=n=2:v=1:a=0[v]"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss","452.42","-i",ROOT/"input/yFFPgN_u6aY.mp4","-filter_complex",graph,"-map","[v]","-an","-c:v","ffv1",source],timeout=120)
    config=load_config();metadata=ingest(source,folder,rights_class="unknown",rights_note="Real local source imagery; deliberately constructed camera-cut test")
    metadata["sha256"]=metadata["fingerprint"]["sha256"]
    analysis=analyze_window(metadata,0,4,{"words":[]},config,folder/"tracking.json")
    spec={"enabled":True,"layout":"single","selected":"A","boxes":[{"id":"A","name":"Selected speaker","x":160,"y":100,"w":560,"h":850}]}
    framing=build_framing(spec,metadata,4,config,cuts=analysis.get("scene_cuts",[]))
    plan=make_render_plan(metadata,{"id":"c_sf_cut","start":0,"end":4},config,folder,headline="Camera change check")
    plan.update({"speaker_frame":spec,"framing":framing,"transcript":{"words":[]},"captions_ass":str(folder/"captions.ass"),"caption_plan":str(folder/"captions_plan.json")})
    render(plan,config,folder,folder/"camera_changed.mp4")
    capture(folder/"camera_changed.mp4",folder,"camera")
    absent={"enabled":True,"layout":"single","selected":"B","boxes":[{"id":"B","name":"Off-screen questioner","x":100,"y":100,"w":400,"h":800,"offscreen":True}]}
    off=build_framing(absent,metadata,2,config)
    plan["trim"]={"start":0,"end":2,"duration":2};plan.update({"speaker_frame":absent,"framing":off})
    render(plan,config,folder,folder/"offscreen_wide.mp4")
    capture(folder/"offscreen_wide.mp4",folder,"offscreen")
    result={"source":"input/yFFPgN_u6aY.mp4 at 452.42s; left view for 2s, then right view for 2s","scope":"Framing-only tests, no full caption/audio QA claim; cut timing deliberately constructed from real imagery","detected_cuts":analysis.get("scene_cuts",[]),"camera_warnings":framing["debug"]["warnings"],"offscreen_warnings":off["debug"]["warnings"],"camera_fallback":any(s["mode"]=="WIDE" and s["t0"]>=1.8 for s in framing["segments"]),"offscreen_fallback":all(s["mode"]=="WIDE" for s in off["segments"])}
    result["passed"]=result["camera_fallback"] and result["offscreen_fallback"]
    atomic_write_json(folder/"result.json",result);print(result)
    return 0 if result["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
