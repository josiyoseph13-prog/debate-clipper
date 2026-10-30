"""Manual framing pins (Phase 4C, master plan Sections 12.2-12.3).

A pin is a point in clip time carrying one framing: zoom, horizontal
and vertical move, and the preset it came from. The first pin always
sits at t=0. Export turns pins into MANUAL framing segments using the
same centre math dc/cli.py already used for the old static
framing_controls (centre = source centre + move * 25% of the source
dimension; rect from dc.layout.crop_rect), so the Edit preview and
the exported crop agree.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .core.config import AppConfig
from .layout import crop_rect

PRESETS = ("auto", "a", "b", "both", "wide", "custom")
SHAPES = ("9:16", "1:1", "16:9")
ZOOM_MIN, ZOOM_MAX = 1.0, 2.5
MOVE_LIMIT = 1.0


def default_pin(t: float = 0.0) -> dict[str, Any]:
    return {"t": float(t), "zoom": 1.0, "move_x": 0.0, "move_y": 0.0, "preset": "auto"}


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def normalize_pins(raw: Any, duration: float) -> list[dict[str, Any]]:
    """Clean an untrusted pins payload.

    An empty/absent input stays empty (that is how "no manual pins"
    is stored). A non-empty input is clamped, de-duplicated by time
    (last one wins), sorted, and guaranteed to contain a pin at 0.
    """
    if not isinstance(raw, list) or not raw:
        return []
    duration = max(0.0, float(duration or 0))
    by_time: dict[float, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            t = float(item.get("t", 0))
            zoom = float(item.get("zoom", 1.0))
            move_x = float(item.get("move_x", 0.0))
            move_y = float(item.get("move_y", 0.0))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (t, zoom, move_x, move_y)):
            continue
        preset = str(item.get("preset", "custom"))
        if preset not in PRESETS:
            preset = "custom"
        t = round(_clamp(t, 0.0, duration), 3)
        by_time[t] = {
            "t": t,
            "zoom": round(_clamp(zoom, ZOOM_MIN, ZOOM_MAX), 4),
            "move_x": round(_clamp(move_x, -MOVE_LIMIT, MOVE_LIMIT), 4),
            "move_y": round(_clamp(move_y, -MOVE_LIMIT, MOVE_LIMIT), 4),
            "preset": preset,
        }
    pins = [by_time[key] for key in sorted(by_time)]
    if pins and pins[0]["t"] != 0.0:
        pins.insert(0, default_pin(0.0))
    return pins


def pin_center(pin: dict[str, Any], source_w: float, source_h: float) -> tuple[float, float]:
    """Crop centre for a pin — the exact formula the render has always used."""
    return (
        float(source_w) / 2 + float(pin.get("move_x", 0.0)) * float(source_w) * 0.25,
        float(source_h) / 2 + float(pin.get("move_y", 0.0)) * float(source_h) * 0.25,
    )


def shape_config(config: AppConfig, shape: str | None) -> AppConfig:
    """Config variant whose feed region has the requested clip-shape ratio.

    Only the feed width changes (height kept): crop_rect reads just the
    feed ratio, so this steers crop aspect without touching the canvas
    or any other region. "9:16" is the production default and returns
    the config unchanged.
    """
    if not shape or shape == "9:16":
        return config
    ratios = {"1:1": 1.0, "16:9": 16 / 9}
    ratio = ratios.get(shape)
    if ratio is None:
        return config
    data = copy.deepcopy(config.data)
    feed = data["regions"]["feed"]
    feed["w"] = round(float(feed["h"]) * ratio)
    return AppConfig(data, config.path)


def shape_feed_config(config: AppConfig, shape: str | None) -> AppConfig:
    """Config variant whose feed region itself has the clip shape.

    The renderer refuses non-uniform crop scales (warp_subpixel), so a
    non-default shape cannot just change the crop aspect — the feed
    the crop is scaled into must have the same aspect. The canvas
    stays the production 1080x1920 brand canvas: the feed keeps its
    top position, takes the shape's height for the canvas width, and
    the bottom white region absorbs the difference. "9:16" returns
    the config unchanged.
    """
    if not shape or shape == "9:16":
        return config
    ratios = {"1:1": 1.0, "16:9": 16 / 9}
    ratio = ratios.get(shape)
    if ratio is None:
        return config
    data = copy.deepcopy(config.data)
    canvas = data["canvas"]
    feed = data["regions"]["feed"]
    feed_h = round(float(canvas["w"]) / ratio)
    feed["h"] = feed_h
    bottom = data["regions"].get("bottom_white")
    if bottom is not None:
        bottom["y"] = int(feed["y"]) + feed_h
        bottom["h"] = int(canvas["h"]) - int(bottom["y"])
    return AppConfig(data, config.path)


def pin_crop_rect(pin: dict[str, Any], source_w: int, source_h: int, config: AppConfig, shape: str | None = None) -> dict[str, float]:
    center_x, center_y = pin_center(pin, source_w, source_h)
    rect = crop_rect(int(source_w), int(source_h), shape_config(config, shape), center_x=center_x, center_y=center_y, zoom=float(pin.get("zoom", 1.0)))
    return {key: float(rect[key]) for key in ("x", "y", "w", "h")}


def pins_to_framing(pins: list[dict[str, Any]], source_w: int, source_h: int, duration: float, config: AppConfig, shape: str | None = None) -> dict[str, Any]:
    """Build a plan["framing"] dict whose segments switch at pin times.

    Segments are MANUAL with one region each; the path uses the same
    duplicate-timestamp step encoding as authored cuts elsewhere in
    the framing schema.
    """
    duration = max(0.0, float(duration or 0))
    rects = [pin_crop_rect(pin, source_w, source_h, config, shape) for pin in pins]
    segments = []
    for index, pin in enumerate(pins):
        t0 = float(pin["t"])
        t1 = float(pins[index + 1]["t"]) if index + 1 < len(pins) else duration
        if t1 <= t0:
            continue
        segments.append({
            "t0": t0, "t1": t1, "mode": "MANUAL",
            "regions": [rects[index]], "confidence": 1.0,
            "reasons": ["FRAMING_PIN"],
        })
    path: list[dict[str, Any]] = []
    for index, (pin, rect) in enumerate(zip(pins, rects)):
        t = float(pin["t"])
        if index > 0:
            path.append({"t": t, **rects[index - 1]})
        path.append({"t": t, **rect})
    if pins:
        path.append({"t": duration, **rects[-1]})
    return {
        "schema_version": 5,
        "segments": segments,
        "path": path,
        "debug": {"source_w": int(source_w), "source_h": int(source_h), "framing_pins": len(pins), "shape": shape or "9:16"},
    }


def _move_for_center(center: float, size: float) -> float:
    if size <= 0:
        return 0.0
    return round(_clamp((center - size / 2) / (size * 0.25), -MOVE_LIMIT, MOVE_LIMIT), 4)


def presets_from_tracking(observations: list[dict[str, Any]], t: float, source_w: int, source_h: int, config: AppConfig, shape: str | None = None) -> dict[str, Any]:
    """Person A / Person B / Both pin values from real face tracking.

    Tracks are ranked by their total observation count across the
    whole clip (the two most-seen people); each preset centres the
    crop on that track's median face position near time t. Returns
    available=False when no usable face is near t — callers must say
    so instead of inventing a position.
    """
    if not observations:
        return {"available": False, "reason": "no face tracking for this clip yet"}
    totals: dict[str, int] = {}
    for row in observations:
        totals[str(row.get("track"))] = totals.get(str(row.get("track")), 0) + 1
    ranked = [track for track, _ in sorted(totals.items(), key=lambda item: -item[1])]
    window = [row for row in observations if abs(float(row.get("t", -1e9)) - float(t)) <= 1.5]
    centers: dict[str, tuple[float, float, float]] = {}
    for track in ranked[:2]:
        rows = [row for row in window if str(row.get("track")) == track and isinstance(row.get("source_box"), (list, tuple)) and len(row["source_box"]) == 4]
        if not rows:
            continue
        boxes = sorted((float(r["source_box"][0]) + float(r["source_box"][2]) / 2, float(r["source_box"][1]) + float(r["source_box"][3]) / 2, float(r["source_box"][2])) for r in rows)
        mid = boxes[len(boxes) // 2]
        centers[track] = mid
    if not centers:
        return {"available": False, "reason": "no face is visible at this moment"}
    ordered = [centers[track] for track in ranked if track in centers]

    def pin_for(center_x: float, center_y: float, zoom: float, preset: str) -> dict[str, Any]:
        return {
            "zoom": round(_clamp(zoom, ZOOM_MIN, ZOOM_MAX), 4),
            "move_x": _move_for_center(center_x, float(source_w)),
            "move_y": _move_for_center(center_y, float(source_h)),
            "preset": preset,
        }

    result: dict[str, Any] = {"available": True, "a": None, "b": None, "both": None}
    if ordered:
        result["a"] = pin_for(ordered[0][0], ordered[0][1], 1.8, "a")
    if len(ordered) > 1:
        result["b"] = pin_for(ordered[1][0], ordered[1][1], 1.8, "b")
        span = abs(ordered[0][0] - ordered[1][0]) + (ordered[0][2] + ordered[1][2]) / 2
        base = pin_crop_rect(default_pin(), source_w, source_h, config, shape)
        zoom = float(base["w"]) / (span * 1.5) if span > 0 else 1.0
        result["both"] = pin_for((ordered[0][0] + ordered[1][0]) / 2, (ordered[0][1] + ordered[1][1]) / 2, zoom, "both")
    elif ordered:
        result["both"] = dict(result["a"], preset="both")
    return result
