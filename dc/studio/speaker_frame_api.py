"""Lazy, host-only Speaker Frame endpoints, under Studio's security middleware."""
from datetime import datetime,timezone
import re
from pathlib import Path

from ..core.config import ROOT,load_preset
from ..core.decisions import latest_decision,record_decision
from ..core.io import read_json,atomic_write_json
from ..core.security import validate_id
from ..core.hashing import content_hash
from ..speaker_frame import validate_speaker_frame,build_framing


def install_routes(app,lan,render_lock):
    from fastapi import HTTPException,Request
    from fastapi.responses import FileResponse
    from starlette.concurrency import run_in_threadpool

    def context(job_id,candidate_id):
        from ..cli import _load_job
        validate_id(job_id)
        validate_id(candidate_id)
        job,source,transcript,artifact=_load_job(job_id)
        candidate=next((row for row in artifact.get("candidates",[]) if row["id"]==candidate_id),None)
        if candidate is None:
            raise ValueError("Clip not found")
        source_path=Path(source["path"])
        if not source_path.is_file() or source_path.is_symlink() or not source_path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Invalid source path")
        decision=latest_decision(ROOT,job_id,candidate_id)
        candidate={**candidate,**decision.get("edits",{})}
        duration=candidate["end"]-candidate["start"]
        if duration<=0 or candidate["start"]<0 or candidate["end"]>source.get("duration",candidate["end"]):
            raise ValueError("Invalid clip times")
        saved=read_json(job/"job_config.json",{}) or {}
        config=load_preset(saved.get("preset","political_lens"))
        folder=job/"speaker_frame"/candidate_id
        if (job/"speaker_frame").is_symlink() or folder.is_symlink():
            raise ValueError("Invalid Speaker Frame path")
        if any((folder/name).is_symlink() for name in ("tracking.json","auto.json","chrome.png","picker.mp4","picker.mp4.part")):
            raise ValueError("Invalid Speaker Frame cache path")
        return job,folder,source,transcript,candidate,decision,config,duration

    def prepare(job_id,candidate_id,rerun=False,choice=None):
        from ..vision import analyze_window,directed_framing
        from ..framing import framing_plan
        from ..chrome import render_chrome
        from ..core.process import run_process
        from ..core.tools import require_tool
        job,folder,source,transcript,candidate,decision,config,duration=context(job_id,candidate_id)
        saved_spec=decision.get("speaker_frame",{})
        if rerun and saved_spec.get("enabled") and choice not in {"keep","replace"}:
            raise ValueError("Keep your Speaker Frame changes or replace them?")
        folder.mkdir(parents=True,exist_ok=True)
        tracking=folder/"tracking.json"
        if tracking.is_symlink():
            raise ValueError("Invalid tracking path")
        if rerun:
            # Invalidate this opt-in cache only, without changing normal Auto.
            atomic_write_json(tracking,{})
        try:
            analysis=analyze_window({**source,"sha256":source.get("fingerprint",{}).get("sha256")},candidate["start"],candidate["end"],transcript,config,tracking)
        except (ImportError,RuntimeError,ValueError) as exc:
            analysis={"observations":[],"tracks":{},"scene_cuts":[],"reason":f"Not measured: {exc}"}
            atomic_write_json(tracking,analysis)
        automatic=directed_framing(analysis,source,duration,config,read_json(ROOT/"reports/framing_gate.json",{}) or {}) or framing_plan(source["width"],source["height"],duration,config)
        picker_key=content_hash({"source":source.get("fingerprint",{}).get("sha256"),"start":candidate["start"],"end":candidate["end"],"picker_version":1})
        previous=read_json(folder/"auto.json",{}) or {}
        if previous.get("picker_key")!=picker_key or not (folder/"picker.mp4").is_file():
            partial=folder/"picker.mp4.part"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(candidate["start"]),"-i",source["path"],"-t",str(duration),"-vf","scale=960:-2","-c:v","libx264","-preset","ultrafast","-crf","23","-c:a","aac","-movflags","+faststart","-f","mp4",partial],timeout=max(120,duration*5))
            partial.replace(folder/"picker.mp4")
        auto={"framing":automatic,"start":candidate["start"],"end":candidate["end"],"config_hash":config.hash(),"picker_key":picker_key}
        atomic_write_json(folder/"auto.json",auto)
        rows=analysis.get("observations",[])
        tracks=sorted(analysis.get("tracks",{}),key=lambda track:analysis["tracks"][track],reverse=True)
        selected=automatic.get("segments",[{}])[0].get("track")
        if selected in tracks:
            tracks.remove(selected)
            tracks.insert(0,selected)
        boxes=[]
        for track in tracks:
            local=[row for row in rows if row["track"]==track and abs(row["t"])<.5]
            if not local or analysis["tracks"][track]<max(8,duration*2):
                continue
            face=min(local,key=lambda row:row["t"])["source_box"]
            x,y,w,h=face
            bx,by=max(0,x-w*.35),max(0,y-h*.2)
            boxes.append({"id":"AB"[len(boxes)],"name":f"Speaker {'AB'[len(boxes)]}","x":bx,"y":by,"w":min(w*1.7,source["width"]-bx),"h":min(h*2.1,source["height"]-by),"face":face,"suggested":True})
            if len(boxes)==2:
                break
        turns=read_json(job/"turns.json",{}) or {}
        voices=[]
        for voice in sorted({row.get("speaker","unknown") for row in turns.get("turns",[])})[:8]:
            if voice=="unknown":
                continue
            try:
                validate_id(voice)
            except ValueError:
                continue
            sample=next((row for row in turns["turns"] if row.get("speaker")==voice and row["end"]>candidate["start"] and row["start"]<candidate["end"]),None)
            if sample:
                path=folder/f"voice_{voice}.wav"
                if path.is_symlink():
                    raise ValueError("Invalid voice sample path")
                start=max(candidate["start"],sample["start"])
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(start),"-i",source["path"],"-t",str(min(3,sample["end"]-start)),"-vn","-ac","1","-ar","16000",path],timeout=60)
                voices.append({"id":voice,"url":f"/api/speaker-frame/{job_id}/{candidate_id}/asset/{path.name}"})
        chrome=folder/"chrome.png"
        if chrome.is_symlink():
            raise ValueError("Invalid chrome path")
        headline=decision.get("headline") or next(iter(candidate.get("hook",{}).get("headline_options",[])),"The full exchange")
        render_chrome(config,headline,chrome)
        if rerun and choice=="replace":
            record_decision(ROOT,{"schema_version":5,"time":datetime.now(timezone.utc).isoformat(),"job_id":job_id,"candidate_id":candidate_id,"action":"save","speaker_frame":{"enabled":False}})
            saved_spec={}
        return {"start":candidate["start"],"end":candidate["end"],"duration":duration,"source":{k:source[k] for k in ("width","height")},"canvas":config.canvas,"feed":config.regions["feed"],"auto":automatic,"suggestions":boxes,"saved":saved_spec,"camera_cuts":analysis.get("scene_cuts",[]),"voices":voices,"turns":turns,"chrome_url":f"/api/speaker-frame/{job_id}/{candidate_id}/asset/chrome.png","picker_url":f"/api/speaker-frame/{job_id}/{candidate_id}/asset/picker.mp4","message":"Suggested by Auto Reframe","audio_note":"" if voices else "Audio unclear. Showing both. No identified voice turns are available; use the timeline to correct moments."}

    async def payload(request):
        if lan:
            raise HTTPException(403,"Speaker Frame editing is available from localhost only")
        try:
            value=await request.json()
            if not isinstance(value,dict):
                raise ValueError("Object required")
            validate_id(value.get("job_id",""))
            validate_id(value.get("candidate_id",""))
            return value
        except (ValueError,TypeError):
            raise HTTPException(400,"Invalid Speaker Frame request")

    @app.post("/api/speaker-frame/open")
    async def open_editor(request:Request):
        value=await payload(request)
        if not render_lock.acquire(blocking=False):
            raise HTTPException(409,"Another preview or render is running")
        try:
            return await run_in_threadpool(prepare,value["job_id"],value["candidate_id"],value.get("rerun") is True,value.get("choice"))
        except (ValueError,SystemExit,RuntimeError,ImportError) as exc:
            raise HTTPException(400,str(exc))
        finally:
            render_lock.release()

    def evaluate(value,save=False):
        job,folder,source,transcript,candidate,decision,config,duration=context(value["job_id"],value["candidate_id"])
        spec=validate_speaker_frame(value.get("speaker_frame"),source["width"],source["height"],duration)
        result={"speaker_frame":spec}
        if spec.get("enabled"):
            spec.update({"clip_start":candidate["start"],"clip_end":candidate["end"]})
            analysis=read_json(folder/"tracking.json",{}) or {}
            result["framing"]=build_framing(spec,{**source,"clip_start":candidate["start"]},duration,config,read_json(job/"turns.json",{}),analysis.get("scene_cuts",[]),analysis.get("observations",[]))
        if save:
            record_decision(ROOT,{"schema_version":5,"time":datetime.now(timezone.utc).isoformat(),"job_id":value["job_id"],"candidate_id":value["candidate_id"],"action":"save","speaker_frame":spec})
        result["message"]="Speaker Frame saved for this clip." if spec.get("enabled") else "Back to Auto Reframe."
        return result

    @app.post("/api/speaker-frame/preview")
    async def preview(request:Request):
        value=await payload(request)
        try:
            return await run_in_threadpool(evaluate,value,False)
        except (ValueError,SystemExit) as exc:
            raise HTTPException(400,str(exc))

    @app.post("/api/speaker-frame/save")
    async def save(request:Request):
        value=await payload(request)
        try:
            return await run_in_threadpool(evaluate,value,True)
        except (ValueError,SystemExit) as exc:
            raise HTTPException(400,str(exc))

    @app.get("/api/speaker-frame/{job_id}/{candidate_id}/asset/{name}")
    async def asset(job_id:str,candidate_id:str,name:str):
        try:
            _,folder,*_=context(job_id,candidate_id)
            if name not in {"chrome.png","picker.mp4"} and not re.fullmatch(r"voice_[A-Za-z0-9_-]{1,64}\.wav",name):
                raise ValueError("Invalid asset")
            path=folder/name
            if not path.is_file() or path.is_symlink() or path.resolve().parent!=folder.resolve():
                raise ValueError("Asset not found")
            return FileResponse(path)
        except (ValueError,SystemExit):
            raise HTTPException(404,"Speaker Frame asset not found")
