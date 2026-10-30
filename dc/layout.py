from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core.config import AppConfig


@dataclass(frozen=True)
class LayoutReport:
    passed: bool
    checks: list[dict[str, Any]]

    @property
    def errors(self) -> list[str]:
        return [str(check["name"]) for check in self.checks if not check["passed"]]


def validate_layout(config: AppConfig) -> LayoutReport:
    canvas = config.canvas
    regions = config.regions
    feed = regions["feed"]
    bottom = regions["bottom_white"]
    hook = regions["hook"]
    header = regions["header"]
    target_ratio = float(config.data.get("reference_feed_ratio", feed["w"] / feed["h"]))
    checks = [
        {"name": "canvas_fill", "passed": feed["y"] + feed["h"] + bottom["h"] == canvas["h"], "value": feed["y"] + feed["h"] + bottom["h"], "threshold": canvas["h"]},
        {"name": "feed_aspect", "passed": abs(feed["w"] / feed["h"] - target_ratio) < 0.002, "value": feed["w"] / feed["h"], "threshold": 0.002},
        {"name": "header_hook_separation", "passed": header["y"] + header["h"] <= hook["top_limit"], "value": header["y"] + header["h"], "threshold": hook["top_limit"]},
        {"name": "hook_before_feed", "passed": hook["bottom"] < feed["y"], "value": hook["bottom"], "threshold": feed["y"]},
        {"name": "hook_width", "passed": hook["w"] <= canvas["w"], "value": hook["w"], "threshold": canvas["w"]},
        {"name": "even_dimensions", "passed": all(int(v) % 2 == 0 for v in (canvas["w"], canvas["h"], feed["w"], feed["h"])), "value": True, "threshold": "all even"},
    ]
    return LayoutReport(all(item["passed"] for item in checks), checks)


def normalize_headline(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\n", " ")).strip()


def _measure(text: str, size: int, font_path: Path | None = None) -> tuple[int, int]:
    try:
        from PIL import ImageFont

        candidates = [font_path] if font_path else []
        candidates.extend([
            Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ])
        font = next((ImageFont.truetype(str(candidate), size) for candidate in candidates if candidate and candidate.exists()), ImageFont.load_default())
        box = font.getbbox(text)
        return max(0, box[2] - box[0]), max(1, box[3] - box[1])
    except Exception:
        return max(1, int(len(text) * size * 0.55)), size


def fit_headline(text: str, config: AppConfig, font_path: Path | None = None) -> dict[str, Any]:
    text = normalize_headline(text)
    hook = config.get("hook", default={})
    if font_path is None:
        root = Path(__file__).resolve().parents[1]
        configured = root / hook.get("font", "assets/fonts/Poppins-SemiBold.ttf")
        font_path = configured if configured.is_file() else root / "assets/fonts/Poppins-SemiBold.ttf"
    minimum, maximum = map(int, hook.get("px_range", [50, 40]))
    max_lines = int(hook.get("max_lines", 3))
    max_width = int(hook.get("max_w", 800))
    for size in range(minimum, maximum - 1, -1):
        words = text.split()
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and _measure(candidate, size, font_path)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if len(lines) <= max_lines and all(_measure(item, size, font_path)[0] <= max_width for item in lines):
            widths = [_measure(item, size, font_path)[0] for item in lines]
            return {"text": text, "lines": lines, "font_px": size, "width": max(widths, default=0), "height": int(len(lines) * size * float(hook.get("line_pitch", 1.04))), "fit": True}
    # A long title is still returned as a reviewable artifact, never silently truncated.
    size = maximum
    words = text.split()
    lines = [" ".join(words[i:i + max(1, math.ceil(len(words) / max_lines))]) for i in range(0, len(words), max(1, math.ceil(len(words) / max_lines)))]
    return {"text": text, "lines": lines[:max_lines], "font_px": size, "width": max_width, "height": int(max_lines * size), "fit": False}


def crop_rect(source_w: int, source_h: int, config: AppConfig, center_x: float | None = None, center_y: float | None = None, zoom: float = 1.0) -> dict[str, float]:
    feed = config.regions["feed"]
    target_ratio = float(feed["w"]) / float(feed["h"])
    zoom = max(1.0, float(zoom))
    crop_h = min(float(source_h), float(source_w) / target_ratio) / zoom
    crop_w = crop_h * target_ratio
    if crop_w > source_w:
        crop_w = float(source_w)
        crop_h = crop_w / target_ratio
    cx = float(center_x if center_x is not None else source_w / 2)
    cy = float(center_y if center_y is not None else source_h / 2)
    x = min(max(0.0, cx - crop_w / 2), max(0.0, source_w - crop_w))
    y = min(max(0.0, cy - crop_h / 2), max(0.0, source_h - crop_h))
    scale = float(feed["h"]) / crop_h
    return {"x": x, "y": y, "w": crop_w, "h": crop_h, "scale": scale, "upscale_factor": scale}


def upscale_policy(source_w: int, source_h: int, config: AppConfig, zoom: float = 1.0) -> dict[str, Any]:
    rect = crop_rect(source_w, source_h, config, zoom=zoom)
    scale = float(rect["upscale_factor"])
    if scale <= 1.5:
        action = "normal"
    elif scale <= 2.0:
        action = "soft_upscale"
    else:
        action = "prefer_wide_or_dual"
    return {"action": action, "upscale_factor": scale, "rect": rect, "normal_max": 1.5, "soft_max": 2.0, "zoom": float(zoom)}


def validate_framing_rect(rect: dict[str, float], source_w: int, source_h: int) -> bool:
    return rect["x"] >= 0 and rect["y"] >= 0 and rect["w"] > 0 and rect["h"] > 0 and rect["x"] + rect["w"] <= source_w + 1e-6 and rect["y"] + rect["h"] <= source_h + 1e-6
