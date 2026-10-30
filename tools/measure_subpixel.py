"""T-24: measure decoded lossless camera motion against integer cropping."""
from pathlib import Path
import sys
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import atomic_write_json
from dc.core.process import run_process,transform_video_stream
from dc.core.tools import require_tool
from dc.renderer import render_subpixel_feed


def main():
    config=load_config()
    work=ROOT/"work"/"job_subpixel_acceptance"
    work.mkdir(parents=True,exist_ok=True)
    width,height=config.regions["feed"]["w"]+150,config.regions["feed"]["h"]
    rng=np.random.default_rng(17)
    coarse=rng.integers(0,2,(height//8+1,width//8+1),dtype=np.uint8)*255
    texture=cv2.resize(coarse,(width,height),interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(work/"texture.png"),texture)
    source=work/"source.mkv"
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-loop","1","-framerate","25","-i","texture.png","-t","2","-c:v","ffv1",source.name],cwd=work,timeout=60)
    fw,fh=config.regions["feed"]["w"],config.regions["feed"]["h"]
    rect={"x":40,"y":0,"w":fw,"h":fh}
    plan={"source":{"path":str(source),"width":width,"height":height},"trim":{"start":0,"end":2,"duration":2},"frame_rate":{"target_cfr":25},"framing":{"segments":[{"t0":0,"t1":2,"mode":"SINGLE","regions":[rect]}],"path":[{"t":0,**rect},{"t":2,**rect,"x":55}]},"plan_hash":"synthetic_t24"}
    moving=work/"subpixel.mkv"
    render_subpixel_feed(source,plan,config,moving)
    integer=work/"integer.mkv"
    decode=[require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-i",source.name,"-an","-pix_fmt","bgr24","-f","rawvideo","pipe:1"]
    encode=[require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pixel_format","bgr24","-video_size",f"{fw}x{fh}","-framerate","25","-i","pipe:0","-c:v","ffv1","-pix_fmt","bgr0",integer.name]
    def crop(raw,index):
        frame=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3)
        left=int(40+index*.3)
        return frame[:,left:left+fw].tobytes()
    transform_video_stream(decode,encode,width*height*3,crop,work,60)
    measurements={}
    for name,path in (("subpixel",moving),("integer",integer)):
        capture=cv2.VideoCapture(str(path))
        previous=None
        shifts=[]
        window=cv2.createHanningWindow((512,512),cv2.CV_64F)
        while True:
            ok,frame=capture.read()
            if not ok:break
            patch=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)[300:812,200:712].astype(np.float64)
            if previous is not None:
                displacement,response=cv2.phaseCorrelate(previous.copy(),patch.copy(),window)
                shifts.append({"dx":displacement[0],"dy":displacement[1],"response":response})
            previous=patch
        capture.release()
        measurements[name]={"frames":len(shifts)+1,"jitter_std_px":float(np.std([row["dx"] for row in shifts])),"mean_displacement_px":float(np.mean([row["dx"] for row in shifts])),"samples":shifts}
    actual,baseline=measurements["subpixel"]["jitter_std_px"],measurements["integer"]["jitter_std_px"]
    report={"schema_version":5,"test_id":"T-24","command":"python tools/measure_subpixel.py","source":"deterministic synthetic high-contrast texture","planned_pan_px_per_frame":.3,"method":"phase correlation on decoded FFV1 frames","measurements":measurements,"thresholds":{"max_absolute_jitter_px":.15,"max_baseline_fraction":.5},"passed":actual<=.15 and actual<=baseline*.5}
    atomic_write_json(ROOT/"reports"/"verification_v5"/"subpixel.json",report)
    print({"passed":report["passed"],"subpixel_jitter":actual,"integer_jitter":baseline})
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
