"""youtube-info — probe YouTube metadata and transcripts honestly.

Metadata comes from yt-dlp in dump-json mode (no media download).
Transcripts come from youtube-transcript-api. Both are best-effort:
YouTube has blocked this machine's network before (HTTP 429 / bot
checks), so failures are reported as results with their real error
text — never retried into evasion, never papered over.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .common import ResearchError, youtube_video_id

_YTDLP_CANDIDATES = [
    Path.home() / "workspace/tools/media-venv/bin/yt-dlp",
]


def _find_ytdlp() -> str | None:
    for candidate in _YTDLP_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return shutil.which("yt-dlp")


def probe(url_or_id: str, want_transcript: bool) -> dict:
    video_id = youtube_video_id(url_or_id)
    if not video_id:
        raise ResearchError(f"could not find a YouTube video id in {url_or_id!r}")
    url = f"https://www.youtube.com/watch?v={video_id}"
    result: dict = {"video_id": video_id, "url": url,
                    "metadata": None, "metadata_status": "not_run",
                    "transcript": None, "transcript_status": "not_requested"}

    ytdlp = _find_ytdlp()
    if ytdlp is None:
        result["metadata_status"] = "yt-dlp not installed"
    else:
        try:
            proc = subprocess.run(
                [ytdlp, "--dump-single-json", "--no-download",
                 "--no-warnings", url],
                capture_output=True, text=True, timeout=90)
            if proc.returncode == 0:
                info = json.loads(proc.stdout)
                result["metadata"] = {
                    "title": info.get("title"),
                    "channel": info.get("channel") or info.get("uploader"),
                    "duration_seconds": info.get("duration"),
                    "upload_date": info.get("upload_date"),
                    "view_count": info.get("view_count"),
                }
                result["metadata_status"] = "ok"
            else:
                tail = (proc.stderr or "").strip().splitlines()
                result["metadata_status"] = (
                    "failed: " + (tail[-1][:300] if tail else "yt-dlp error"))
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            result["metadata_status"] = f"failed: {type(exc).__name__}"

    if want_transcript:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            segments = [{"start": s.start, "duration": s.duration,
                         "text": s.text} for s in fetched]
            text = " ".join(s["text"] for s in segments)
            result["transcript"] = {"segments": len(segments),
                                     "chars": len(text),
                                     "text_preview": text[:500]}
            result["transcript_status"] = "ok"
        except Exception as exc:  # library raises many typed errors
            result["transcript_status"] = (
                f"failed: {type(exc).__name__}: {str(exc)[:300]}")
    return result
