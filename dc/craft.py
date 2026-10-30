from __future__ import annotations

import re
from typing import Any

from .captions import transcript_words
from .selection import _normal, _tokens, headline_fidelity


def prepare_emoji_pops(plan:dict,transcript:dict,config,work)->dict:
    """Optional raster glyphs, transcript anchors, and conservative collisions."""
    from .captions import boxes_intersect,solve_caption_slot
    from .chrome import emoji_image
    from .core.io import atomic_write_json
    selected=[word for word in transcript_words(transcript) if plan["trim"]["start"]<=word["start"]<plan["trim"]["end"]]
    manifest={"schema_version":5,"items":[],"warnings":[]}
    text=" ".join(word["text"] for word in selected).lower()
    if not config.get("craft","emoji_pops","enabled",default=False) or config.get("craft","caption_mode",default="hormozi_glow")=="gravitas" or re.search(r"\b(war|death|deaths|killed|abuse|election|voting|ballot)\b",text):
        plan["emoji_pops"]=[]
        atomic_write_json(work/"emoji_pops.json",manifest)
        return manifest
    topics={"education":"🎓","school":"🎓","college":"🎓","law":"⚖️","economy":"💰","government":"🏛️","immigration":"🛂","guns":"🔫","health":"🩺"}
    last=-float(config.get("craft","emoji_pops","min_gap_s",default=8))
    slot=solve_caption_slot(config,plan.get("caption_exclusions"),width=config.get("captions","max_w",default=800))
    feed=config.regions["feed"]
    for word in selected:
        token=re.sub(r"[^a-z]","",word["text"].lower())
        t=word["start"]-plan["trim"]["start"]
        if token not in topics or t-last<float(config.get("craft","emoji_pops","min_gap_s",default=8)):continue
        try:glyph=emoji_image(topics[token],int(config.get("craft","emoji_pops","px",default=55)),config)
        except (OSError,ValueError) as exc:
            manifest["warnings"].append("EMOJI_DROPPED: "+str(exc))
            continue
        x=int(slot["x"]-glyph.width/2)
        y=int(slot["box"][1]-config.get("captions","halo_px",default=45)-glyph.height-12)
        box=(x,y,glyph.width,glyph.height)
        if slot["review"] or y<feed["y"] or any(boxes_intersect(box,exclusion) for exclusion in plan.get("caption_exclusions",[])):
            manifest["warnings"].append("EMOJI_DROPPED_COLLISION")
            continue
        filename=f"emoji_pop_{len(manifest['items'])}.png"
        glyph.save(work/filename)
        manifest["items"].append({"glyph":topics[token],"word_i":word["i"],"text":word["text"],"start":t,"end":min(plan["trim"]["duration"],t+.8),"x":x,"y":y-feed["y"],"box":list(box),"file":filename})
        last=t
    plan["emoji_pops"]=manifest["items"]
    atomic_write_json(work/"emoji_pops.json",manifest)
    return manifest


def build_craft_ass(plan: dict, config, output_path):
    from .captions import ass_escape, ass_time
    from .core.io import atomic_write_bytes
    feed = config.regions["feed"]
    lines = [f"[Script Info]\nScriptType: v4.00+\nPlayResX: {feed['w']}\nPlayResY: {feed['h']}\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Chip,Poppins SemiBold,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H55000000,-1,0,0,0,100,100,0,0,3,12,0,7,0,0,0,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"]
    for item in plan.get("polish", {}).get("nameplates", []):
        lines.append(f"Dialogue: 0,{ass_time(item['start'])},{ass_time(item['end'])},Chip,,0,0,0,,{{\\pos(48,28)}}{ass_escape(item['name'])}\n")
    receipt = plan.get("receipt")
    if receipt:
        lines.append(f"Dialogue: 0,0:00:00.00,{ass_time(min(1.5,plan['trim']['duration']))},Chip,,0,0,0,,{{\\pos(48,28)}}{ass_escape(receipt['chip'])}\n")
    atomic_write_bytes(output_path, "".join(lines).encode("utf-8"))
    return output_path


