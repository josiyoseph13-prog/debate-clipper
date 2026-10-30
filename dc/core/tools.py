from __future__ import annotations

import os
import shutil
import re
import json
from functools import lru_cache
from pathlib import Path

from .config import ROOT


def find_tool(name: str) -> str | None:
    env_name = f"{name.upper()}_PATH"
    configured = os.environ.get(env_name)
    if configured and Path(configured).exists():
        return configured
    found = shutil.which(name)
    if found:
        return found
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [ROOT / f"{name}{suffix}", ROOT / ".exe" / f"{name}{suffix}", ROOT.parent / ".exe" / f"{name}{suffix}"]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    settings=ROOT/"config"/"local_tools.json"
    if settings.is_file():
        try:
            profile=json.loads(settings.read_text(encoding="utf-8-sig")).get("windows" if os.name=="nt" else "linux",{})
            configured=profile.get(name)
            if configured and Path(configured).is_file():return str(configured)
        except (OSError,ValueError,TypeError):pass
    return None


def require_tool(name: str) -> str:
    found = find_tool(name)
    if not found:
        raise FileNotFoundError(f"{name} was not found on PATH or via {name.upper()}_PATH")
    return found


@lru_cache(maxsize=8)
def _ffmpeg_major(tool: str, modified_ns: int) -> int:
    from .process import run_process
    version=run_process([tool,"-version"],timeout=10,output_limit=10000)
    match=re.search(r"ffmpeg version n?(\d+)",version)
    return int(match.group(1)) if match else 0


def filter_script_args(path: str | Path) -> list[str]:
    """FFmpeg9 removed the old script alias; retain file-based graphs on both."""
    tool=require_tool("ffmpeg")
    major=_ffmpeg_major(tool,Path(tool).stat().st_mtime_ns)
    return ["-/filter_complex" if major>=7 else "-filter_complex_script",os.fspath(path)]
