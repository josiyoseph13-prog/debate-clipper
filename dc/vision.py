"""Approved-window vision and a conservative, inspectable camera director."""
from __future__ import annotations
import math
from pathlib import Path
from .core.hashing import content_hash
from .core.io import atomic_write_json, read_json


def haar_detector():
    import cv2
    if not hasattr(cv2,"CascadeClassifier") or not hasattr(cv2,"data"):
        return None
    model = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not model.is_file():
        return None
    detector = cv2.CascadeClassifier(str(model))
    return detector if not detector.empty() else None


def classify_frame(frame) -> dict:
    import cv2
    import numpy as np
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    detector = haar_detector()
    faces = detector.detectMultiScale(gray, 1.1, 5, minSize=(24,24)) if detector else []
    central = np.abs(gray[:,width//2-1].astype(float)-gray[:,width//2+1].astype(float)).mean()
    horizontal = np.abs(gray[height//2-1,:].astype(float)-gray[height//2+1,:].astype(float)).mean()
    label, confidence = ("side-by-side",.6) if len(faces)>=2 and central>30 else ("split",.6) if len(faces)>=2 and horizontal>30 else ("single",.55) if len(faces)==1 else ("graphic",.35) if not len(faces) and cv2.Canny(gray,80,160).mean()>45 else ("unknown",0.0)
    text_density = float(np.mean(cv2.Canny(gray[int(height*.7):int(height*.95)],80,160)>0))
    return {"layout":label,"confidence":confidence,"faces":[list(map(int,row)) for row in faces],"source_has_captions":text_density>.18,"text_band":[0,.7,1,.25] if text_density>.18 else None,"engine":"haar-and-edge-heuristic","validated_accuracy":False}


def classify_shots(source: Path, shots: list[dict]) -> list[dict]:
    from .core.process import check_cancelled
    try:
        import cv2
        capture = cv2.VideoCapture(str(source))
        result = []
        for shot in shots:
            check_cancelled()
            capture.set(cv2.CAP_PROP_POS_MSEC,(shot["start"]+shot["end"])*500)
            ok,image = capture.read()
            if ok:
                image = cv2.resize(image,(320,max(2,round(image.shape[0]*320/image.shape[1]))))
                result.append({**shot,**classify_frame(image),"reason":"Measured representative frame; heuristic label"})
            else:
                result.append(shot)
        capture.release()
        return result
    except ImportError:
        return shots


class Director:
    def __init__(self, config):
        self.config = config
        self.mode,self.track,self.since,self.pending,self.pending_since = "WIDE",None,0,None,0

    def update(self,t:float,probabilities:dict,crosstalk:float=0,feasible:bool=True,cut:bool=False):
        if cut:
            self.mode,self.track,self.since = "WIDE",None,t
        ranking = sorted(probabilities.items(),key=lambda item:item[1],reverse=True)
        margin = ranking[0][1]-ranking[1][1] if len(ranking)>1 else (ranking[0][1] if ranking else 0)
        desired = ("SINGLE",ranking[0][0]) if ranking and margin>=.3 and feasible else ("WIDE",None)
        if crosstalk>=self.config.get("framing","crosstalk_on",default=.6) and len(ranking)>=2 and feasible:
            desired=("DUAL",None)
        if desired!=self.pending:
            self.pending,self.pending_since=desired,t
        hold=1.0 if self.mode=="WIDE" else self.config.get("framing","switch_hold_s",default=.6)
        dwell=self.config.get("framing","dual_min_dwell_s",default=3) if self.mode=="DUAL" else self.config.get("framing","min_dwell_s",default=1.5)
        if t-self.pending_since>=hold and t-self.since>=dwell and desired!=(self.mode,self.track):
            self.mode,self.track=desired
            self.since=t
        return {"mode":self.mode,"track":self.track,"margin":margin}


def directed_framing(analysis:dict,source:dict,duration:float,config,gate:dict)->dict|None:
    """Use a measured gate when available, otherwise a clearly marked local fallback."""
    # APEX (2026-10-15): LR-ASD evidence, balanced config, flag-gated. Any
    # failure or a no-SINGLE outcome falls through to the pre-ASD behaviour.
    try:
        from . import asd as _asd
        if _asd.enabled(config) and isinstance(analysis, dict) and analysis.get("asd"):
            _plan = _asd.build_plan(analysis["asd"], analysis.get("observations", []), source, duration, config)
            if _plan is not None:
                return _plan
    except Exception:
        pass
    if not gate.get("enabled") or gate.get("wrong_speaker_fraction",1)>.15 or gate.get("face_safe_fraction",0)<.98:
        return _unverified_face_fallback(analysis, source, duration, config, gate)
    import numpy as np
    from .layout import crop_rect
    from .framing import smooth_path
    tracks=analysis.get("correlations",{})
    if not tracks or max(tracks.values())<.2: return None
    values=np.array(list(tracks.values()),dtype=float)
    scores=2*(values-values.mean())/max(1e-6,values.std())
    weights=np.exp(scores-scores.max())
    probabilities=dict(zip(tracks,(weights/weights.sum()).tolist()))
    director=Director(config)
    path,segments=[],[]
    for index in range(int(duration*6)+1):
        t=min(duration,index/6)
        state=director.update(t,probabilities)
        observations=[row for row in analysis.get("observations",[]) if abs(row["t"]-t)<.3 and row["track"]==state["track"]]
        if state["mode"]=="SINGLE" and observations:
            face=observations[-1]["source_box"]
            desired_h=min(source["height"],max(config.regions["feed"]["h"]/config.get("framing","s_max",default=1.5),face[3]/config.get("framing","phi_target",default=.2)))
            zoom=source["height"]/desired_h
            rect=crop_rect(source["width"],source["height"],config,face[0]+face[2]/2,face[1]+face[3]/2+(0.5-config.get("framing","head_y_frac",default=.33))*desired_h,zoom)
            mode="SINGLE"
        else:
            rect=crop_rect(source["width"],source["height"],config)
            mode="WIDE"
        if not segments or segments[-1]["mode"]!=mode:
            if segments:segments[-1]["t1"]=t
            segments.append({"t0":t,"t1":duration,"mode":mode,"regions":[rect],"confidence":max(probabilities.values()),"reasons":["GATED_AV_CORRELATION"]})
        path.append({"t":t,**rect})
    from .framing import rate_limit_path
    cut_times=[segment["t0"] for segment in segments]
    return {"schema_version":5,"segments":segments,"path":rate_limit_path(smooth_path(path,config.get("framing","tau_follow",default=.35)),cut_times,source["width"],source["height"]),"debug":{"gate":gate,"probabilities":probabilities,"exclusion_level":"face"}}


def _unverified_face_fallback(analysis:dict, source:dict, duration:float, config, gate:dict):
    """Follow a clearly moving mouth during speech; abstain on ambiguous faces.

    This is local evidence, not a labeled active-speaker accuracy claim.
    """
    import numpy as np
    from .framing import smooth_path
    observations = analysis.get("observations", []) or []
    if not observations or analysis.get("engine") != "mediapipe_landmarks":
        return None
    from .layout import crop_rect
    feed = config.regions["feed"]
    tracks = {str(row["track"]) for row in observations}
    path, segments, evidence = [], [], []
    selected, pending, pending_since, since, last_evidence = None, None, 0.0, 0.0, -10.0
    scene_start=0.0
    for index in range(int(duration * 6) + 1):
        t = min(duration, index / 6)
        current_scene=max([0.0]+[cut for cut in analysis.get("scene_cuts",[]) if cut<=t])
        new_scene=current_scene!=scene_start
        if new_scene:
            selected,pending,since,last_evidence=None,None,t,-10.0
            scene_start=current_scene
        next_scene=min([duration]+[cut for cut in analysis.get("scene_cuts",[]) if cut>t])
        scores=[]
        for track in tracks:
            local=[row for row in observations if str(row["track"])==track and scene_start<=row["t"]<next_scene and abs(row["t"]-t)<=1.5 and row.get("mouth") is not None and row["source_box"][3]>=config.get("framing","min_face_px",default=48)]
            available=min(next_scene,t+1.5)-max(scene_start,t-1.5)
            if len(local)<max(6,available*analysis.get("landmark_fps",15)*.65):
                continue
            if not any(row.get("speech",True) for row in local):
                continue
            scores.append((track,float(np.std([row["mouth"] for row in local]))))
        scores.sort(key=lambda item:item[1],reverse=True)
        desired=scores[0][0] if scores and scores[0][1]>=.012 and (len(scores)==1 or scores[0][1]>=max(.008,scores[1][1])*2) else None
        if desired is not None:
            last_evidence=t
        if desired!=pending:
            pending,pending_since=desired,t
        if index==0 or new_scene or (desired is not None and t-pending_since>=config.get("framing","switch_hold_s",default=.6) and t-since>=config.get("framing","min_dwell_s",default=1.5)):
            if selected!=desired:
                selected,since=desired,t
        if desired is None and t-last_evidence>3.0:
            selected=None
        rows=[row for row in observations if str(row["track"])==selected]
        row=min(rows,key=lambda item:abs(item["t"]-t)) if rows else None
        if row is None or abs(row["t"]-t)>1.5:
            rect = crop_rect(source["width"], source["height"], config)
            mode = "WIDE"
        else:
            x, y, w, h = [float(value) for value in row["source_box"]]
            desired_h = min(source["height"], max(feed["h"] / config.get("framing", "s_max", default=1.5), h / config.get("framing", "phi_target", default=.2)))
            zoom = source["height"] / desired_h
            rect = crop_rect(source["width"], source["height"], config, x + w / 2, y + h / 2 + (0.5 - config.get("framing", "head_y_frac", default=.33)) * desired_h, zoom)
            mode = "SINGLE"
        if not segments or (segments[-1]["mode"],segments[-1].get("track")) != (mode,selected):
            if segments:
                segments[-1]["t1"] = t
            segments.append({"t0": t, "t1": duration, "mode": mode, "track":selected,"regions": [rect], "confidence": 0.5 if mode=="SINGLE" else 0.0, "reasons": ["LOCAL_MOUTH_MOTION" if mode=="SINGLE" else "AMBIGUOUS_SPEAKER"]})
        evidence.append({"t":t,"track":selected,"mouth_motion":dict(scores),"active_speaker_accuracy":"Not measured"})
        path.append({"t": t, **rect})
    if not any(segment["mode"]=="SINGLE" for segment in segments):
        return None
    # Hard cuts between subjects avoid panning across a bodyguard/crowd.
    # Within a shot, retain a calm, speed-limited subpixel camera path.
    smoothed=[]
    for segment in segments:
        points=[point for point in path if segment["t0"]<=point["t"]<segment["t1"]]
        if not points:
            continue
        part=smooth_path(points,config.get("framing","tau_slow",default=.8))
        for left,right in zip(part,part[1:]):
            dt=right["t"]-left["t"]
            old_h=left["h"]
            right["h"]=min(old_h*(1+.18*dt),max(old_h*(1-.18*dt),right["h"]))
            right["w"]=right["h"]*feed["w"]/feed["h"]
            for key,limit in (("x",source["width"]-right["w"]),("y",source["height"]-right["h"])):
                right[key]=min(limit,max(0,min(left[key]+180*dt,max(left[key]-180*dt,right[key]))))
        if smoothed:
            smoothed.append({**smoothed[-1],"t":segment["t0"]})
        smoothed.extend(part)
        segment["regions"]=[{key:value for key,value in part[0].items() if key!="t"}]
    smoothed.append({**smoothed[-1],"t":duration})
    from .framing import rate_limit_path
    smoothed = rate_limit_path(smoothed, (), source["width"], source["height"])
    return {"schema_version": 5, "segments": segments, "path": smoothed, "debug": {"gate": gate,"fallback": "local_mouth_motion", "active_speaker_accuracy": "Not measured", "evidence":evidence}}


def analyze_window(source:dict,start:float,end:float,transcript:dict,config,output:Path)->dict:
    import cv2
    key=content_hash({"source":source.get("sha256"),"start":start,"end":end,"config":config.get("framing"),"transcript":content_hash(transcript),"opencv":cv2.__version__,"haar_available":haar_detector() is not None,"version":5})
    cached=read_json(output,{}) or {}
    if cached.get("cache_key")==key:
        return cached
    import cv2
    import numpy as np
    from .captions import transcript_words
    landmarks=None
    model_name=config.get("framing","face_landmarker")
    if model_name:
        import mediapipe as mp
        from .models import model_spec
        spec=model_spec(model_name)
        landmarks=mp.tasks.vision.FaceLandmarker.create_from_options(mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(spec["paths"]["model"])),num_faces=4,output_face_blendshapes=True))
    fps=config.get("framing","landmark_fps",default=15) if landmarks else config.get("framing","analysis_fps",default=6)
    capture=cv2.VideoCapture(source["path"])
    proxy_w=int(config.get("framing","proxy_width",default=640))
    # Decode the approved window once. Repeated timestamp seeks in VP9 sources
    # can re-decode the same GOP hundreds of times and dominate analysis time.
    import tempfile
    from .core.process import check_cancelled, run_process
    from .core.tools import require_tool
    proxy=tempfile.TemporaryDirectory(prefix="tracking_proxy_",dir=output.parent)
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(start),"-i",source["path"],"-t",str(end-start),"-an","-vf",f"fps={fps},scale={proxy_w}:-2","-q:v","3",str(Path(proxy.name)/"%06d.jpg")],timeout=max(120,(end-start)*5))
    proxy_frames=sorted(Path(proxy.name).glob("*.jpg"))
    words=transcript_words(transcript)
    tracks,observations,next_id={},[],0
    scene_cuts,previous_image=[],None
    detector=haar_detector()
    for index in range(math.ceil((end-start)*fps)):
        check_cancelled()
        t=index/fps
        if index>=len(proxy_frames):
            break
        frame=cv2.imread(str(proxy_frames[index]))
        if frame is None: break
        thumbnail=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(64,36)).astype(float)/255
        if previous_image is not None and np.mean(np.abs(thumbnail-previous_image))>.22:
            scene_cuts.append(t)
            for track in tracks:
                tracks[track][-1]["ended_at_cut"]=True
        previous_image=thumbnail
        boxes,mouths=[],[]
        if landmarks:
            import mediapipe as mp
            # A full-frame pass misses the smaller questioner in source split
            # screens. Overlapping half-frame passes retain source coordinates.
            tiles=[(0,frame.shape[1],0,frame.shape[0])]
            if source["width"] / source["height"] > 1.4:
                tiles.extend([(0,round(frame.shape[1]*.55),0,frame.shape[0]),(round(frame.shape[1]*.45),frame.shape[1],0,frame.shape[0])])
            elif source["height"] > source["width"]:
                # Portrait sources get the same treatment on the other axis:
                # overlapping horizontal bands, because a full-frame portrait
                # pass misses faces that fill too little of the tall frame.
                tiles.extend([(0,frame.shape[1],0,round(frame.shape[0]*.55)),(0,frame.shape[1],round(frame.shape[0]*.45),frame.shape[0])])
            for left,right,top,bottom in tiles:
                tile=frame[top:bottom,left:right]
                detected=landmarks.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(cv2.cvtColor(tile,cv2.COLOR_BGR2RGB))))
                for face,shapes in zip(detected.face_landmarks,detected.face_blendshapes):
                    xs,ys=[point.x for point in face],[point.y for point in face]
                    box=[left+min(xs)*tile.shape[1],top+min(ys)*tile.shape[0],(max(xs)-min(xs))*tile.shape[1],(max(ys)-min(ys))*tile.shape[0]]
                    if any(abs(box[0]+box[2]/2-prior[0]-prior[2]/2)<min(box[2],prior[2])*.5 and abs(box[1]+box[3]/2-prior[1]-prior[3]/2)<min(box[3],prior[3])*.5 for prior in boxes):
                        continue
                    boxes.append(box)
                    mouths.append(next((row.score for row in shapes if row.category_name=="jawOpen"),0))
        else:
            boxes=detector.detectMultiScale(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),1.1,5,minSize=(24,24)) if detector else []
            mouths=[None]*len(boxes)
        active_ids=set()
        for box,mouth in zip(boxes,mouths):
            x,y,w,h=map(float,box)
            nearest=min((track for track in tracks if track not in active_ids and not tracks[track][-1].get("ended_at_cut") and t-tracks[track][-1]["t"]<1),key=lambda track:abs(tracks[track][-1]["x"]-x)+abs(tracks[track][-1]["y"]-y),default=None)
            if nearest is None or abs(tracks[nearest][-1]["x"]-x)>proxy_w*.2:
                nearest=str(next_id)
                next_id+=1
                tracks[nearest]=[]
            scale=source["width"]/proxy_w
            row={"t":t,"track":nearest,"x":x,"y":y,"w":w,"h":h,"mouth":mouth,"speech":any(word["start"]-.05<=start+t<=word["end"]+.05 for word in words),"source_box":[x*scale,y*scale,w*scale,h*scale]}
            tracks[nearest].append(row)
            observations.append(row)
            active_ids.add(nearest)
    capture.release()
    proxy.cleanup()
    if landmarks:
        landmarks.close()
    correlations={}
    for track,rows in tracks.items():
        valid=[row for row in rows if row["mouth"] is not None and row["source_box"][3]>=config.get("framing","min_face_px",default=48)]
        if len(valid)<45:
            continue
        energy=np.array([np.std([prior["mouth"] for prior in valid if row["t"]-.8<=prior["t"]<=row["t"]]) for row in valid])
        speech=np.array([float(any(word["start"]-.05<=start+row["t"]<=word["end"]+.05 for word in words)) for row in valid])
        if np.std(energy) and np.std(speech):
            correlations[track]=float(np.corrcoef(energy,speech)[0,1])
    # APEX (2026-10-15): optional LR-ASD scoring (flag-gated, never raises).
    asd_payload, asd_reason = None, None
    try:
        from . import asd as _asd
        _audio = output.parent / "audio_16k.wav"
        asd_payload, asd_reason = _asd.score_window(source, start, end - start, observations, config, output.parent, _audio if _audio.is_file() else None)
    except Exception as _exc:
        asd_reason = f"{type(_exc).__name__}: {_exc}"
    result={"schema_version":5,"cache_key":key,"observations":observations,"tracks":{key:len(value) for key,value in tracks.items()},"correlations":correlations,"scene_cuts":scene_cuts,"engine":"mediapipe_landmarks" if landmarks else "haar_turn_only","landmark_fps":fps if landmarks else None,"verified_mapping":False,"fallback":"local mouth-motion review or WIDE","reason":"Active-speaker accuracy is Not measured; AV mappings require a labeled accuracy gate"}
    if asd_payload:
        result["asd"] = asd_payload
    elif asd_reason and asd_reason != "asd disabled":
        result["asd_error"] = asd_reason
    atomic_write_json(output,result)
    return result


