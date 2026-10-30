from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .core.config import AppConfig
from .core.io import atomic_write_bytes, atomic_write_json
from .core.hashing import content_hash
from .core.process import ProcessCancelled, check_cancelled


def ass_color(rgb: str, alpha: int = 0) -> str:
    value = rgb.lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError(f"Invalid RGB colour: {rgb}")
    r, g, b = value[:2], value[2:4], value[4:]
    return f"&H{max(0, min(255, int(alpha))):02X}{b.upper()}{g.upper()}{r.upper()}&"


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(float(seconds) * 100)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole:02d}.{fraction:02d}"


def ass_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def transcript_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    if transcript.get("words"):
        source = transcript["words"]
    else:
        source = [word for segment in transcript.get("segments", []) for word in segment.get("words", [])]
    words = []
    for index, item in enumerate(source):
        if index % 128 == 0:
            check_cancelled()
        text = str(item.get("text", item.get("word", ""))).strip()
        start, end = float(item.get("start", 0)), float(item.get("end", 0))
        if not text or end <= start:
            continue
        words.append({"i": index, "text": text, "start": start, "end": end, "prob": float(item.get("prob", item.get("probability", 1))), "speaker": item.get("speaker"), **({"entity_id": item["entity_id"]} if item.get("entity_id") is not None else {})})
    return [{**word, "i": index} for index, word in enumerate(sorted(words, key=lambda row: (row["start"], row["end"])))]


