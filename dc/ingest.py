from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core.config import ROOT
from .core.hashing import source_fingerprint
from .core.io import atomic_write_json
from .core.process import ProcessCancelled, run_process
from .core.tools import require_tool


def ffprobe(path: Path) -> dict[str, Any]:
    try:
        output = run_process([require_tool("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", path], timeout=30)
        return json.loads(output)
    except ProcessCancelled:
        raise
    except Exception:
        # A source artifact remains useful when ffprobe is not installed; doctor reports the missing tool.
        return {"format": {}, "streams": []}


def ingest(source: Path | str, job_dir: Path, url: str | None = None, rights_class: str = "unknown", rights_note: str = "") -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(source_path)
    probe = ffprobe(source_path)
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Source has no video stream")
    duration = float(probe.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise ValueError("Source duration is not positive")
    fingerprint = source_fingerprint(source_path)
    metadata_path = source_path.with_suffix(".metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    artifact = {"schema_version": 5, "source_id": fingerprint["sha256"][:16], "path": str(source_path), "source_url": url or metadata.get("webpage_url"), "duration": duration, "width": int(video.get("width", 0)), "height": int(video.get("height", 0)), "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"), "r_frame_rate": video.get("r_frame_rate"), "avg_frame_rate": video.get("avg_frame_rate"), "has_audio": any(stream.get("codec_type") == "audio" for stream in streams), "fingerprint": fingerprint, "meta": metadata, "probe": probe, "rights_class": rights_class, "rights_note": rights_note, "rights_unknown": rights_class == "unknown"}
    atomic_write_json(job_dir / "source.json", artifact)
    return artifact
