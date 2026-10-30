from __future__ import annotations

import math
from typing import Any

from .core.config import AppConfig
from .layout import crop_rect, validate_framing_rect, upscale_policy


def smooth_path(points: list[dict[str, float]], tau: float = 0.35) -> list[dict[str, float]]:
    if not points:
        return []
    output = [dict(points[0])]
    for point in points[1:]:
        previous = output[-1]
        dt = max(0.0, point["t"] - previous["t"])
        alpha = 1 - math.exp(-dt / max(tau, 0.001))
        output.append({"t": point["t"], **{key: previous[key] + alpha * (point[key] - previous[key]) for key in ("x", "y", "w", "h")}})
    return output


def framing_plan(source_w: int, source_h: int, duration: float, config: AppConfig, mode: str = "auto", manual_regions: list[dict[str, float]] | None = None) -> dict[str, Any]:
    if mode == "manual":
        if not manual_regions:
            raise ValueError("Manual mode needs source-coordinate rectangles")
        for region in manual_regions:
            if not validate_framing_rect(region, source_w, source_h):
                raise ValueError("Manual crop leaves source frame")
            expected_ratio = config.regions["feed"]["w"] / config.regions["feed"]["h"]
            if abs(region["w"] / region["h"] - expected_ratio) > expected_ratio * .001:
                raise ValueError("Manual crop must preserve the feed aspect ratio")
        rect = dict(manual_regions[0])
        return {"schema_version": 5, "segments": [{"t0": 0, "t1": duration, "mode": "MANUAL", "regions": manual_regions, "confidence": 1.0, "reasons": ["MANUAL_LOCK"]}], "path": [{"t": 0, **rect}, {"t": duration, **rect}], "debug": {"source_w": source_w, "source_h": source_h}}
    if mode == "dual":
        panel_height = config.regions["feed"]["h"] / 2
        half_w = max(2, int(source_w // 2))
        panel_h = max(2, int(round(half_w / (16 / 9))))
        if panel_h > source_h:
            panel_h = source_h - (source_h % 2)
            half_w = max(2, int(round(panel_h * (16 / 9))))
        top = {"x": 0.0, "y": float(max(0, (source_h - panel_h) / 2)), "w": float(half_w), "h": float(panel_h), "scale": panel_height / panel_h, "upscale_factor": panel_height / panel_h}
        bottom = {"x": float(source_w - half_w), "y": top["y"], "w": float(half_w), "h": float(panel_h), "scale": panel_height / panel_h, "upscale_factor": panel_height / panel_h}
        return {"schema_version": 5, "segments": [{"t0": 0, "t1": duration, "mode": "DUAL", "regions": [top, bottom], "confidence": 0.25, "reasons": ["MANUAL_DUAL_REQUEST"]}], "path": [{"t": 0, **top}, {"t": duration, **top}], "debug": {"source_w": source_w, "source_h": source_h, "fallback": False}}
    rect = crop_rect(source_w, source_h, config)
    scale = rect["upscale_factor"]
    # No unverified active-speaker evidence is allowed to create a confident crop.
    selected_mode = "WIDE" if mode == "auto" or scale > 2.0 else mode.upper()
    reasons = ["NO_LANDMARKS"] if mode == "auto" else []
    if scale > 2:
        reasons.append("UPSCALE_BUDGET")
    policy=upscale_policy(source_w,source_h,config)
    return {"schema_version": 5, "segments": [{"t0": 0, "t1": duration, "mode": selected_mode, "regions": [rect], "confidence": 0.35 if selected_mode == "WIDE" else 1.0, "reasons": reasons, "upscale_factor": scale, "upscale_policy": policy["action"]}], "path": [{"t": 0, **rect}, {"t": duration, **rect}], "debug": {"source_w": source_w, "source_h": source_h, "exclusion_level": "none", "fallback": selected_mode == "WIDE", "upscale_policy": policy}}


def rate_limit_path(points: list[dict[str, float]], cut_times=(), source_w: float | None = None, source_h: float | None = None, max_pan: float = 180.0, max_zoom: float = 0.18, deadband_px: float = 0.0) -> list[dict[str, float]]:
    """Clamp a camera path to the export QA motion limits: at most
    max_pan px/s on any rect corner axis and at most max_zoom
    fraction/s of crop-size change, the quantities framing_quality
    measures. Steps are scaled toward the target, never overshot, so
    both corner-axis rates and the rect-center speed stay in limits.

    A step is an authored cut -- passed through instantly -- only when
    it lands on a time in ``cut_times`` (planner segment boundaries,
    scene cuts) or carries a duplicate/non-increasing timestamp, the
    path convention for authored joins. Cuts are re-encoded as a
    duplicate-timestamp join (previous rect held to the cut time, new
    rect at the same time), matching how existing planners write them.
    A step is never treated as a cut because it is large: tracking
    corrections, gaps, and noise are clamped like any other move.
    Rects are kept inside the source when its dimensions are given.
    """
    if not points:
        return []

    def clamped(rect):
        x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
        if source_w is not None:
            x = min(max(0.0, x), max(0.0, source_w - w))
        if source_h is not None:
            y = min(max(0.0, y), max(0.0, source_h - h))
        return {"t": rect["t"], "x": x, "y": y, "w": w, "h": h}

    cuts = sorted(float(c) for c in cut_times)
    output: list[dict[str, float]] = []
    previous = None
    pending_dir, pending_t = None, 0.0
    for point in points:
        target = clamped({"t": float(point["t"]), "x": float(point["x"]), "y": float(point["y"]),
                          "w": float(point["w"]), "h": float(point["h"])})
        if previous is None:
            output.append(target)
            previous = target
            continue
        dt = target["t"] - previous["t"]
        is_cut = dt <= 0 or any(previous["t"] + 1e-9 < c <= target["t"] + 1e-9 for c in cuts)
        if is_cut:
            if target["t"] > previous["t"]:
                output.append({**previous, "t": target["t"]})
            output.append(target)
            previous = target
            pending_dir, pending_t = None, 0.0
            continue
        aim = dict(target)
        if deadband_px > 0:
            pcx, pcy = previous["x"] + previous["w"] / 2, previous["y"] + previous["h"] / 2
            dx, dy = aim["x"] + aim["w"] / 2 - pcx, aim["y"] + aim["h"] / 2 - pcy
            if math.hypot(dx, dy) < deadband_px:
                direction = (round(dx), round(dy))
                if direction == pending_dir:
                    pending_t += dt
                else:
                    pending_dir, pending_t = direction, dt
                if pending_t < 0.5:
                    aim["x"] += pcx - (aim["x"] + aim["w"] / 2)
                    aim["y"] += pcy - (aim["y"] + aim["h"] / 2)
            else:
                pending_dir, pending_t = None, 0.0
        scale = 1.0
        budget = max_pan * (1 - 1e-9) * dt
        for delta in (aim["x"] - previous["x"], aim["y"] - previous["y"],
                      (aim["x"] + aim["w"]) - (previous["x"] + previous["w"]),
                      (aim["y"] + aim["h"]) - (previous["y"] + previous["h"])):
            if abs(delta) > budget:
                scale = min(scale, budget / abs(delta))
        dcx = (aim["x"] + aim["w"] / 2) - (previous["x"] + previous["w"] / 2)
        dcy = (aim["y"] + aim["h"] / 2) - (previous["y"] + previous["h"] / 2)
        dist = math.hypot(dcx, dcy)
        if dist > budget:
            scale = min(scale, budget / dist)
        if aim["w"] != previous["w"]:
            ratio = abs(aim["w"] / previous["w"] - 1)
            if ratio > max_zoom * (1 - 1e-9) * dt:
                scale = min(scale, max_zoom * (1 - 1e-9) * dt / ratio)
        rect = clamped({"t": target["t"],
                        "x": previous["x"] + scale * (aim["x"] - previous["x"]),
                        "y": previous["y"] + scale * (aim["y"] - previous["y"]),
                        "w": previous["w"] + scale * (aim["w"] - previous["w"]),
                        "h": previous["h"] + scale * (aim["h"] - previous["h"])})
        output.append(rect)
        previous = rect
    return output


def rect_at(path: list[dict[str, float]], time: float) -> dict[str, float]:
    if not path:
        raise ValueError("Empty camera path")
    before = path[0]
    after = path[-1]
    for left, right in zip(path, path[1:]):
        if left["t"] <= time <= right["t"]:
            before, after = left, right
            break
    if time <= path[0]["t"]:
        return dict(path[0])
    if time >= path[-1]["t"]:
        return dict(path[-1])
    weight = (time - before["t"]) / max(1e-9, after["t"] - before["t"])
    return {"t": time, **{key: before[key] + weight * (after[key] - before[key]) for key in ("x", "y", "w", "h")}}


def warp_subpixel(frame, rect: dict[str, float], output_w: int, output_h: int):
    import cv2
    import numpy as np

    source_h, source_w = frame.shape[:2]
    if not validate_framing_rect(rect, source_w, source_h):
        raise ValueError("Camera crop outside source")
    sx, sy = output_w / rect["w"], output_h / rect["h"]
    if abs(sx - sy) / max(sx, sy) > 0.001:
        raise ValueError("Non-uniform camera scale")
    matrix = np.array([[sx, 0, -rect["x"] * sx], [0, sy, -rect["y"] * sy]], dtype=np.float64)
    return cv2.warpAffine(frame, matrix, (output_w, output_h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)


def path_is_static(path: list[dict[str, float]], threshold: float = 0.25) -> bool:
    return all(max(row[key] for row in path) - min(row[key] for row in path) < threshold for key in ("x", "y", "w", "h")) if path else True


def framing_quality(plan: dict[str, Any]) -> dict[str, Any]:
    """Return human-readable camera checks without claiming unmeasured faces."""
    framing = plan.get("framing", {}) or {}
    path = framing.get("path", []) or []
    max_pan = 0.0
    max_zoom = 0.0
    cuts = 0
    moving = False
    moves = 0
    for left, right in zip(path, path[1:]):
        dt = float(right.get("t", 0)) - float(left.get("t", 0))
        if dt <= 0:
            cuts += 1
            moving = False
            continue
        changed = max(abs(float(right[key])-float(left[key])) for key in ("x","y","w","h")) > .05
        if changed and not moving:
            moves += 1
        moving = changed
        max_pan = max(max_pan, abs(float(right.get("x", 0)) - float(left.get("x", 0))) / dt, abs(float(right.get("y", 0)) - float(left.get("y", 0))) / dt)
        left_h = max(1e-6, float(left.get("h", 1)))
        right_h = max(1e-6, float(right.get("h", 1)))
        max_zoom = max(max_zoom, abs(right_h / left_h - 1.0) / dt)
    safe_wide = all(str(segment.get("mode", "")).upper() in {"WIDE", "DUAL"} for segment in framing.get("segments", []) or [])
    return {
        "face_visible": "Not measured; safe wide layout used." if safe_wide else "Not measured; human review required.",
        "face_in_safe_area": "Not measured; human review required.",
        "headroom": "Not measured",
        "speaker_size": "Not measured",
        "active_speaker_accuracy": "Not measured",
        "camera_moves": moves,
        "clean_cuts": cuts,
        "camera_jump": {"value_px_per_second": round(max_pan, 3), "limit_px_per_second": 180, "passed": max_pan <= 180},
        "zoom_change": {"value_fraction_per_second": round(max_zoom, 5), "limit_fraction_per_second": 0.18, "passed": max_zoom <= 0.18},
        "passed": max_pan <= 180 and max_zoom <= 0.18,
    }
