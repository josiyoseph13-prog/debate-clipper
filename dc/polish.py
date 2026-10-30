from __future__ import annotations

from typing import Any


def tight_cut_edits(words: list[dict[str, Any]], min_pause_s: float = 1.2, target_pause_s: float = 0.35, max_fraction: float = 0.15) -> list[dict[str, float]]:
    edits = []
    for previous, current in zip(words, words[1:]):
        gap = float(current["start"]) - float(previous["end"])
        speaker = previous.get("speaker")
        if gap > min_pause_s and speaker and speaker != "unknown" and speaker == current.get("speaker"):
            # Retain half of the target silence at each side of the cut;
            # only the strictly word-free center is removed.
            edits.append({"start": float(previous["end"]) + target_pause_s/2, "end": float(current["start"]) - target_pause_s/2, "removed_s": gap - target_pause_s, "kind": "silence_only"})
    total = sum(max(0, edit["removed_s"]) for edit in edits)
    duration = max(0.001, float(words[-1]["end"] - words[0]["start"])) if words else 1
    return edits if total / duration <= max_fraction else []


def punch_in_beats(beats: list[float], duration: float, max_zoom: float = 1.06, min_gap: float = 6.0) -> list[dict[str, float]]:
    result = []
    last = -min_gap
    for beat in sorted(float(value) for value in beats):
        if 0 <= beat <= duration and beat - last >= min_gap:
            result.append({"start": max(0, beat - 0.3), "beat": beat, "end": min(duration, beat + 0.6), "zoom": max_zoom})
            last = beat
    return result


def nameplate(name: str, start: float, show_s: float = 1.2) -> dict[str, Any]:
    return {"schema_version": 5, "name": name, "start": start, "end": start + show_s, "manual_label": True}


def apply_polish(plan: dict, transcript: dict, config) -> dict:
    from .captions import transcript_words
    from .timeline import kept_spans
    from .framing import rect_at
    from .layout import validate_framing_rect
    words = [word for word in transcript_words(transcript) if plan["trim"]["start"] <= word["start"] and word["end"] <= plan["trim"]["end"]]
    result = {"schema_version": 5, "punch_ins": [], "tight_cut": [], "nameplates": [], "audio": config.get("audio", default={}), "warnings": []}
    if config.get("polish", "tight_cut", "enabled", default=False) and not plan.get("receipt"):
        result["tight_cut"] = tight_cut_edits(words, **{key: config.get("polish", "tight_cut", key, default=value) for key, value in (("min_pause_s", 1.2), ("max_fraction", .15))}, target_pause_s=config.get("polish", "tight_cut", "to_s", default=.35))
        if result["tight_cut"]:
            spans = kept_spans(plan["trim"]["start"], plan["trim"]["end"], result["tight_cut"])
            plan["source_spans"] = spans
            plan["original_trim"] = dict(plan["trim"])
            plan["trim"]["duration"] = sum(span["end"] - span["start"] for span in spans)
            plan["edits"] = result["tight_cut"]
            plan["edited"] = True
    mode = plan["framing"]["segments"][0]["mode"]
    if config.get("polish", "punch_in", "enabled", default=False) and mode in {"SINGLE", "MANUAL"}:
        beats = [max(0, word["start"] - plan["trim"]["start"]) for word in words if word["text"].lower().strip(".,!?") in {"no", "never", "actually", "because"} or any(char.isdigit() for char in word["text"])]
        zoom = float(config.get("polish", "punch_in", "max_zoom", default=1.06))
        base = plan["framing"]["path"]
        if config.regions["feed"]["h"] / min(row["h"] for row in base) * zoom <= config.get("framing", "s_max", default=1.5):
            result["punch_ins"] = punch_in_beats(beats, plan["trim"]["duration"], zoom)
            path = []
            duration = plan["trim"]["duration"]
            for index in range(int(duration * 10) + 1):
                t = min(duration, index / 10)
                rect = rect_at(base, t)
                active = next((beat for beat in result["punch_ins"] if beat["start"] <= t <= beat["end"]), None)
                scale = 1 + (zoom - 1) * min(1, (t-active["start"])/.6, (active["end"]-t)/.2) if active else 1
                width, height = rect["w"] / scale, rect["h"] / scale
                path.append({"t": t, "x": rect["x"] + (rect["w"]-width)/2, "y": rect["y"] + (rect["h"]-height)/2, "w": width, "h": height})
            plan["framing"]["path"] = path
            plan["edited"] = bool(result["punch_ins"]) or plan.get("edited", False)
        else:
            result["warnings"].append("PUNCH_IN_UPSCALE_BUDGET")
    labels = plan.get("speaker_labels", {})
    if config.get("polish", "nameplates", "enabled", default=False):
        seen = set()
        for word in words:
            speaker = word.get("speaker")
            if speaker and speaker != "unknown" and speaker in labels and speaker not in seen:
                result["nameplates"].append(nameplate(labels[speaker], max(0, word["start"] - plan["trim"]["start"]), config.get("polish", "nameplates", "show_s", default=1.2)))
                seen.add(speaker)
    result["edited"] = plan.get("edited", False)
    plan["polish"] = result
    return result


def split_series(candidate: dict, transcript: dict, maximum_parts: int = 3) -> list[dict]:
    from .selection import context_sufficiency
    if candidate["end"] - candidate["start"] <= 75:
        return [candidate]
    boundaries = [candidate["start"]]
    sentences = [row for row in transcript.get("segments", []) if candidate["start"] <= row["start"] and row["end"] <= candidate["end"] and str(row.get("text", "")).endswith((".", "?", "!"))]
    for index in range(1, maximum_parts):
        target = candidate["start"] + (candidate["end"] - candidate["start"]) * index / maximum_parts
        if sentences:
            boundary = min(sentences, key=lambda row: abs(row["end"] - target))["end"]
            if boundary - boundaries[-1] > 8 and candidate["end"] - boundary > 8:
                boundaries.append(boundary)
    boundaries.append(candidate["end"])
    parts = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        text = " ".join(row.get("text", "") for row in sentences if start <= row["start"] and row["end"] <= end)
        flags = list(candidate.get("integrity_flags", []))
        if not context_sufficiency(text)["passed"]:
            flags.append({"code": "I-2", "severity": "review", "reason": "Series part needs independent context"})
        parts.append({**candidate, "id": f"{candidate['id']}_part{index+1}", "start": start, "end": end, "duration": end-start, "text": text, "series": {"part": index+1, "total": len(boundaries)-1}, "integrity_flags": flags})
    return parts