def render_craft_overlay(plan: dict[str, Any], config, output_path, kind: str | None = None) -> Path:
    """Render transcript-derived chips/cards into a transparent feed layer."""
    from pathlib import Path

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required for craft overlays") from exc
    output_path = Path(output_path)
    feed = config.regions["feed"]
    image = Image.new("RGBA", (int(feed["w"]), int(feed["h"])), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Poppins-SemiBold.ttf"
    font = ImageFont.truetype(str(font_path), 30) if font_path.exists() else ImageFont.load_default()
    card_font = ImageFont.truetype(str(font_path), 40) if font_path.exists() else ImageFont.load_default()

    manifest={"schema_version":5,"items":[],"warnings":[]}
    def plate(x: int, y: int, text: str, label: str, selected_font):
        max_width = int(feed["w"] * 0.75)
        words = str(text).split()
        lines, line = [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and draw.textlength(candidate, font=selected_font) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if len(lines)>3:
            manifest["warnings"].append("CRAFT_TEXT_OVERFLOW")
            return
        line_height = int(selected_font.size * 1.2) if hasattr(selected_font, "size") else 36
        width = min(max_width, max([draw.textlength(item, font=selected_font) for item in lines], default=0) + 36)
        height = line_height * len(lines) + 54
        from .captions import boxes_intersect
        exclusions=plan.get("caption_exclusions",[])
        caption_band=(config.get("captions","x_limits",default=[140,940])[0],config.get("captions","center_y_canvas",default=feed["y"]+feed["h"]/2)-100,config.get("captions","max_w",default=800),200)
        candidates=[(x,y),(int(feed["w"]-width-48),y),(x,y+160),(x,feed["h"]-height-280)]
        placed=next(((px,py) for px,py in candidates if px>=0 and px+width<=feed["w"] and py>=0 and py+height<=feed["h"] and not any(boxes_intersect((px,py+feed["y"],width,height),box) for box in [*exclusions,caption_band])),None)
        if not placed:
            manifest["warnings"].append("CRAFT_NO_COLLISION_FREE_SLOT")
            return
        x,y=placed
        draw.rounded_rectangle((x, y, x + width, y + height), radius=14, fill=(0, 0, 0, 166))
        draw.text((x + 18, y + 12), label, font=font, fill="#B4F83D")
        for index, line_text in enumerate(lines):
            draw.text((x + 18, y + 42 + index * line_height), line_text, font=selected_font, fill="white")
        manifest["items"].append({"label":label,"text":text,"box":[x,y+feed["y"],width,height]})

    chip = plan.get("craft", {}).get("question_chip")
    if chip and kind != "evidence_card":
        plate(48, 48, chip.get("text", ""), "QUESTION", font)
    card = plan.get("craft", {}).get("evidence_card")
    if card and kind != "question_chip":
        plate(48, 220, card.get("text", ""), card.get("tag", "CLAIMED BY SPEAKER"), card_font)
    image.save(output_path, format="PNG", optimize=False)
    from .core.io import atomic_write_json
    atomic_write_json(output_path.with_suffix(".json"),manifest)
    return output_path


def question_chip(transcript: dict[str, Any], clip_start: float, clip_end: float, config, question: str | None = None) -> dict[str, Any] | None:
    if not config.get("craft", "question_chip", "enabled", default=True):
        return None
    words = transcript_words(transcript)
    source = " ".join(word["text"] for word in words)
    if question is None:
        question_spans = [segment for segment in transcript.get("segments", []) if float(segment.get("end", 0)) <= clip_start and "?" in str(segment.get("text", ""))]
        answer = next((segment for segment in transcript.get("segments", []) if float(segment.get("end", 0)) > clip_start), {})
        span = question_spans[-1] if question_spans else {}
        question_speaker, answer_speaker = span.get("speaker"), answer.get("speaker")
        if not question_speaker or question_speaker == "unknown" or not answer_speaker or answer_speaker == "unknown" or question_speaker == answer_speaker:
            return None
        question = span.get("text")
    if not question or not _normal(question):
        return None
    question = " ".join(str(question).split())
    max_chars = int(config.get("craft", "question_chip", "max_chars", default=90))
    if len(question) > max_chars:
        suffixes = [question[match.end():].strip() for match in re.finditer(r"[,;:]\s*", question)]
        question = next((suffix for suffix in suffixes if len(suffix) <= max_chars), "")
    if not question or len(question) > max_chars or _normal(question) not in _normal(source):
        return None
    return {"schema_version": 5, "label": "QUESTION", "text": question, "start": 0.0, "end": float(config.get("craft", "question_chip", "show_s", default=2.5)), "augmented": True, "exact_transcript": True}


def evidence_card(transcript: dict[str, Any], clip_start: float, clip_end: float, config) -> dict[str, Any] | None:
    if not config.get("craft", "evidence_cards", "enabled", default=False):
        return None
    words = [word for word in transcript_words(transcript) if clip_start <= word["start"] <= clip_end]
    for index, word in enumerate(words):
        if re.search(r"\d", word["text"]):
            text = word["text"].strip(".,!?()[]")
            return {"schema_version": 5, "text": text, "start": max(0.0, word["start"] - clip_start), "end": min(clip_end-clip_start,max(0.0, word["start"] - clip_start) + float(config.get("craft", "evidence_cards", "show_s", default=1.8))), "claim_checked": False, "tag": "CLAIMED BY SPEAKER"}
    return None


def receipt_pair(transcript: dict[str, Any], config, min_gap: float | None = None) -> dict[str, Any] | None:
    if not config.get("semantic", "receipts", "enabled", default=True):
        return None
    sentences = []
    for segment in transcript.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if len(_tokens(text)) >= 5 and (re.search(r"\d", text) or any(word in text.lower() for word in ("always", "never", "will", "did", "is"))):
            sentences.append(segment)
    gap = float(min_gap if min_gap is not None else config.get("semantic", "receipts", "min_gap_s", default=60))
    for first_index, first in enumerate(sentences):
        for second in sentences[first_index + 1:]:
            if float(second["start"]) - float(first["end"]) < gap:
                continue
            first_speaker = first.get("speaker")
            second_speaker = second.get("speaker")
            # Unknown diarization is not evidence of same-speaker identity.
            if not first_speaker or not second_speaker or first_speaker == "unknown" or second_speaker == "unknown":
                continue
            if first_speaker != second_speaker:
                continue
            verified=transcript.get("verified_speakers",[])
            if first_speaker not in verified and not (first.get("speaker_verified") and second.get("speaker_verified")):
                continue
            if float(first["end"])-float(first["start"])>12 or not str(first.get("text","")).rstrip().endswith((".","?","!")):
                continue
            qualifiers = [segment for segment in transcript.get("segments", []) if float(first["end"]) <= float(segment.get("start", 0)) <= float(first["end"]) + float(config.get("semantic", "receipts", "qualifier_window_s", default=30)) and any(marker in str(segment.get("text", "")).lower() for marker in ("what i meant", "to clarify", "let me correct", "i should have said"))]
            if qualifiers:
                continue
            overlap = set(_tokens(str(first.get("text", "")))) & set(_tokens(str(second.get("text", ""))))
            if len(overlap) < 2:
                continue
            first_text = str(first.get("text", ""))
            second_text = str(second.get("text", ""))
            negative = lambda text: bool(re.search(r"\b(no|not|never|cannot|can't|won't|isn't|didn't)\b", text.lower()))
            if negative(first_text) == negative(second_text):
                continue
            if any(marker in (first_text+" "+second_text).lower() for marker in ("they say", "my opponent claims", "let's say", "imagine", "hypothetically")):
                continue
            from .core.hashing import content_hash
            return {"schema_version": 5, "first": {"start": float(first["start"]), "end": float(first["end"]), "text": first_text, "sha256": content_hash(first_text)}, "second": {"start": float(second["start"]), "end": float(second["end"]), "text": second_text, "sha256": content_hash(second_text)}, "chip": f"EARLIER · {int(float(first['start']) // 60):02d}:{int(float(first['start']) % 60):02d}", "edited": True, "auto_allowed": False, "gap_s": float(second["start"]) - float(first["end"]), "engine": "lexical_proposal", "semantic_verified": False, "review_required": True}
    return None
