"""Opt-in manual framing. Names are typed labels, never face identities."""
from __future__ import annotations

import copy
import math
import re


def number(value, minimum, maximum, name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(f"{name} must be a number between {minimum:g} and {maximum:g}")
    return float(value)


def validate_speaker_frame(value, width, height, duration):
    if not isinstance(value,dict):
        raise ValueError("Speaker Frame must be an object")
    allowed={"enabled","layout","selected","frame_t","boxes","blend","voice_map","overrides","shots","both_blended","duo","clip_start","clip_end"}
    if set(value)-allowed:
        raise ValueError("Unknown Speaker Frame setting")
    if value.get("enabled") is not True:
        if value.get("enabled") is False and set(value)=={"enabled"}:
            return {"enabled":False}
        raise ValueError("Speaker Frame must be explicitly enabled")
    layout=value.get("layout","single")
    if layout not in {"single","stacked","blended","auto","duo"}:
        raise ValueError("Choose One speaker, Stacked, Blended, Auto, or Duo")
    def boxes(items):
        if not isinstance(items,list) or not 1<=len(items)<=2:
            raise ValueError("Draw one or two speaker boxes")
        result=[]
        for item in items:
            if not isinstance(item,dict) or set(item)-{"id","name","x","y","w","h","face","offscreen","suggested"}:
                raise ValueError("Invalid speaker box")
            ident=item.get("id")
            if ident not in {"A","B"} or any(row["id"]==ident for row in result):
                raise ValueError("Box IDs must be A and B, without duplicates")
            name=item.get("name",f"Speaker {ident}")
            if not isinstance(name,str) or not 1<=len(name.strip())<=40 or not re.fullmatch(r"[\w .,'’()\-]+",name,flags=re.UNICODE):
                raise ValueError("Names must be short plain labels, without HTML")
            row={"id":ident,"name":name.strip()}
            for key,maximum in (("x",width),("y",height),("w",width),("h",height)):
                row[key]=number(item.get(key),0 if key in {"x","y"} else 8,maximum,f"Box {key}")
            if row["x"]+row["w"]>width+.001 or row["y"]+row["h"]>height+.001:
                raise ValueError("A box leaves the source picture")
            row["offscreen"]=item.get("offscreen",False)
            if not isinstance(row["offscreen"],bool):
                raise ValueError("Off screen must be a switch")
            if item.get("face") is not None:
                face=item["face"]
                if not isinstance(face,list) or len(face)!=4:
                    raise ValueError("Invalid suggested face")
                face=[number(v,0,width if i%2==0 else height,"Face coordinate") for i,v in enumerate(face)]
                if face[2]<8 or face[3]<8 or face[0]+face[2]>width or face[1]+face[3]>height:
                    raise ValueError("Suggested face leaves the picture")
                row["face"]=face
            result.append(row)
        return result
    clean={"enabled":True,"layout":layout,"selected":value.get("selected","A"),"frame_t":number(value.get("frame_t",0),0,duration,"Frame time"),"boxes":boxes(value.get("boxes"))}
    ids={row["id"] for row in clean["boxes"]}
    if clean["selected"] not in ids or layout in {"stacked","blended","duo"} and len(ids)!=2:
        raise ValueError("Choose a saved speaker; Both layouts need two boxes")
    blend=value.get("blend",{})
    if not isinstance(blend,dict) or set(blend)-{"width","position","direction","swap"}:
        raise ValueError("Invalid blend controls")
    clean["blend"]={"width":number(blend.get("width",.18),.04,.35,"Blend width"),"position":number(blend.get("position",.5),.3,.7,"Join position"),"direction":blend.get("direction","horizontal"),"swap":blend.get("swap",False)}
    if clean["blend"]["direction"] not in {"horizontal","vertical"} or not isinstance(clean["blend"]["swap"],bool):
        raise ValueError("Invalid blend direction or swap")
    clean["both_blended"]=value.get("both_blended",False)
    if not isinstance(clean["both_blended"],bool):
        raise ValueError("Use blended when both talk must be a switch")
    duo=value.get("duo",{})
    if not isinstance(duo,dict) or set(duo)-{"style","full_after","duo_after"}:
        raise ValueError("Invalid Duo controls")
    style=duo.get("style","smart")
    if style not in {"always_duo","always_full","smart"}:
        raise ValueError("Duo style must be Always Duo, Always Full, or Smart")
    clean["duo"]={"style":style,"full_after":number(duo.get("full_after",3.0),.5,20,"Full-screen delay"),"duo_after":number(duo.get("duo_after",.6),0,10,"Return to Duo delay")}
    mapping=value.get("voice_map",{})
    if not isinstance(mapping,dict) or len(mapping)>8 or any(not isinstance(k,str) or k=="unknown" or not re.fullmatch(r"[\w\-]{1,64}",k) or v not in ids for k,v in mapping.items()):
        raise ValueError("Link each known voice to one saved speaker box")
    clean["voice_map"]=mapping
    overrides=value.get("overrides",[])
    if not isinstance(overrides,list) or len(overrides)>100:
        raise ValueError("Too many timeline corrections")
    clean["overrides"]=[]
    for row in overrides:
        if not isinstance(row,dict) or set(row)-{"start","end","choice"}:
            raise ValueError("Invalid timeline correction")
        a=number(row.get("start"),0,duration,"Range start")
        b=number(row.get("end"),0,duration,"Range end")
        choice=row.get("choice")
        if b<=a or choice not in ids|{"both","wide"} or choice=="both" and len(ids)!=2:
            raise ValueError("Choose A, B, Both, or Wide for a valid range")
        if any(a<prior["end"] and b>prior["start"] for prior in clean["overrides"]):
            raise ValueError("Timeline corrections must not overlap")
        clean["overrides"].append({"start":a,"end":b,"choice":choice})
    shots=value.get("shots",[])
    if not isinstance(shots,list) or len(shots)>100:
        raise ValueError("Too many camera parts")
    clean["shots"]=[]
    for row in shots:
        if not isinstance(row,dict) or set(row)-{"t","boxes"}:
            raise ValueError("Invalid camera-part boxes")
        clean["shots"].append({"t":number(row.get("t"),0,duration,"Camera time"),"boxes":boxes(row.get("boxes"))})
    if len({row["t"] for row in clean["shots"]})!=len(clean["shots"]):
        raise ValueError("Camera-part times must be different")
    for key in ("clip_start","clip_end"):
        if key in value:
            clean[key]=number(value[key],0,1000000,key)
    return clean


def crop_for_box(box,source,output_w,output_h):
    """Uniform, source-bounded crop, centered on the user-selected upper body."""
    ratio=output_w/output_h
    # Wide stacked panels show the upper part of the selected body box. Fitting
    # the whole tall box into a wide panel also pulled the source split screen
    # and crowd into each panel. Keep a tighter, uniform upper-body crop.
    h=min(box["h"],box["w"]/ratio*1.5) if ratio>1.2 else max(box["h"],box["w"]/ratio)
    h=min(h,source["height"],source["width"]/ratio)
    w=h*ratio
    x=min(source["width"]-w,max(0,box["x"]+box["w"]/2-w/2))
    y=min(source["height"]-h,max(0,box["y"] if ratio>1.2 else box["y"]+box["h"]/2-h/2))
    return {"x":x,"y":y,"w":w,"h":h,"scale":output_h/h}


def blend_slots(width,height,blend):
    horizontal=blend["direction"]=="horizontal"
    size=width if horizontal else height
    join=round(size*blend["position"])
    band=max(2,round(size*blend["width"]))
    left=max(1,join-band//2)
    right=min(size-1,left+band)
    slots=[(0,0,right,height),(left,0,width-left,height)] if horizontal else [(0,0,width,right),(0,left,width,height-left)]
    return slots,left,right


def build_framing(spec,source,duration,config,turns=None,cuts=None,observations=None):
    spec=validate_speaker_frame(spec,source["width"],source["height"],duration)
    if not spec["enabled"]:
        return None
    feed=config.regions["feed"]
    turns=(turns or {}).get("turns",[])
    cuts=sorted(cut for cut in cuts or [] if 0<cut<duration)
    observations=observations or []
    warnings=[]
    def warn(t,text):
        if warnings and warnings[-1]["text"]==text:
            return
        row={"t":round(t,3),"text":text}
        if row not in warnings:
            warnings.append(row)
    points={0.0,duration,*cuts,*[row["t"] for row in spec["shots"]]}
    if spec["layout"] in {"auto","duo"}:
        points.update(index/10 for index in range(1,int(duration*10)+1) if index/10<duration)
    for row in spec["overrides"]:
        points.update([row["start"],row["end"]])
    for row in turns:
        a=max(0,float(row["start"])-source.get("clip_start",0))
        b=min(duration,float(row["end"])-source.get("clip_start",0))
        if 0<=a<b<=duration:
            points.update([a,b])
    points=sorted(points)
    segments=[]
    held=None
    duo_last_choice=None
    duo_hold_until=0.0
    for a,b in zip(points,points[1:]):
        t=(a+b)/2
        latest_cut=max([0.0]+[cut for cut in cuts if cut<=a])
        part=next(iter(sorted((row for row in spec["shots"] if row["t"]<=a),key=lambda row:row["t"],reverse=True)),None)
        boxes=copy.deepcopy(part["boxes"] if part else spec["boxes"])
        box_map={row["id"]:row for row in boxes}
        choice=spec["selected"] if spec["layout"]=="single" else "both"
        duo_full=False
        if spec["layout"]=="auto":
            active=[row for row in turns if float(row["start"])<=source.get("clip_start",0)+t<float(row["end"])]
            voices={spec["voice_map"].get(row.get("speaker")) for row in active}
            clear=active and None not in voices and all(row.get("confidence") is None or row.get("confidence",0)>=.5 for row in active)
            if clear:
                desired=next(iter(voices)) if len(voices)==1 else "both"
                span=min(float(row["end"]) for row in active)-max(float(row["start"]) for row in active)
                choice=held if span<.6 and held else desired
                if held and choice!=held and segments and a-segments[-1]["t0"]<1.5:
                    choice=held
            else:
                choice="both" if len(boxes)==2 else "wide"
                warn(a,"Audio unclear. Showing both." if len(boxes)==2 else "Audio unclear. Showing the wide shot.")
        elif spec["layout"]=="duo":
            active=[row for row in turns if float(row["start"])<=source.get("clip_start",0)+t<float(row["end"])]
            mapped={spec["voice_map"].get(row.get("speaker")) for row in active}
            clear=active and None not in mapped and len(mapped)==1 and all(row.get("confidence") is None or row.get("confidence",0)>=.5 for row in active)
            style=spec["duo"]["style"]
            if style=="always_duo":
                choice="both"
            elif not active and duo_last_choice in box_map and t < duo_hold_until:
                choice=duo_last_choice
                duo_full=True
            elif clear and style in {"always_full","smart"}:
                voice=next(iter(mapped))
                current=max(row for row in active if spec["voice_map"].get(row.get("speaker"))==voice)
                uninterrupted=t-(float(current["start"])-source.get("clip_start",0))
                # Full view starts only after the explicit delay. Once it has
                # started, hold it through the turn and the return delay.
                prior_full=held in box_map and held==duo_last_choice
                since_end=(source.get("clip_start",0)+t)-float(current["end"])
                if style=="always_full" or uninterrupted>=spec["duo"]["full_after"] or prior_full and since_end<spec["duo"]["duo_after"]:
                    choice=voice
                    duo_full=True
                    duo_last_choice=voice
                    duo_hold_until=float(current["end"])-source.get("clip_start",0)+spec["duo"]["duo_after"]
                else:
                    choice="both"
            else:
                choice="both"
                warn(a,"Audio unclear. Staying in Duo." if len(boxes)==2 else "Audio unclear. Showing the wide shot.")
        override=next((row for row in spec["overrides"] if row["start"]<=t<row["end"]),None)
        if override:
            choice=override["choice"]
        if latest_cut>0 and (part is None or part["t"]<latest_cut-.05):
            choice="wide"
            warn(latest_cut,"Camera changed. Check the boxes.")
        chosen=boxes if choice=="both" else [box_map[choice]] if choice in box_map else []
        # Explicit off-screen marks always win. Missing observations are not
        # evidence that a manually drawn box is valid; report Not measured.
        chosen=[box for box in chosen if not box.get("offscreen")]
        if not chosen or choice=="wide":
            choice="wide"
            mode="WIDE"
            rect=crop_for_box({"x":0,"y":0,"w":source["width"],"h":source["height"]},source,feed["w"],feed["h"])
            regions=[rect]
            if latest_cut==0:
                warn(a,"Speaker off screen or not selected. Showing the wide shot.")
        elif len(chosen)==1:
            mode="SINGLE"
            regions=[crop_for_box(chosen[0],source,feed["w"],feed["h"])]
            if choice=="both":
                warn(a,"Speaker off screen. Showing the other speaker.")
        else:
            mode="BLEND" if spec["layout"] in {"blended","duo"} or spec["layout"]=="auto" and spec["both_blended"] else "DUAL"
            if spec["blend"]["swap"]:
                chosen=chosen[::-1]
            if mode=="BLEND":
                slots,left,right=blend_slots(feed["w"],feed["h"],spec["blend"])
                regions=[crop_for_box(box,source,slot[2],slot[3]) for box,slot in zip(chosen,slots)]
                for box,rect,slot in zip(chosen,regions,slots):
                    face=box.get("face")
                    if face:
                        horizontal=spec["blend"]["direction"]=="horizontal"
                        axis=0 if horizontal else 1
                        low=slot[axis]+(face[axis]-rect["x" if horizontal else "y"])*slot[axis+2]/rect["w" if horizontal else "h"]
                        high=low+face[axis+2]*slot[axis+2]/rect["w" if horizontal else "h"]
                        if low<right and high>left:
                            warn(a,"A face is in the blend area. Move the join or choose Stacked.")
            else:
                regions=[crop_for_box(box,source,feed["w"],feed["h"]//2) for box in chosen]
        if any(rect.get("scale",1)>2 for rect in regions):
            warn(a,"Source resolution is low for this crop. Try Stacked or a wider box.")
        current={"t0":a,"t1":b,"mode":mode,"choice":choice,"regions":regions,"boxes":chosen,"blend":spec["blend"],"confidence":1.0,"reasons":["USER_SPEAKER_FRAME"]}
        if spec["layout"]=="duo":
            current["duo_full"]=duo_full
        if segments and all(segments[-1].get(key)==current.get(key) for key in ("mode","choice","regions","boxes")):
            segments[-1]["t1"]=b
        else:
            segments.append(current)
        held=choice
    path=[]
    for segment in segments:
        rect=segment["regions"][0]
        if path:
            path.append({**path[-1],"t":segment["t0"]})
        path.extend([{"t":segment["t0"],**rect},{"t":segment["t1"],**rect}])
    layout_seconds={}
    for segment in segments:
        label={"SINGLE":"One speaker","DUAL":"Both stacked","BLEND":"Duo" if spec["layout"]=="duo" else "Both blended","WIDE":"Wide"}[segment["mode"]]
        layout_seconds[label]=round(layout_seconds.get(label,0)+segment["t1"]-segment["t0"],3)
    return {"schema_version":5,"segments":segments,"path":path,"debug":{"speaker_frame":True,"warnings":warnings,"layout_seconds":layout_seconds,"camera_cuts":cuts,"tracking":"OFF; boxes stay fixed inside each confirmed camera part","faces_inside_safe_area":"Not measured","headroom":"Not measured"}}


def compose_frame(frame,segment,width,height):
    """Render the same panel geometry used by the browser live canvas."""
    import numpy as np
    from .framing import warp_subpixel
    if segment["mode"]=="SINGLE":
        return warp_subpixel(frame,segment["regions"][0],width,height)
    if segment["mode"]=="DUAL":
        return np.concatenate([warp_subpixel(frame,r,width,height//2) for r in segment["regions"]],axis=0)
    if segment["mode"]!="BLEND":
        raise ValueError("Wide composition is handled by the existing renderer")
    slots,left,right=blend_slots(width,height,segment["blend"])
    layers=[]
    for rect,(x,y,w,h) in zip(segment["regions"],slots):
        layer=np.zeros((height,width,3),dtype=np.uint8)
        layer[y:y+h,x:x+w]=warp_subpixel(frame,rect,w,h)
        layers.append(layer)
    axis=width if segment["blend"]["direction"]=="horizontal" else height
    weight=np.clip((np.arange(axis,dtype=np.float32)-left)/max(1,right-left),0,1)
    weight=weight*weight*(3-2*weight)
    weight=weight[None,:,None] if segment["blend"]["direction"]=="horizontal" else weight[:,None,None]
    return np.rint(layers[0]*(1-weight)+layers[1]*weight).astype(np.uint8)


def exclusions(framing,feed,observations):
    """Map measured source faces to each panel; manual body boxes aren't faces."""
    result=[]
    for segment in framing["segments"]:
        if segment["mode"]=="WIDE":
            continue
        if segment["mode"]=="BLEND":
            slots,_,_=blend_slots(feed["w"],feed["h"],segment["blend"])
        elif segment["mode"]=="DUAL":
            slots=[(0,0,feed["w"],feed["h"]//2),(0,feed["h"]//2,feed["w"],feed["h"]//2)]
        else:
            slots=[(0,0,feed["w"],feed["h"])]
        samples=[row for row in observations if segment["t0"]<=row["t"]<segment["t1"]]
        for row in samples[::max(1,len(samples)//20)]:
            x,y,w,h=row["source_box"]
            for rect,slot in zip(segment["regions"],slots):
                if rect["x"]<=x+w/2<=rect["x"]+rect["w"] and rect["y"]<=y+h/2<=rect["y"]+rect["h"]:
                    scale=slot[2]/rect["w"]
                    result.append((slot[0]+(x-rect["x"])*scale-8,feed["y"]+slot[1]+(y-rect["y"])*scale-8,w*scale+16,h*scale+16))
    return result


def measure_output(output,plan,config):
    """Inspect real decoded panels. Manual body boxes are never face evidence."""
    import tempfile
    from pathlib import Path
    import cv2
    import mediapipe as mp
    from .models import model_spec
    from .core.process import run_process,check_cancelled
    from .core.tools import require_tool
    from .framing import framing_quality
    spec=model_spec(config.get("framing","face_landmarker"))
    detector=mp.tasks.vision.FaceLandmarker.create_from_options(mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(spec["paths"]["model"])),num_faces=4))
    feed=config.regions["feed"]
    samples=[]
    expected=0
    try:
        with tempfile.TemporaryDirectory(prefix="speaker_frame_qa_",dir=output.parent) as folder:
            for index in range(12):
                check_cancelled()
                t=min(plan["trim"]["duration"]-.1,plan["trim"]["duration"]*.98*index/11)
                segment=next((s for s in plan["framing"]["segments"] if s["t0"]<=t<s["t1"]),plan["framing"]["segments"][-1])
                if segment["mode"]=="WIDE":
                    samples.append({"t":round(t,3),"layout":"Wide","face":"Not measured; safe fallback used"})
                    continue
                path=Path(folder)/f"{index}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(t),"-i",output,"-frames:v","1",path],timeout=60)
                frame=cv2.imread(str(path))[feed["y"]:feed["y"]+feed["h"],feed["x"]:feed["x"]+feed["w"]]
                if segment["mode"]=="BLEND":
                    slots,left,right=blend_slots(feed["w"],feed["h"],segment["blend"])
                elif segment["mode"]=="DUAL":
                    slots=[(0,0,feed["w"],feed["h"]//2),(0,feed["h"]//2,feed["w"],feed["h"]//2)]
                else:
                    slots=[(0,0,feed["w"],feed["h"])]
                for box,rect,(sx,sy,sw,sh) in zip(segment["boxes"],segment["regions"],slots):
                    expected+=1
                    sample={"t":round(t,3),"speaker":box["id"],"layout":segment["mode"],"face_found":False}
                    # Match only a source face inside this manual upper-body box.
                    local=[r for r in plan.get("face_observations",[]) if abs(r["t"]-t)<.15 and box["x"]<=r["source_box"][0]+r["source_box"][2]/2<=box["x"]+box["w"] and box["y"]<=r["source_box"][1]+r["source_box"][3]/2<=box["y"]+box["h"]]
                    source_face=min(local,key=lambda r:abs(r["t"]-t))["source_box"] if local else None
                    tile=frame[sy:sy+sh,sx:sx+sw]
                    found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(tile,cv2.COLOR_BGR2RGB)))
                    candidates=[]
                    for face in found.face_landmarks:
                        xs,ys=[p.x for p in face],[p.y for p in face]
                        candidates.append((min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)))
                    if source_face:
                        x,y,w,h=source_face
                        target=((x+w/2-rect["x"])/rect["w"],(y+h/2-rect["y"])/rect["h"])
                        face=min(candidates,key=lambda f:math.hypot(f[0]+f[2]/2-target[0],f[1]+f[3]/2-target[1])) if candidates else None
                        if face and math.hypot(face[0]+face[2]/2-target[0],face[1]+face[3]/2-target[1])<.15:
                            x,y,w,h=face
                            inside=x>=.02 and x+w<=.98 and y>=.02 and y+h<=.98
                            blend_clear=True
                            if segment["mode"]=="BLEND":
                                lo=sx+x*sw if segment["blend"]["direction"]=="horizontal" else sy+y*sh
                                hi=lo+(w*sw if segment["blend"]["direction"]=="horizontal" else h*sh)
                                blend_clear=hi<=left or lo>=right
                            sample.update({"face_found":True,"face_inside_safe_area":inside,"face_outside_blend":blend_clear,"headroom_fraction":round(y,4),"face_height_fraction":round(h,4),"box_feed_px":[round(sx+x*sw,2),round(sy+y*sh,2),round(w*sw,2),round(h*sh,2)]})
                    samples.append(sample)
    finally:
        detector.close()
    found=[row for row in samples if row.get("face_found")]
    inside=sum(row["face_inside_safe_area"] and row["face_outside_blend"] for row in found)
    safe="no" if any(not r["face_inside_safe_area"] or not r["face_outside_blend"] for r in found) else "yes" if expected and len(found)==expected else "Not measured"
    headroom="Not measured" if len(found)!=expected or not found else "too little" if min(r["headroom_fraction"] for r in found)<.04 else "too much" if max(r["headroom_fraction"] for r in found)>.35 else "good"
    quality=framing_quality(plan)
    return {"faces_inside_safe_area":safe,"headroom":headroom,"face_found":len(found),"expected_face_samples":expected,"face_inside_count":inside,"method":"12 decoded output samples; per-panel face detections matched to measured source faces inside the user's boxes; 2% panel inset","layout_seconds":plan["framing"]["debug"]["layout_seconds"],"warnings":plan["framing"]["debug"]["warnings"],"camera_moves":quality["camera_moves"],"camera_speed_px_s":quality["camera_jump"]["value_px_per_second"],"speaker_identity":"User labels only; automatic speaker accuracy Not measured","tracking":"OFF","samples":samples}