def group_words(words: list[dict[str, Any]], config: AppConfig) -> list[list[dict[str, Any]]]:
    maximum = int(config.get("captions", "max_group_chars", default=16))
    pause = float(config.get("captions", "pause_hide_s", default=0.6))
    # Group protected phrases without combining source tokens: each word still
    # needs its own active interval, including short articles/prepositions.
    units: list[list[dict[str, Any]]] = []
    attach = {"a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "from", "with"}
    unit_terms = {"percent", "percentage", "million", "billion", "trillion", "dollars", "years", "months", "days", "kg", "km", "mph", "%"}
    def protected(left, right):
        a, b = str(left["text"]).strip(".,!?;:"), str(right["text"]).strip(".,!?;:")
        number_unit = bool(re.search(r"\d", a)) and b.lower() in unit_terms
        name_parts = a.istitle() and b.istitle() and a.lower() not in attach | {"i", "why", "what", "how", "one", "this", "that", "we", "you"}
        explicit = left.get("entity_id") is not None and left.get("entity_id") == right.get("entity_id")
        return not str(left["text"]).endswith((".", "?", "!")) and (a.lower() in attach or number_unit or name_parts or explicit)
    for word in words:
        previous = units[-1][-1] if units else None
        if previous and word["start"] - previous["end"] <= pause and previous.get("speaker") == word.get("speaker") and protected(previous, word):
            units[-1].append(word)
        else:
            units.append([word])
    groups, current = [], []
    for unit in units:
        gap = unit[0]["start"] - current[-1]["end"] if current else 0
        prospective = " ".join(item["text"] for item in [*current, *unit])
        speaker_change = current and current[-1].get("speaker") != unit[0].get("speaker")
        if current and (len(current) + len(unit) > 3 or len(prospective) > maximum or gap > pause or speaker_change):
            groups.append(current)
            current = []
        current.extend(unit)
    if current:
        groups.append(current)
    minimum=float(config.get("captions","min_group_s",default=.30))
    def duration(group):return group[-1]["end"]-group[0]["start"]+.15
    def compatible(left,right):
        return left[-1].get("speaker")==right[0].get("speaker") and right[0]["start"]-left[-1]["end"]<=pause
    index=0
    while index<len(groups):
        group=groups[index]
        if duration(group)<minimum:
            # Rebalance a short group using real neighbouring words, preserving
            # protected pairs and source order. Do not stretch active timings.
            if index+1<len(groups) and compatible(group,groups[index+1]):
                nxt=groups[index+1]
                take=1
                while take<len(nxt) and protected(nxt[take-1],nxt[take]):take+=1
                trial=group+nxt[:take]
                if len(trial)<=3 and len(" ".join(word["text"] for word in trial))<=maximum and (take==len(nxt) or duration(nxt[take:])>=minimum):
                    groups[index]=trial
                    if take==len(nxt):groups.pop(index+1)
                    else:groups[index+1]=nxt[take:]
            if duration(groups[index])<minimum and index>0 and compatible(groups[index-1],groups[index]):
                previous=groups[index-1]
                take=len(previous)-1
                while take>0 and protected(previous[take-1],previous[take]):take-=1
                trial=previous[take:]+groups[index]
                if len(trial)<=3 and len(" ".join(word["text"] for word in trial))<=maximum and (take==0 or duration(previous[:take])>=minimum):
                    groups[index]=trial
                    if take==0:
                        groups.pop(index-1)
                        index-=1
                    else:groups[index-1]=previous[:take]
        index+=1
    return groups


def caption_text(text: str) -> str:
    """Strip sentence punctuation, retaining decimals, currency and contractions."""
    return re.sub(r"[^\w'’%$€£¥.,+\- ]", "", str(text)).rstrip(".,").upper()


def boxes_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def solve_caption_slot(config: AppConfig, exclusions: list[tuple[float, float, float, float]] | None = None, width: float = 600, height: float = 60) -> dict[str, Any]:
    exclusions = exclusions or []
    center_x = float(config.get("captions", "center_x", default=config.canvas["w"] / 2))
    ladder = config.get("captions", "slot_ladder", default=[config.regions["feed"]["y"] + config.regions["feed"]["h"] / 2])
    from .core.config import load_safe_zones
    profile = load_safe_zones().get(config.get("safe_zone", "profile", default="balanced"), {})
    bottom_max = min(float(config.get("captions", "bottom_max", default=config.canvas["h"])), config.canvas["h"] - float(profile.get("bottom", 440)))
    halo = float(config.get("captions", "halo_px", default=45))
    for center_y in ladder:
        box = (center_x - width / 2, float(center_y) - height / 2, width, height)
        if box[1] - halo < config.regions["feed"]["y"] or box[1] + height + halo > bottom_max:
            continue
        if not any(boxes_intersect(box, exclusion) for exclusion in exclusions):
            return {"x": center_x, "y": float(center_y), "box": list(box), "review": False, "plate": False}
    # Stay inside the feed; make the failure explicit so QA cannot mark it passed.
    fallback_y = min(bottom_max - height / 2 - halo, max(config.regions["feed"]["y"] + height / 2 + halo, float(ladder[0])))
    return {"x": center_x, "y": fallback_y, "box": [center_x - width / 2, fallback_y - height / 2, width, height], "review": True, "plate": True}


def build_captions(transcript: dict[str, Any], start: float, end: float, config: AppConfig, output_path: Path, exclusions: list[tuple[float, float, float, float]] | None = None, suppress:bool=False, suppress_reason: str = "Explicit user trust_source_captions setting; source text accuracy is unverified") -> dict[str, Any]:
    selected = [word for word in transcript_words(transcript) if word["end"] > start and word["start"] < end]
    words = [{**word, "start": max(word["start"], start) - start, "end": min(word["end"], end) - start} for word in selected]
    groups = group_words(words, config)
    caption = config.data["captions"]
    feed = config.regions["feed"]
    font_family = caption["font_family"]
    configured_font = Path(config.path).parent.parent / caption.get("font_file", "")
    if not configured_font.exists() and (Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf").exists():
        font_family = "Inter"
    calibration = calibrate_caption(config)
    size = float(caption.get("font_size_override", calibration.get("font_size", caption.get("font_size", 110))))
    scale_x = float(calibration.get("scale_x", caption.get("scale_x", 92)))
    try:
        from PIL import ImageFont

        font_path = configured_font if configured_font.exists() else Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf"
        font = ImageFont.truetype(str(font_path), int(round(size)))
        # Pillow px and libass fs have different cap scales. Use the calibrated
        # RIGHT width to convert advances rather than squeezing the whole clip.
        advance_ratio = float(calibration.get("measurement", {}).get("width", caption.get("target_word_w_RIGHT", 172))) / max(1, font.getlength("RIGHT"))
    except Exception:
        font = None
        advance_ratio = scale_x / 100
    dy = float(caption.get("dy_override", calibration.get("dy", caption.get("dy", 6.5))))
    slot = solve_caption_slot(config, exclusions, width=float(caption.get("max_w", 800)))
    local_y = slot["y"] - feed["y"] + dy
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {feed['w']}
PlayResY: {feed['h']}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font_family},{size},{ass_color(caption['base'])},{ass_color(caption['active'])},{ass_color(caption['stroke'])},&H00000000,-1,0,0,0,{scale_x},100,0,0,1,{caption['stroke_px']},{caption['shadow_px']},5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    fitting_warnings=[]
    plan_events = []
    plan_groups = []
    style = config.get("craft", "caption_mode", default=caption.get("style", "hormozi_glow"))
    if style == "gravitas":
        # Sentence-level mode still wraps to measured word groups; a full
        # sentence stays on screen as at most two bounded lines, no word pops.
        sentence_groups, current = [], []
        for word in words:
            current.append(word)
            if word["text"].rstrip().endswith((".", "?", "!")) or len(current) >= 12:
                sentence_groups.append(current)
                current = []
        if current:
            sentence_groups.append(current)
        groups = sentence_groups
    for group in groups:
        group_index = len(plan_groups)
        group_start = max(0.0, group[0]["start"] - 0.03)
        group_end = min(end - start, group[-1]["end"] + 0.12)
        plan_groups.append({"start": group_start, "end": group_end, "word_ids": [word["i"] for word in group], "text": " ".join(word["text"] for word in group)})
        display = [caption_text(item["text"]) for item in group]
        group_scale = 1.0
        line_breaks = []
        if font is not None:
            available = float(caption.get("max_w", 800)) - 2 * float(caption.get("stroke_px", 5))
            current_line = []
            line_widths = []
            for token in display:
                trial = " ".join([*current_line, token])
                if current_line and font.getlength(trial) * advance_ratio > available:
                    line_widths.append(font.getlength(" ".join(current_line)) * advance_ratio)
                    line_breaks.append(len(current_line))
                    current_line = [token]
                else:
                    current_line.append(token)
            if current_line:
                line_widths.append(font.getlength(" ".join(current_line)) * advance_ratio)
            measured_width = max(line_widths or [0])
            pop_peak = float(caption.get("pop", {}).get("peak", 1.08)) if caption.get("pop", {}).get("enabled", True) else 1.0
            if measured_width * pop_peak > available:
                floor = float(caption.get("min_cap_px", 36)) / float(caption.get("target_cap_px", 44))
                group_scale = max(floor, available / max(1, measured_width * pop_peak))
                if measured_width * pop_peak * group_scale > available + 1:
                    fitting_warnings.append("CAPTION_TEXT_OVERFLOW")
        plan_groups[-1].update({"font_size":round(size*group_scale,3),"scale_x":scale_x,"word_count":len(group),"line_breaks":line_breaks,"line_count":len(line_breaks)+1})
        for active_index, word in enumerate(group):
            if style == "gravitas" and active_index > 0:
                continue
            event_start = max(0.0, word["start"] - 0.03)
            next_start = group_end if style == "gravitas" else (group[active_index + 1]["start"] - 0.03 if active_index + 1 < len(group) else word["end"] + 0.12)
            next_group = groups[group_index + 1] if group_index + 1 < len(groups) else None
            if next_group:
                next_start = min(next_start, next_group[0]["start"] - 0.03)
            event_end = min(end - start, next_start)
            if event_end <= event_start:
                continue
            if style == "gravitas":
                display = [item["text"] for item in group]
            position = rf"\an5\pos({slot['x']:.1f},{local_y:.1f})\fs{size*group_scale:.3f}\fscx{scale_x}"
            active_colour = caption["base"] if style == "gravitas" else caption["active"]
            emphasis_terms = {"no", "not", "never", "none", "nothing"}
            body_parts = []
            emphasis_used = False
            for index, text in enumerate(display):
                plain = text.lower()
                emphasize = index != active_index and not emphasis_used and (plain in emphasis_terms or any(char.isdigit() for char in plain))
                colour = active_colour if index == active_index else (caption["emphasis"] if emphasize else caption["base"])
                emphasis_used = emphasis_used or emphasize
                prefix = r"\N" if index in line_breaks else ("" if index == 0 else " ")
                body_parts.append(prefix + r"{\c" + ass_color(colour) + "}" + ass_escape(text))
            body = "".join(body_parts)
            if style == "gravitas":
                from .layout import _measure
                sentence=" ".join(display)
                requested=int(caption.get("gravitas_font_size",55))
                minimum=int(caption.get("gravitas_min_font_size",36))
                fitted_lines=[]
                for sentence_size in range(requested,minimum-1,-1):
                    fitted_lines=[]
                    current=""
                    for token in sentence.split():
                        trial=(current+" "+token).strip()
                        if current and _measure(trial,sentence_size,font_path)[0]>caption.get("max_w",800):
                            fitted_lines.append(current)
                            current=token
                        else:current=trial
                    if current:fitted_lines.append(current)
                    if len(fitted_lines)<=2 and all(_measure(line,sentence_size,font_path)[0]<=caption.get("max_w",800) for line in fitted_lines):break
                if len(fitted_lines)>2 or any(_measure(line,sentence_size,font_path)[0]>caption.get("max_w",800) for line in fitted_lines):
                    fitting_warnings.append("GRAVITAS_TEXT_OVERFLOW")
                body=r"{\c"+ass_color(caption["base"])+"}"+r"\N".join(ass_escape(line) for line in fitted_lines)
                position += rf"\fs{sentence_size}\fscx100"
            pop = ""
            if style == "hormozi_glow" and caption.get("pop", {}).get("enabled", True) and (len(group) == 1 or active_index == 0):
                pop = rf"\fscx{scale_x * .82:.2f}\fscy82\t(0,90,\fscx{scale_x * 1.08:.2f}\fscy108)\t(90,170,\fscx{scale_x}\fscy100)"
            if style == "hormozi_glow":
                glow = caption["glow"]
                for layer, bord, blur, alpha in ((0, glow["outer_bord"], glow["outer_blur"], glow["outer_alpha"]), (1, glow["inner_bord"], glow["inner_blur"], glow["inner_alpha"])):
                    glow_body = " ".join((r"{\alpha" + (f"&H{int(alpha):02X}&" if index == active_index else "&HFF&") + "}" + ass_escape(text)) for index, text in enumerate(display))
                    tags = position + pop + rf"\c{ass_color(caption['active'])}\3c{ass_color(caption['active'])}\bord{bord}\blur{blur}\shad0"
                    events.append(f"Dialogue: {layer},{ass_time(event_start)},{ass_time(event_end)},Main,,0,0,0,,{{{tags}}}{glow_body}")
            events.append(f"Dialogue: 2,{ass_time(event_start)},{ass_time(event_end)},Main,,0,0,0,,{{{position}{pop}}}{body}")
            if slot["plate"]:
                # ASS vector plate is behind the same group, clipped by feed.
                width, height = float(caption.get("max_w", 800)), 90
                alpha = int(255 * (1 - float(caption.get("plate_fallback", {}).get("alpha", .6))))
                plate = rf"{{\an7\pos({slot['x']-width/2:.1f},{local_y-height/2:.1f})\p1\bord0\shad0\c&H000000&\alpha&H{alpha:02X}&}}m 0 0 l {width} 0 {width} {height} 0 {height}"
                events.append(f"Dialogue: -1,{ass_time(event_start)},{ass_time(event_end)},Main,,0,0,0,,{plate}")
            plan_events.append({"start": event_start, "end": event_end, "active_word": word["i"], "text": " ".join(display), "slot": slot, "group": group_index})
    warnings = ["CAPTION_REVIEW"] if slot["review"] else []
    warnings.extend(sorted(set(fitting_warnings)))
    if calibration.get("status")!="calibrated":
        warnings.append("CAPTION_CALIBRATION_UNVERIFIED")
    if not configured_font.is_file():
        warnings.append("FONT_FALLBACK")
    if any(group["end"] - group["start"] < float(caption.get("min_group_s", .30)) - 1e-6 for group in plan_groups):
        warnings.append("SHORT_CAPTION_GROUP")
    plan = {"schema_version": 5, "start": start, "end": end, "words": words, "events": plan_events, "groups": plan_groups, "slot": slot, "font": font_family, "font_size": size, "scale_x": scale_x, "dy": dy, "style": style, "warnings": warnings}
    if suppress:
        events=[]
        plan.update({"events":[],"groups":[],"warnings":["SOURCE_CAPTIONS_TRUST_REVIEW"],"suppressed":True,"suppression_reason":suppress_reason})
    atomic_write_bytes(output_path, (header + "\n".join(events) + "\n").encode("utf-8"))
    atomic_write_json(output_path.with_name("captions_plan.json"), plan)
    return plan


def build_ass(transcript: dict[str, Any], clip_start: float, clip_end: float, output_path: Path, **_: Any) -> Path:
    """Compatibility entry point for callers of the earlier caption module."""
    from .core.config import load_config

    build_captions(transcript, clip_start, clip_end, load_config(), Path(output_path))
    return Path(output_path)


def calibrate_caption(config: AppConfig, cache_path: Path | None = None) -> dict[str, Any]:
    """Measure libass fill geometry; retain an explicit Pillow-only fallback."""
    from .core.hashing import file_hash

    font_path = Path(config.path).parent.parent / config.get("captions", "font_file", default="")
    if not font_path.exists():
        result = {"schema_version": 5, "status": "missing_font", "font": str(font_path), "backend": "pillow-preflight"}
        if cache_path:
            atomic_write_json(cache_path, result)
        return result
    from .core.tools import find_tool
    from .core.process import run_process
    from .core.io import read_json
    from .core.config import ROOT
    import os
    import tempfile
    ffmpeg = find_tool("ffmpeg")
    style_key = content_hash({"font": file_hash(font_path), "family": config.get("captions", "font_family"), "target": [config.get("captions", "target_cap_px", default=44), config.get("captions", "target_word_w_RIGHT", default=172)], "ffmpeg": run_process([ffmpeg, "-version"], timeout=10, output_limit=4000) if ffmpeg else None, "version": 2})
    cache_path = cache_path or ROOT / "config" / "caption_calibration.json"
    cached = read_json(cache_path, {}) or {}
    if cached.get("cache_key") == style_key and cached.get("status") == "calibrated":
        return cached
    if ffmpeg:
        try:
            from PIL import Image
            import numpy as np
            (ROOT / "work").mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="calibration_", dir=ROOT / "work") as folder:
                work = Path(folder)
                feed = config.regions["feed"]
                center_x, center_y = feed["w"] / 2, feed["h"] / 2
                family = config.get("captions", "font_family")
                fonts = os.path.relpath(font_path.parent, work).replace("\\", "/")
                size, scale_x, dy = 110.0, 92.0, 0.0
                measurement = None
                for _ in range(4):
                    ass = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {feed['w']}\nPlayResY: {feed['h']}\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Cal,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,{scale_x},100,0,0,1,0,0,5,0,0,0,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:01.00,Cal,,0,0,0,,{{\\an5\\pos({center_x},{center_y+dy})}}RIGHT\n"
                    (work / "cal.ass").write_text(ass, encoding="utf-8")
                    render_log = run_process([ffmpeg, "-hide_banner", "-loglevel", "info", "-y", "-f", "lavfi", "-i", f"color=c=black:s={feed['w']}x{feed['h']}", "-vf", f"subtitles=cal.ass:fontsdir={fonts}", "-frames:v", "1", "cal.png"], cwd=work, timeout=30)
                    with Image.open(work / "cal.png") as image:
                        pixels = np.asarray(image.convert("RGB"))
                    rows, columns = np.where(np.min(pixels, axis=2) >= 220)
                    if not len(rows):
                        raise RuntimeError("libass produced no fill pixels")
                    width, height = int(columns.max() - columns.min() + 1), int(rows.max() - rows.min() + 1)
                    measured_y = float((rows.max() + rows.min()) / 2)
                    measurement = {"width": width, "cap_height": height, "center_x": float((columns.max() + columns.min()) / 2), "center_y": measured_y}
                    target_w, target_h = float(config.get("captions", "target_word_w_RIGHT", default=172)), float(config.get("captions", "target_cap_px", default=44))
                    if abs(height - target_h) <= 1 and abs(width - target_w) <= 1 and abs(measured_y - center_y) <= 1:
                        break
                    ratio = target_h / height
                    size *= ratio
                    scale_x *= target_w / width / ratio
                    dy += center_y - measured_y
                measured_ok = abs(measurement["width"] - target_w) <= 3 and abs(measurement["cap_height"] - target_h) <= 3 and abs(measurement["center_y"] - center_y) <= 3
                result = {"schema_version": 5, "status": "calibrated" if measured_ok else "calibration_failed", "backend": "libass-lossless", "cache_key": style_key, "font": str(font_path), "font_sha256": file_hash(font_path), "font_size": round(size, 3), "scale_x": round(scale_x, 3), "dy": round(dy, 3), "measurement": measurement, "font_selection": [line for line in render_log.splitlines() if "fontselect:" in line],"shaper":[line for line in render_log.splitlines() if "Shaper:" in line]}
                atomic_write_json(cache_path, result)
                return result
        except ProcessCancelled:
            raise
        except Exception as exc:
            libass_error = str(exc)
    else:
        libass_error = "FFmpeg unavailable"
    try:
        from PIL import ImageFont

        font = ImageFont.truetype(str(font_path), 110)
        bbox = font.getbbox("RIGHT")
        result = {"schema_version": 5, "status": "pillow_preflight", "backend": "pillow", "font": str(font_path), "font_sha256": file_hash(font_path), "right_width": bbox[2] - bbox[0], "cap_height": bbox[3] - bbox[1], "target_width": config.get("captions", "target_word_w_RIGHT", default=172), "target_cap_height": config.get("captions", "target_cap_px", default=44)}
        result["libass_error"] = libass_error
    except Exception as exc:
        result = {"schema_version": 5, "status": "error", "font": str(font_path), "error": str(exc), "backend": "pillow-preflight"}
    if cache_path:
        atomic_write_json(cache_path, result)
    return result