def caption_exclusions(analysis:dict,source:dict,config,framing:dict)->list[tuple]:
    from .framing import rect_at
    feed=config.regions["feed"]
    result=[]
    for row in analysis.get("observations",[])[::max(1,len(analysis.get("observations",[]))//20)]:
        segment=next((segment for segment in framing["segments"] if segment["t0"]<=row["t"]<segment["t1"]),framing["segments"][-1])
        mode=segment["mode"]
        x,y,w,h=row["source_box"]
        if mode=="WIDE":
            scale=min(feed["w"]/source["width"],feed["h"]/source["height"])
            ox,oy=(feed["w"]-source["width"]*scale)/2,(feed["h"]-source["height"]*scale)/2
        elif mode in {"SINGLE","MANUAL"}:
            rect=rect_at(framing["path"],row["t"])
            scale=feed["h"]/rect["h"]
            ox,oy=-rect["x"]*scale,-rect["y"]*scale
        elif mode=="DUAL":
            for index,rect in enumerate(segment["regions"][:2]):
                if not (rect["x"]<=x+w/2<=rect["x"]+rect["w"] and rect["y"]<=y+h/2<=rect["y"]+rect["h"]):continue
                scale=(feed["h"]/2)/rect["h"]
                result.append(((x-.2*w-rect["x"])*scale-24,feed["y"]+index*feed["h"]/2+(y-.25*h-rect["y"])*scale-24,w*1.4*scale+48,h*1.4*scale+48))
            continue
        else:
            continue
        if mode=="SINGLE" and framing.get("debug",{}).get("fallback")=="local_mouth_motion":
            # Protect the measured face plus a small margin, not the upper
            # torso. The older oversized box pushed captions far below the
            # reference even when no glyph would touch a face.
            pad_x,pad_y=w*.04*scale+8,h*.04*scale+8
            result.append((ox+x*scale-pad_x,feed["y"]+oy+y*scale-pad_y,w*scale+2*pad_x,h*scale+2*pad_y))
        else:
            result.append((ox+(x-.2*w)*scale-24,feed["y"]+oy+(y-.25*h)*scale-24,w*1.4*scale+48,h*1.4*scale+48))
    return result


def source_text_exclusions(shots:dict,source:dict,config,framing:dict,start:float,end:float)->list[tuple]:
    """Map measured lower-text bands into the current feed to avoid doubling."""
    if not config.get("source_text","detect",default=True):return []
    from .framing import rect_at
    feed=config.regions["feed"]
    result=[]
    for shot in shots.get("shots",[]):
        if shot.get("source_has_captions") and shot.get("text_band") and shot["end"]>start and shot["start"]<end:
            x,y,w,h=shot["text_band"]
            x,y,w,h=x*source["width"],y*source["height"],w*source["width"],h*source["height"]
            t=max(0,min(end-start,(shot["start"]+shot["end"])/2-start))
            segment=next((row for row in framing["segments"] if row["t0"]<=t<row["t1"]),framing["segments"][-1])
            if segment["mode"]=="WIDE":
                scale=min(feed["w"]/source["width"],feed["h"]/source["height"])
                result.append(((feed["w"]-source["width"]*scale)/2+x*scale,feed["y"]+(feed["h"]-source["height"]*scale)/2+y*scale,w*scale,h*scale))
            else:
                rectangles=segment["regions"][:2] if segment["mode"]=="DUAL" else [rect_at(framing["path"],t)]
                panel_height=feed["h"]/len(rectangles)
                for index,rect in enumerate(rectangles):
                    left,top=max(x,rect["x"]),max(y,rect["y"])
                    right,bottom=min(x+w,rect["x"]+rect["w"]),min(y+h,rect["y"]+rect["h"])
                    if right>left and bottom>top:
                        scale=panel_height/rect["h"]
                        result.append(((left-rect["x"])*scale,feed["y"]+index*panel_height+(top-rect["y"])*scale,(right-left)*scale,(bottom-top)*scale))
    return result


def measure_rendered_faces(output:Path,plan:dict,config)->dict:
    """Measure visible face geometry on decoded output, not inferred safety.

    The source track selects which detected box to check. It does not establish
    who spoke or validate platform safe zones. Missing detections are failures,
    not silently omitted samples.
    """
    import tempfile
    import cv2
    import mediapipe as mp
    from .models import model_spec
    from .framing import rect_at
    from .core.process import run_process,check_cancelled
    from .core.tools import require_tool
    spec=model_spec(config.get("framing","face_landmarker"))
    detector=mp.tasks.vision.FaceLandmarker.create_from_options(mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(spec["paths"]["model"])),num_faces=4))
    feed=config.regions["feed"]
    duration=plan["trim"]["duration"]
    samples=[]
    try:
        with tempfile.TemporaryDirectory(prefix="face_qa_",dir=output.parent) as folder:
            for index in range(12):
                check_cancelled()
                t=min(duration-.1,duration*.98*index/11)
                segment=next((row for row in plan["framing"]["segments"] if row["t0"]<=t<row["t1"]),plan["framing"]["segments"][-1])
                track=segment.get("track")
                rows=[row for row in plan.get("face_observations",[]) if row["track"]==track]
                source_face=min(rows,key=lambda row:abs(row["t"]-t)) if rows else None
                sample={"t":round(t,3),"track":track,"face_found":False,"face_inside_safe_area":False}
                if source_face is None or abs(source_face["t"]-t)>1.5 or segment["mode"]!="SINGLE":
                    sample["reason"]="Not measured; no selected face track at this time"
                    samples.append(sample)
                    continue
                path=Path(folder)/f"{index}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(t),"-i",output,"-frames:v","1",path],timeout=60)
                frame=cv2.imread(str(path))[feed["y"]:feed["y"]+feed["h"],feed["x"]:feed["x"]+feed["w"]]
                found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
                rect=rect_at(plan["framing"]["path"],t)
                x,y,w,h=source_face["source_box"]
                expected=((x+w/2-rect["x"])/rect["w"],(y+h/2-rect["y"])/rect["h"])
                faces=[]
                for face in found.face_landmarks:
                    xs,ys=[p.x for p in face],[p.y for p in face]
                    faces.append((min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)))
                box=min(faces,key=lambda b:(b[0]+b[2]/2-expected[0])**2+(b[1]+b[3]/2-expected[1])**2) if faces else None
                if box is not None and math.hypot(box[0]+box[2]/2-expected[0],box[1]+box[3]/2-expected[1])<.12:
                    x,y,w,h=box
                    sample.update({"face_found":True,"box_feed_px":[round(x*feed["w"],2),round(y*feed["h"],2),round(w*feed["w"],2),round(h*feed["h"],2)],"headroom_fraction":round(y,4),"face_height_fraction":round(h,4),"center_offset_fraction":round(abs(x+w/2-.5),4),"face_inside_safe_area":x>=.02 and x+w<=.98 and y>=.02 and y+h<=.98})
                samples.append(sample)
    finally:
        detector.close()
    measured=[row for row in samples if row["face_found"]]
    def bounds(key):
        return [min(row[key] for row in measured),max(row[key] for row in measured)] if measured else "Not measured"
    return {"method":"MediaPipe on 12 decoded output samples, matched to selected anonymous source track","safe_area":"2% inset of video window; platform safe zones Not measured","face_visible":{"found":len(measured),"samples":len(samples)},"face_in_safe_area":{"inside":sum(row["face_inside_safe_area"] for row in samples),"samples":len(samples)},"headroom":{"fraction_range":bounds("headroom_fraction"),"note":"landmark face box, not hairline"},"speaker_size":{"face_height_fraction_range":bounds("face_height_fraction"),"center_offset_fraction_range":bounds("center_offset_fraction")},"active_speaker_accuracy":"Not measured; local mouth-motion evidence requires review","samples":samples}
