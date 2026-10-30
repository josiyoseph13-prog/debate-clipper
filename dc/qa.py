from __future__ import annotations

import json
import re
import math
import tempfile
from pathlib import Path
from typing import Any

from .core.config import AppConfig
from .core.hashing import file_hash
from .core.io import atomic_write_json
from .core.process import ProcessCancelled, run_process
from .core.tools import require_tool


def measure_audio_alignment(output: Path, plan: dict[str, Any], work_dir: Path) -> dict[str, Any]:
    """Measure audio offset against the actual source window, including AAC."""
    import wave
    import numpy as np

    with tempfile.TemporaryDirectory(dir=work_dir) as folder:
        decoded = []
        for kind in ("source", "output"):
            target = Path(folder) / f"{kind}.wav"
            path = Path(plan["source"]["path"]) if kind == "source" else output
            seek = ["-ss", str(plan["trim"]["start"])] if kind == "source" else []
            run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *seek, "-i", path, "-t", str(min(60, plan["trim"]["duration"])), "-vn", "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", target], timeout=120)
            with wave.open(str(target), "rb") as wav:
                decoded.append(np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64))
        source, encoded = decoded
        size = min(len(source), len(encoded))
        source, encoded = source[:size], encoded[:size]
        source -= source.mean()
        encoded -= encoded.mean()
        norm = float(np.linalg.norm(source) * np.linalg.norm(encoded))
        if norm < 1:
            return {"offset_ms": None, "correlation": 0, "reason": "silent reference"}
        fft_size = 1 << (size * 2 - 1).bit_length()
        correlation = np.fft.irfft(np.fft.rfft(encoded, fft_size) * np.conj(np.fft.rfft(source, fft_size)), fft_size)
        lag = min(16000, size - 1)
        search = np.concatenate([correlation[-lag:], correlation[:lag + 1]])
        best = int(np.argmax(search))
        return {"offset_ms": round((best - lag) / 8, 3), "correlation": round(float(search[best] / norm), 5), "method": "decoded_pcm_fft", "sample_rate": 8000}


