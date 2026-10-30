"""Source-ordered, word-preserving edit maps shared by render and exports."""
from __future__ import annotations

import copy
from pathlib import Path

from .core.io import atomic_write_json
from .core.process import run_process
from .core.tools import require_tool, filter_script_args
from .captions import transcript_words


def kept_spans(start: float, end: float, cuts: list[dict]) -> list[dict]:
    cursor, offset = start, 0.0
    spans = []
    for cut in sorted(cuts, key=lambda row: row["start"]):
        if cut["start"] < cursor or cut["end"] > end or cut["end"] <= cut["start"]:
            raise ValueError("Overlapping or invalid edit")
        if cut["start"] > cursor:
            spans.append({"start": cursor, "end": cut["start"], "output_start": offset})
            offset += cut["start"] - cursor
        cursor = cut["end"]
    if cursor < end:
        spans.append({"start": cursor, "end": end, "output_start": offset})
    return spans


def map_transcript(transcript: dict, spans: list[dict]) -> dict:
    result = {"schema_version": 5, "language": transcript.get("language", "en"), "segments": [], "words": []}
    words = transcript_words(transcript)
    for span in spans:
        for word in words:
            if word["start"] >= span["start"] - 1e-6 and word["end"] <= span["end"] + 1e-6:
                mapped = {**word, "source_start": word["start"], "source_end": word["end"], "start": word["start"] - span["start"] + span["output_start"], "end": word["end"] - span["start"] + span["output_start"]}
                result["words"].append(mapped)
        for segment in transcript.get("segments", []):
            selected = [word for word in result["words"] if span["start"] <= word["source_start"] and word["source_start"] >= float(segment.get("start", 0)) and word["source_end"] <= float(segment.get("end", 0)) and word["source_end"] <= span["end"]]
            if selected:
                result["segments"].append({**segment, "text": " ".join(word["text"] for word in selected), "words": selected, "start": selected[0]["start"], "end": selected[-1]["end"]})
    return result


def prepare_edited_source(plan: dict, work: Path) -> Path:
    spans = plan["source_spans"]
    output = work / "edited_source.mkv"
    args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y"]
    graph, concat_inputs = [], []
    for index, span in enumerate(spans):
        duration = span["end"] - span["start"]
        args += ["-ss", str(span["start"]), "-t", str(duration), "-i", plan["source"]["path"]]
        graph.append(f"[{index}:v]trim=duration={duration},setpts=PTS-STARTPTS,fps={plan['frame_rate']['target_cfr']}[v{index}]")
        concat_inputs.append(f"[v{index}]")
        if plan["source"].get("has_audio"):
            graph.append(f"[{index}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.03,afade=t=out:st={max(0,duration-.03)}:d=0.03[a{index}]")
            concat_inputs.append(f"[a{index}]")
    has_audio = int(bool(plan["source"].get("has_audio")))
    graph.append("".join(concat_inputs) + f"concat=n={len(spans)}:v=1:a={has_audio}[v]" + ("[a]" if has_audio else ""))
    script = work / "edits.graph"
    script.write_text(";\n".join(graph), encoding="utf-8")
    args += [*filter_script_args(script.name), "-map", "[v]", "-c:v", "ffv1", "-level", "3"]
    if has_audio:
        args += ["-map", "[a]", "-c:a", "pcm_s16le"]
    args += ["-f", "matroska", output.name]
    run_process(args, cwd=work, timeout=max(180, plan["trim"]["duration"] * 20))
    atomic_write_json(work / "edit_map.json", {"schema_version": 5, "source_spans": spans, "edits": plan.get("edits", [])})
    return output


def runtime_plan(plan: dict, source: Path) -> dict:
    result = copy.deepcopy(plan)
    result["source"]["path"] = str(source)
    result["trim"] = {"start": 0.0, "end": plan["trim"]["duration"], "duration": plan["trim"]["duration"]}
    result["transcript"] = map_transcript(plan["transcript"], plan["source_spans"])
    def mapped_time(relative):
        absolute=plan["original_trim"]["start"]+float(relative)
        for span in plan["source_spans"]:
            if span["start"]<=absolute<=span["end"]:
                return absolute-span["start"]+span["output_start"]
        next_span=next((span for span in plan["source_spans"] if span["start"]>absolute),None)
        return next_span["output_start"] if next_span else plan["trim"]["duration"]
    for item in result.get("craft",{}).values():
        if isinstance(item,dict):
            for key in ("start","end"):
                if key in item:item[key]=mapped_time(item[key])
    for item in result.get("polish",{}).get("nameplates",[]):
        item["start"],item["end"]=mapped_time(item["start"]),mapped_time(item["end"])
    for row in result.get("framing",{}).get("path",[]):
        row["t"]=mapped_time(row["t"])
    for segment in result.get("framing",{}).get("segments",[]):
        segment["t0"],segment["t1"]=mapped_time(segment["t0"]),mapped_time(segment["t1"])
    return result
