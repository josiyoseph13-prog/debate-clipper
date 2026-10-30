from pathlib import Path
from .core.io import atomic_write_json
from .core.security import validate_id
from .signals import timestamp_mentions


def download_source(url:str,folder:Path,no_network:bool=False,comments:int=0):
    if no_network:
        raise RuntimeError("--no-network blocks URL download")
    import yt_dlp
    folder.mkdir(parents=True,exist_ok=True)
    options={"outtmpl":str(folder/"%(id)s.%(ext)s"),"noplaylist":True,"overwrites":False,"restrictfilenames":True,"merge_output_format":"mp4","format":"bestvideo[height<=1080]+bestaudio/best","quiet":True,"extractor_args":{"youtube":{"max_comments":[str(max(0,min(500,comments)))],"player_client":["android"]}},"getcomments":bool(comments)}
    with yt_dlp.YoutubeDL(options) as downloader:
        info=downloader.extract_info(url,download=True)
        source=Path(info.get("requested_downloads",[{}])[0].get("filepath") or downloader.prepare_filename(info))
        if not source.is_file():
            source=source.with_suffix(".mp4")
    validate_id(str(info["id"]))
    metadata={key:info.get(key) for key in ("id","title","description","chapters","upload_date","channel","uploader","license","webpage_url","duration","heatmap")}
    if comments:
        metadata["crowd_mentions"]=timestamp_mentions([str(row.get("text","")) for row in info.get("comments",[])])
    atomic_write_json(source.with_suffix(".info.json"),{"schema_version":5,**metadata})
    return source,metadata
