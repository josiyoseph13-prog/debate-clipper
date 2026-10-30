"""Explicit-click private publishers; credentials are supplied through keyring."""
from __future__ import annotations
import json
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from ..core.io import read_json
from ..core.logging import log_event
from ..integrity import publish_gate


def publish(export_dir:Path,platform:str,config,confirmed:bool,no_network:bool=True,adapter=None):
    if not confirmed: raise ValueError("Publishing requires an explicit Studio click")
    if not config.get("distribution","publish","enabled",default=False): raise RuntimeError("Publisher disabled in configuration")
    if no_network: raise RuntimeError("--no-network blocks publishing")
    candidate=read_json(export_dir/"candidate.json",{}) or {}
    provenance=read_json(export_dir/"provenance.json",{}) or {}
    qa=read_json(export_dir/"export_report.json",{}) or {}
    allowed,reasons=publish_gate(candidate,provenance,config)
    if not allowed or qa.get("status")!="passed": raise ValueError("Publish blocked: "+", ".join(reasons+["QA must pass"] if qa.get("status")!="passed" else reasons))
    metadata=read_json(export_dir/"metadata.json")
    if adapter:
        result=adapter(export_dir/"clip.mp4",metadata,privacy="private")
    elif platform=="youtube_shorts":
        result=publish_youtube(export_dir/"clip.mp4",metadata)
    elif platform=="tiktok":
        result=publish_tiktok_inbox(export_dir/"clip.mp4")
    else:
        raise RuntimeError("Register an audited platform adapter; Instagram is intentionally unavailable without account/media hosting prerequisites")
    log_event(export_dir/"publish_log.jsonl",candidate["id"],"publish","uploaded",platform=platform,privacy="private",remote_id=result.get("id"))
    return result


def credential(platform):
    import keyring
    value=keyring.get_password("political-lens",platform)
    if not value: raise RuntimeError("Platform OAuth token absent from OS keyring")
    return value


def request_json(url,body,token):
    request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=60) as response:
        return json.loads(response.read(1_000_000)),dict(response.headers)


class _NoUploadRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,response,code,message,headers,new_url):
        return None


def _upload_request(request,platform):
    parsed=urlsplit(request.full_url)
    suffixes=("googleapis.com",) if platform=="youtube" else ("tiktokapis.com","tiktokv.com","byteoversea.com")
    host=(parsed.hostname or "").lower()
    if parsed.scheme!="https" or parsed.username or parsed.password or parsed.port not in {None,443} or not any(host==suffix or host.endswith("."+suffix) for suffix in suffixes):
        raise ValueError("Invalid platform upload endpoint")
    return urllib.request.build_opener(_NoUploadRedirect).open(request,timeout=180)


def publish_youtube(path:Path,metadata:dict):
    token=credential("youtube")
    request=urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",data=json.dumps({"snippet":{"title":metadata["title"][:100],"description":metadata["description"]},"status":{"privacyStatus":"private","selfDeclaredMadeForKids":False}}).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json","X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(path.stat().st_size)})
    with urllib.request.urlopen(request,timeout=60) as response:
        location=response.headers["Location"]
    # Bounded chunk reads; an interrupted session can be resumed by the
    # platform session URL stored outside application logs.
    size=path.stat().st_size
    with path.open("rb") as handle:
        offset=0
        while chunk:=handle.read(8*1024*1024):
            end=offset+len(chunk)-1
            request=urllib.request.Request(location,data=chunk,method="PUT",headers={"Authorization":"Bearer "+token,"Content-Type":"video/mp4","Content-Range":f"bytes {offset}-{end}/{size}"})
            try:
                with _upload_request(request,"youtube") as response:
                    data=json.loads(response.read(1_000_000))
            except urllib.error.HTTPError as exc:
                if exc.code!=308: raise
                data={}
            offset=end+1
    return data


def publish_tiktok_inbox(path:Path):
    token=credential("tiktok")
    size=path.stat().st_size
    if size<=0:raise ValueError("Empty upload")
    unit=8*1024*1024
    count=max(1,size//unit)
    chunk_size=size if count==1 else unit
    result,_=request_json("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",{"source_info":{"source":"FILE_UPLOAD","video_size":size,"chunk_size":chunk_size,"total_chunk_count":count}},token)
    if result.get("error",{}).get("code")!="ok": raise RuntimeError("TikTok upload initialization refused")
    data=result["data"]
    # The inbox workflow requires the creator's final in-app posting action.
    with path.open("rb") as handle:
        offset=0
        for index in range(count):
            wanted=unit if index<count-1 else size-offset
            payload=handle.read(wanted)
            if len(payload)!=wanted:raise RuntimeError("Upload file changed while reading")
            end=offset+len(payload)-1
            request=urllib.request.Request(data["upload_url"],data=payload,method="PUT",headers={"Content-Type":"video/mp4","Content-Range":f"bytes {offset}-{end}/{size}"})
            with _upload_request(request,"tiktok") as response:
                response.read(1000)
            offset=end+1
    return {"id":data["publish_id"],"mode":"inbox","privacy":"private"}