def measure_caption_ab(output: Path, plan: dict[str, Any], config: AppConfig, caption_plan: dict[str, Any]) -> list[dict[str, Any]]:
    import numpy as np
    from PIL import Image
    from .renderer import lossless_caption_samples

    events = caption_plan.get("events", [])
    if not events:
        raise ValueError("Caption plan has no events")
    fps=float(plan.get("frame_rate",{}).get("target_cfr",30))
    available=[]
    for event in events:
        first=math.ceil(round(event["start"],2)*fps-1e-7)
        last=math.ceil(round(event["end"],2)*fps-1e-7)-1
        if first<=last:
            frame=min(last,max(first,round((event["start"]+event["end"])*fps/2)))
            available.append((event,frame))
    count=min(int(config.get("qa","caption_samples",default=20)),len(available))
    if not count:raise ValueError("No caption state is visible on the output CFR grid")
    selected=[available[round(index*(len(available)-1)/max(1,count-1))] for index in range(count)]
    # Sort by actual output-frame time; the PNG sets are returned in that order.
    selected=sorted({frame:(event,frame) for event,frame in selected}.values(),key=lambda row:row[1])
    times=[(frame+.001)/fps for event,frame in selected]
    selected=[event for event,frame in selected]
    work_dir = Path(plan.get("captions_ass", output.parent / "captions.ass")).parent
    with tempfile.TemporaryDirectory(dir=work_dir) as folder:
        samples = lossless_caption_samples(plan, config, work_dir, Path(folder), times)
        frame_ids=sorted(set(max(0,int(time*fps)) for time in times))
        expression="+".join(f"eq(n\\,{index})" for index in frame_ids)
        run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",output,"-vf",f"select={expression}","-frames:v",str(len(frame_ids)),"-fps_mode","vfr",str(Path(folder)/"encoded_%03d.png")],timeout=max(120,plan["trim"]["duration"]*5))
        encoded_paths=sorted(Path(folder).glob("encoded_*.png"))
        if len(encoded_paths)!=len(samples["captions"]):
            raise RuntimeError("Encoded caption sample count mismatch")
        first_rows, outside_counts, glow_reaches, active_counts = [], [], [], []
        x, y, w, h = caption_plan["slot"]["box"]
        halo = float(config.get("captions", "halo_px", default=45))
        # The rendered caption centre is slot.y + the plan's effective dy
        # (the user's saved vertical position, Phase 4D); the predicted
        # box must move with it or every moved caption fails this check.
        dy = float(caption_plan.get("dy", 0) or 0)
        # The box geometry is calibrated for the base font size; a bigger
        # user-chosen size (Phase 4D slider) renders proportionally wider
        # and taller text, so the prediction scales with the plan's ratio.
        base_fs = float(config.get("captions", "font_size", default=110) or 110)
        ratio = max(1.0, float(caption_plan.get("font_size", base_fs) or base_fs) / base_fs)
        halo = halo * ratio
        h = h * ratio
        # This is a generous prediction, recorded rather than inferred from the
        # difference itself. A measured overflow fails even with fallback fonts.
        left, right = max(0, int(x - halo)), min(config.canvas["w"], int(x + w + halo))
        top, bottom = max(config.regions["feed"]["y"], int(y - h - halo + dy)), min(config.regions["feed"]["y"] + config.regions["feed"]["h"], int(y + 2 * h + halo + dy))
        accent_hex = config.get("captions", "active").lstrip("#")
        accent = np.array([int(accent_hex[index:index + 2], 16) for index in (0, 2, 4)])
        rendered_errors=[]
        for sample_index,(full_path, baseline_path, fill_path,encoded_path) in enumerate(zip(samples["captions"], samples["baseline"], samples["active_fill"],encoded_paths)):
            full = np.asarray(Image.open(full_path).convert("RGB"), dtype=np.int16)
            baseline = np.asarray(Image.open(baseline_path).convert("RGB"), dtype=np.int16)
            fill = np.asarray(Image.open(fill_path).convert("RGB"), dtype=np.int16)
            encoded=np.asarray(Image.open(encoded_path).convert("RGB"),dtype=np.int16)
            changed = np.max(np.abs(full - baseline), axis=2) > 2
            rows, columns = np.where(changed)
            first_rows.append(int(rows.min()) if len(rows) else None)
            outside = changed.copy()
            outside[top:bottom, left:right] = False
            outside_counts.append(int(outside.sum()))
            difference=np.mean(np.abs(encoded-full),axis=2)
            rendered_errors.append(float(difference[changed].mean()) if changed.any() else 999)
            fill_mask = np.max(np.abs(fill - baseline), axis=2) > 2
            # Background and blended halo colours cannot stand in for the
            # active word. Count only independently isolated bare glyph pixels.
            glyph_colour=np.all(np.abs(encoded-accent)<30,axis=2)
            active_counts.append(int((glyph_colour&fill_mask).sum()))
            fill_rows, fill_cols = np.where(fill_mask)
            if len(fill_cols):
                if "no_glow" in samples:
                    with Image.open(samples["no_glow"][sample_index]) as image:
                        no_glow=np.asarray(image.convert("RGB"),dtype=np.int16)
                    halo_mask=np.max(np.abs(full-no_glow),axis=2)>2
                    _,halo_cols=np.where(halo_mask)
                    if len(halo_cols):glow_reaches.append([int(fill_cols.min()-halo_cols.min()),int(halo_cols.max()-fill_cols.max())])
        evidence = {"samples": len(first_rows), "first_changed_rows": first_rows, "outside_predicted_box": outside_counts, "predicted_box": [left, top, right, bottom], "method": "lossless_png_same_graph"}
        required=min(20,len(events))
        checks = [{"name": "caption_lossless_ab", "value": evidence, "threshold": {"samples":required,"outside_box": 0}, "passed": len(first_rows) >= required and all(row is not None and row >= config.regions["feed"]["y"] for row in first_rows) and not any(outside_counts)}]
        checks.append({"name": "caption_active_colour", "value": max(active_counts, default=0), "threshold": 800 if caption_plan.get("style")!="gravitas" else "not required in gravitas", "passed": max(active_counts, default=0) >= 800 or caption_plan.get("style")=="gravitas","method":"encoded accent pixels intersected with isolated bare active-glyph mask; background excluded"})
        checks.append({"name":"encoded_caption_presence","value":{"changed_pixel_mae":rendered_errors,"samples":len(rendered_errors)},"threshold":{"max_mae":30},"passed":bool(rendered_errors) and max(rendered_errors)<30})
        if caption_plan.get("style") == "hormozi_glow":
            checks.append({"name": "glow_reach", "value": {"active_word_samples": len(glow_reaches), "reach_px": glow_reaches,"method":"full minus identical text without glow; compares halo against bare active fill"}, "threshold": {"minimum_each_side": 30}, "passed": bool(glow_reaches) and all(min(pair) >= 30 for pair in glow_reaches), "severity": "review"})
        return checks


