"""Capture six evenly spaced evidence frames from a video."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dc.core.process import run_process
from dc.core.tools import require_tool


def video_duration(path: Path) -> float:
    data = json.loads(run_process([require_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], timeout=30))
    return float(data.get("format", {}).get("duration") or 0)


def capture(path: Path, destination: Path, label: str, start: float = 0.0, clip_duration: float | None = None) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    length = clip_duration if clip_duration is not None else video_duration(path)
    outputs = []
    fractions = (0.0, 0.2, 0.4, 0.6, 0.8, 0.98)
    for index, fraction in enumerate(fractions, 1):
        point = start + min(max(0.0, length - 0.1), length * fraction)
        output = destination / f"{label}_{index:02d}_{point:.2f}s.png"
        run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{point:.3f}", "-i", str(path), "-frames:v", "1", str(output)], timeout=60)
        outputs.append(output)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    outputs = capture(args.video, args.out, args.label, args.start, args.duration)
    print(json.dumps({"video": str(args.video), "frames": [str(path) for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
