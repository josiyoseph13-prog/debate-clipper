"""Capture start/middle/end evidence frames for Fix Round 2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc.core.process import run_process
from dc.core.tools import require_tool


def duration(path: Path) -> float:
    probe = json.loads(run_process([require_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], timeout=30))
    return float(probe.get("format", {}).get("duration") or 0)


def capture(path: Path, destination: Path, label: str) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    length = duration(path)
    outputs = []
    for name, point in (("start", 0.0), ("middle", length / 2), ("end", max(0.0, length - 0.1))):
        output = destination / f"{label}_{name}.png"
        run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{point:.3f}", "-i", str(path), "-frames:v", "1", str(output)], timeout=60)
        outputs.append(output)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    outputs = capture(args.video, args.out, args.label)
    print(json.dumps({"video": str(args.video), "frames": [str(path) for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