def validate_output(output: Path, plan: dict[str, Any], config: AppConfig, report_path: Path | None = None) -> dict[str, Any]:
    checks = []
    probe: dict[str, Any] = {}
    from .framing import framing_quality
    framing_check = framing_quality(plan)
    if config.get("framing","face_landmarker") and any(segment.get("track") is not None for segment in plan.get("framing",{}).get("segments",[])):
        try:
            from .vision import measure_rendered_faces
            measured=measure_rendered_faces(output,plan,config)
            framing_check.update(measured)
            framing_check["passed"] = framing_check["passed"] and measured["face_in_safe_area"]["inside"]==measured["face_in_safe_area"]["samples"]
        except ProcessCancelled:
            raise
        except (ImportError,RuntimeError,ValueError) as exc:
            framing_check["face_measurement_reason"]=str(exc)
    checks.append({"name": "framing_quality", "value": framing_check, "threshold": "measured camera limits; selected face inside 2% feed inset when measured; speaker identity needs review", "passed": framing_check["passed"], "severity": "review"})
    if plan.get("speaker_frame",{}).get("enabled"):
        try:
            from .speaker_frame import measure_output
            speaker_check=measure_output(output,plan,config)
            checks.append({"name":"speaker_frame","value":speaker_check,"threshold":"selected faces measured inside each panel's 2% inset and outside the blend strip; wide-only fallback has no face claim","passed":speaker_check["faces_inside_safe_area"]=="yes" or speaker_check["expected_face_samples"]==0,"severity":"review"})
        except ProcessCancelled:
            raise
        except (ImportError,RuntimeError,ValueError) as exc:
            checks.append({"name":"speaker_frame","value":{"faces_inside_safe_area":"Not measured","headroom":"Not measured","warnings":[str(exc)],"layout_seconds":plan["framing"]["debug"]["layout_seconds"]},"threshold":"decoded face measurement","passed":False,"severity":"review"})
    checks.append({"name": "file_exists", "value": output.exists() and output.stat().st_size > 0 if output.exists() else False, "threshold": "exists and non-empty", "passed": output.exists() and output.stat().st_size > 0})
    try:
        probe = json.loads(run_process([require_tool("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", output], timeout=30))
        checks.append({"name": "file_probe", "value": True, "threshold": True, "passed": True})
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name": "file_probe", "value": str(exc), "threshold": "valid ffprobe", "passed": False})
    video = next((row for row in probe.get("streams", []) if row.get("codec_type") == "video"), {})
    expected_w, expected_h = config.canvas["w"], config.canvas["h"]
    checks.append({"name": "resolution", "value": [video.get("width"), video.get("height")], "threshold": [expected_w, expected_h], "passed": int(video.get("width", 0)) == expected_w and int(video.get("height", 0)) == expected_h})
    checks.append({"name": "sar", "value": video.get("sample_aspect_ratio"), "threshold": "1:1", "passed": video.get("sample_aspect_ratio", "1:1") in {"1:1", None}})
    actual_duration = float(probe.get("format", {}).get("duration") or 0)
    expected_duration = float(plan.get("trim", {}).get("duration", 0))
    checks.append({"name": "duration", "value": actual_duration, "threshold": expected_duration, "passed": abs(actual_duration - expected_duration) <= float(config.get("qa","duration_tolerance_s",default=.1)) or expected_duration == 0})
    checks.append({"name": "video_codec", "value": video.get("codec_name"), "threshold": "h264", "passed": video.get("codec_name") in {"h264", "avc1"}})
    checks.append({"name": "color_tags", "value": {"space": video.get("color_space"), "range": video.get("color_range"), "primaries": video.get("color_primaries")}, "threshold": {"space": "bt709", "range": "tv", "primaries": "bt709"}, "passed": video.get("color_space") == "bt709" and video.get("color_range") == "tv" and video.get("color_primaries") == "bt709"})
    audio = next((row for row in probe.get("streams", []) if row.get("codec_type") == "audio"), {})
    source_has_audio = bool(plan.get("source", {}).get("has_audio", True))
    checks.append({"name": "audio_stream", "value": bool(audio), "threshold": source_has_audio, "passed": bool(audio) if source_has_audio else True})
    checks.append({"name": "audio_codec", "value": audio.get("codec_name"), "threshold": "aac" if source_has_audio else "not required", "passed": audio.get("codec_name") == "aac" if source_has_audio else True})
    if source_has_audio:
        checks.append({"name":"audio_sample_rate","value":audio.get("sample_rate"),"threshold":config.get("output","audio_hz",default=48000),"passed":int(audio.get("sample_rate",0))==config.get("output","audio_hz",default=48000)})
    if source_has_audio and audio:
        try:
            loudness_output = run_process([require_tool("ffmpeg"), "-hide_banner", "-i", output, "-af", "ebur128=framelog=verbose", "-f", "null", "-"], timeout=120, output_limit=100_000)
            loudness_matches = re.findall(r"\bI:\s*(-?[0-9.]+)\s*LUFS", loudness_output)
            integrated = float(loudness_matches[-1]) if loudness_matches else None
            target_lufs = float(config.get("audio", "target_lufs", default=-14))
            checks.append({"name": "integrated_loudness", "value": integrated, "threshold": [target_lufs - 1.5, target_lufs + 1.5], "passed": integrated is not None and target_lufs - 1.5 <= integrated <= target_lufs + 1.5})
        except ProcessCancelled:
            raise
        except Exception as exc:
            checks.append({"name": "integrated_loudness", "value": str(exc), "threshold": "within 1.5 LU", "passed": False})
        try:
            peak_output = run_process([require_tool("ffmpeg"), "-hide_banner", "-i", output, "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], timeout=120, output_limit=100_000)
            peak_blocks = re.findall(r"\{\s*\"input_i\".*?\}", peak_output, flags=re.S)
            input_tp = float(json.loads(peak_blocks[-1]).get("input_tp")) if peak_blocks else None
            peak_limit = float(config.get("audio", "true_peak_db", default=-1))
            checks.append({"name": "true_peak", "value": input_tp, "threshold": peak_limit, "passed": input_tp is not None and input_tp <= peak_limit})
        except ProcessCancelled:
            raise
        except Exception as exc:
            checks.append({"name": "true_peak", "value": str(exc), "threshold": "at or below configured true peak", "passed": False})
        try:
            alignment = measure_audio_alignment(output, plan, output.parent)
            checks.append({"name": "audio_source_alignment", "value": alignment, "threshold": {"max_offset_ms": 40}, "passed": alignment["offset_ms"] is not None and abs(alignment["offset_ms"]) <= 40 and alignment["correlation"] > .2})
        except ProcessCancelled:
            raise
        except Exception as exc:
            checks.append({"name": "audio_source_alignment", "value": str(exc), "threshold": "40 ms", "passed": False})
    frame_rate = video.get("avg_frame_rate") or "0/0"
    try:
        numerator, denominator = frame_rate.split("/", 1)
        measured_fps = float(numerator) / max(1.0, float(denominator))
    except (ValueError, ZeroDivisionError):
        measured_fps = 0.0
    fps_cap = float(plan.get("output", {}).get("fps_cap", config.get("output", "fps_cap", default=30)))
    checks.append({"name": "fps_cap", "value": measured_fps, "threshold": fps_cap, "passed": 0 < measured_fps <= fps_cap + 0.1})
    target_fps = float(plan.get("frame_rate", {}).get("target_cfr", measured_fps))
    checks.append({"name": "fps_matches_plan", "value": measured_fps, "threshold": target_fps, "passed": abs(measured_fps - target_fps) < .01})
    try:
        frames=run_process([require_tool("ffprobe"),"-v","error","-select_streams","v:0","-show_entries","frame=best_effort_timestamp_time","-of","csv=p=0",output],timeout=60,output_limit=2_000_000)
        times=[float(line.split(",")[0]) for line in frames.splitlines() if line and re.match(r"^[0-9]+\.[0-9]+",line)]
        deltas=[b-a for a,b in zip(times,times[1:])]
        expected=expected_duration*target_fps
        checks.append({"name":"encoded_cadence","value":{"frames":len(times),"max_period_error_s":max((abs(delta-1/target_fps) for delta in deltas),default=999)},"threshold":{"frame_count_tolerance":2,"period_error_s":.001},"passed":abs(len(times)-expected)<=2 and bool(deltas) and max(abs(delta-1/target_fps) for delta in deltas)<.001})
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name":"encoded_cadence","value":str(exc),"threshold":"CFR", "passed":False})
    try:
        anomalies=run_process([require_tool("ffmpeg"),"-hide_banner","-i",output,"-vf",f"crop={config.regions['feed']['w']}:{config.regions['feed']['h']}:{config.regions['feed']['x']}:{config.regions['feed']['y']},blackdetect=d=0.1:pic_th=0.98,freezedetect=n=-60dB:d=1.0","-an","-f","null","-"],timeout=max(120,expected_duration*5),output_limit=100000)
        detected=[line for line in anomalies.splitlines() if "black_start:" in line or "freeze_start:" in line]
        checks.append({"name":"black_frozen_advisory","value":detected,"threshold":"compare anomalous spans with source during review","passed":not detected,"severity":"review"})
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name":"black_frozen_advisory","value":str(exc),"passed":False,"threshold":"decoded analysis","severity":"review"})
    # Seekability and cadence checks exercise the encoded file, not just ffprobe metadata.
    seek_results = []
    try:
        with tempfile.TemporaryDirectory(dir=output.parent) as seek_dir:
            for fraction in (0.25, 0.5, 0.75):
                frame_path = Path(seek_dir) / f"seek_{fraction}.png"
                run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(actual_duration * fraction), "-i", output, "-frames:v", "1", frame_path], timeout=60)
                seek_results.append(frame_path.exists() and frame_path.stat().st_size > 0)
        checks.append({"name": "seek_25_50_75", "value": seek_results, "threshold": [True, True, True], "passed": all(seek_results)})
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name": "seek_25_50_75", "value": str(exc), "threshold": "three decodable frames", "passed": False})
    caption_plan_path = Path(str(plan.get("caption_plan", output.parent / "captions_plan.json")))
    if not caption_plan_path.exists():
        caption_plan_path = output.parent / "captions_plan.json"
    caption_plan = json.loads(caption_plan_path.read_text(encoding="utf-8")) if caption_plan_path.exists() else {}
    if config.get("captions","glow","method",default="ass_layers")=="fast_glow":
        checks.append({"name":"fast_glow_equivalence_gate","value":"Not measured against default ASS glow","threshold":"Measured halo and color equivalence","passed":False,"severity":"review"})
    event_durations = [float(event.get("end", 0)) - float(event.get("start", 0)) for event in caption_plan.get("events", [])]
    min_event_duration = min(event_durations, default=0)
    overlapping = [index for index, (left, right) in enumerate(zip(caption_plan.get("events", []), caption_plan.get("events", [])[1:])) if left["end"] - right["start"] > .08 + 1e-6]
    checks.append({"name": "caption_active_timing", "value": {"events": len(event_durations), "min_s": round(min_event_duration, 3), "overlaps_over_80ms": overlapping}, "threshold": "positive intervals, overlaps <=80ms", "passed": bool(event_durations) and min_event_duration > 0 and not overlapping})
    group_durations = [group["end"] - group["start"] for group in caption_plan.get("groups", [])]
    checks.append({"name": "caption_group_timing", "value": {"groups": len(group_durations), "min_s": round(min(group_durations, default=0), 3)}, "threshold": .30, "passed": bool(group_durations) and min(group_durations) >= .30 - 1e-6, "severity": "review"})
    checks.append({"name": "caption_plan_warnings", "value": caption_plan.get("warnings", []), "threshold": [], "passed": not caption_plan.get("warnings"), "severity": "review"})
    slot = caption_plan.get("slot", {})
    slot_box = slot.get("box", [])
    feed = config.regions["feed"]
    slot_ok = len(slot_box) == 4 and slot_box[0] >= config.get("captions", "x_limits", default=[100, 980])[0] and slot_box[0] + slot_box[2] <= config.get("captions", "x_limits", default=[100, 980])[1] and slot_box[1] + slot_box[3] <= config.get("captions", "bottom_max", default=config.canvas["h"])
    checks.append({"name": "caption_safe_slot", "value": slot_box, "threshold": "inside configured limits", "passed": slot_ok})
    from .captions import transcript_words
    original_words=transcript_words(plan.get("transcript",{}))
    expected_words=[row["text"] for row in original_words if row["end"]>plan.get("trim",{}).get("start",0) and row["start"]<plan.get("trim",{}).get("end",0)]
    actual_words=[row["text"] for row in caption_plan.get("words",[])]
    checks.append({"name":"caption_text_fidelity","value":{"expected_words":len(expected_words),"actual_words":len(actual_words)},"threshold":"exact source-word sequence","passed":expected_words==actual_words})
    clip_start=float(plan.get("trim",{}).get("start",0))
    clip_end=float(plan.get("trim",{}).get("end",0))
    in_clip=[row for row in original_words if row["end"]>clip_start and row["start"]<clip_end]
    cut_words=[row["i"] for row in in_clip if row["start"]+.04<clip_start<row["end"]-.04 or row["start"]+.04<clip_end<row["end"]-.04]
    checks.append({"name":"mid_word_boundaries","value":cut_words,"threshold":[],"passed":not cut_words})
    if in_clip:
        lead,tail=in_clip[0]["start"]-clip_start,clip_end-in_clip[-1]["end"]
        checks.append({"name":"speech_margins","value":{"lead_s":lead,"tail_s":tail},"threshold":{"lead_s":.08,"tail_s":.25},"passed":lead>=.08-1e-6 and tail>=.25-1e-6,"severity":"review"})
    if plan.get("source_text_policy"):
        checks.append({"name":"source_caption_avoidance","value":plan["source_text_policy"],"threshold":"recorded avoidance policy; heuristic detector accuracy unverified","passed":True})
    for index,item in enumerate(plan.get("emoji_pops",[])):
        from .captions import boxes_intersect
        anchored=any(word["i"]==item["word_i"] and word["text"]==item["text"] and abs(word["start"]-clip_start-item["start"])<=.12 for word in in_clip)
        collision=any(boxes_intersect(tuple(item["box"]),tuple(box)) for box in plan.get("caption_exclusions",[]))
        checks.append({"name":f"emoji_pop:{index}","value":item,"threshold":"transcript anchored, bounded and collision free","passed":anchored and 0<=item["start"]<item["end"]<=expected_duration and not collision})
    from .selection import _normal
    full_text=" ".join(word["text"] for word in original_words)
    for name in ("question_chip","evidence_card"):
        item=plan.get("craft",{}).get(name)
        if item:
            text_ok=_normal(item["text"]) in _normal(full_text)
            intervals_ok=0<=item.get("start",0)<item.get("end",0)<=expected_duration+.12
            if name=="evidence_card":
                matching=[row for row in in_clip if _normal(item["text"]) in _normal(row["text"])]
                intervals_ok=intervals_ok and any(abs(row["start"]-clip_start-item.get("start",0))<=.12 for row in matching)
            checks.append({"name":"craft_fidelity:"+name,"value":{"text":item["text"],"interval":[item.get("start"),item.get("end")]},"threshold":"exact transcript substring and bounded timing","passed":text_ok and intervals_ok})
    for file in ("craft.json","evidence.json"):
        manifest_path=Path(plan.get("captions_ass",output.parent/"captions.ass")).parent/file
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            checks.append({"name":"craft_placement:"+file,"value":manifest,"threshold":"zero placement warnings","passed":not manifest.get("warnings"),"severity":"review"})
    bottom_rows = {"name": "bottom_white_guard", "value": "not sampled", "threshold": "mean channel >= 250", "passed": False}
    try:
        from PIL import Image

        with tempfile.TemporaryDirectory(dir=output.parent) as temp_dir:
            frame_path = Path(temp_dir) / "frame.png"
            run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", output, "-frames:v", "1", frame_path], timeout=60)
            image = Image.open(frame_path).convert("RGB")
            bottom = config.regions["bottom_white"]
            crop = image.crop((0, int(bottom["y"] + 4), image.width, image.height))
            import numpy as np
            bottom_pixels=np.asarray(crop)
            mask=np.ones(bottom_pixels.shape[:2],dtype=bool)
            progress=config.get("polish","progress_bar",default={})
            credit=config.get("polish","source_credit",default={})
            if progress.get("enabled"):
                y=int(progress["y"])-int(bottom["y"]+4)
                mask[max(0,y-2):max(0,y+int(progress.get("h",6))+3)]=False
            if credit.get("enabled"):
                y=int(credit["y"])-int(bottom["y"]+4)
                mask[max(0,y-30):max(0,y+30)]=False
            pixels = bottom_pixels[mask].tolist()
            mean_channel = sum(sum(pixel) / len(pixel) for pixel in pixels) / max(1, len(pixels))
            bottom_rows = {"name": "bottom_white_guard", "value": round(mean_channel, 2), "threshold": 250, "passed": mean_channel >= 250}
            chrome_path = Path(str(plan.get("chrome_png", output.parent / "chrome.png")))
            if chrome_path.exists():
                import numpy as np

                chrome = Image.open(chrome_path).convert("RGB").resize((image.width, int(config.regions["feed"]["y"])))
                chrome_errors = []
                for index in range(12):
                    frame_path = Path(temp_dir) / f"chrome_{index}.png"
                    seek_time = min(actual_duration * index / 11, max(0.0, actual_duration - 0.05)) if actual_duration else 0
                    run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(seek_time), "-i", output, "-frames:v", "1", frame_path], timeout=60)
                    frame_top = Image.open(frame_path).convert("RGB").crop((0, 0, image.width, int(config.regions["feed"]["y"])))
                    chrome_errors.append(float(np.abs(np.asarray(frame_top, dtype=np.float32) - np.asarray(chrome, dtype=np.float32)).mean()))
                absolute_mae = max(chrome_errors, default=999.0)
                checks.append({"name": "chrome_integrity_12_frames", "value": {"max_mae": round(absolute_mae, 3), "samples": len(chrome_errors)}, "threshold": 2.5, "passed": len(chrome_errors) == 12 and absolute_mae <= 2.5})
            else:
                checks.append({"name": "chrome_integrity_12_frames", "value": "chrome artifact unavailable", "threshold": 2.5, "passed": False})
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name": "image_sampling", "value": str(exc), "threshold": "decodable samples", "passed": False})
    try:
        if caption_plan.get("suppressed"):
            for check in checks:
                if check["name"] in {"caption_active_timing","caption_group_timing"}:
                    check.update({"passed":True,"threshold":"Own captions suppressed by explicit source-trust setting"})
            checks.append({"name":"source_caption_trust_gate","value":"Source caption accuracy not independently verified","threshold":"Human review before relying on source captions","passed":False,"severity":"review"})
        else:
            checks.extend(measure_caption_ab(output, plan, config, caption_plan))
    except ProcessCancelled:
        raise
    except Exception as exc:
        checks.append({"name": "caption_lossless_ab", "value": str(exc), "threshold": "20 lossless samples", "passed": False})
    checks.append(bottom_rows)
    bottom_rows["severity"] = "review"
    hard_fail = any(not check["passed"] for check in checks if check.get("severity") != "review")
    has_warning = any(not check["passed"] for check in checks if check.get("severity") == "review")
    report = {"schema_version": 5, "status": "failed" if hard_fail else ("needs_review" if has_warning else "passed"), "checks": checks, "output": str(output), "output_sha256": file_hash(output) if output.exists() else None, "plan_hash": plan.get("plan_hash")}
    for check in checks:
        check.setdefault("evidence",str(report_path) if report_path else str(output))
    if report_path:
        atomic_write_json(report_path, report)
    from .contracts import validate_report
    validate_report(report)
    return report
