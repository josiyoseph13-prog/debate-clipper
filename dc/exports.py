from __future__ import annotations

import csv
import html
import json
import re
import shutil
from urllib.parse import quote
from pathlib import Path
from fractions import Fraction
from typing import Any

from .captions import transcript_words
from .core.hashing import content_hash, file_hash
from .core.io import atomic_copy, atomic_write_json
from .core.process import ProcessCancelled, check_cancelled, run_process
from .core.tools import require_tool
from .integrity import publish_gate


def _subtitle_rows(transcript: dict[str, Any], start: float, end: float) -> list[tuple[float, float, str]]:
    return [(max(0, word["start"] - start), min(end - start, word["end"] - start), word["text"].strip()) for word in transcript_words(transcript) if word["end"] > start and word["start"] < end]


def write_sidecars(export_dir: Path, transcript: dict[str, Any], start: float, end: float) -> dict[str, str]:
    rows = _subtitle_rows(transcript, start, end)
    def timestamp(seconds: float, separator: str) -> str:
        milliseconds = max(0, int(round(seconds * 1000)))
        hours, remainder = divmod(milliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        whole, fraction = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{whole:02d}{separator}{fraction:03d}"
    srt = "\n\n".join(f"{index}\n{timestamp(a, ',')} --> {timestamp(b, ',')}\n{text}" for index, (a, b, text) in enumerate(rows, 1)) + ("\n" if rows else "")
    vtt = "WEBVTT\n\n" + "\n\n".join(f"{timestamp(a, '.')} --> {timestamp(b, '.')}\n{text}" for a, b, text in rows) + ("\n" if rows else "")
    (export_dir / "captions.srt").write_text(srt, encoding="utf-8")
    (export_dir / "captions.vtt").write_text(vtt, encoding="utf-8")
    return {"srt": str(export_dir / "captions.srt"), "vtt": str(export_dir / "captions.vtt")}


def _edl_time(seconds: float, rate: int = 30) -> str:
    frame = max(0, int(round(float(seconds) * rate)))
    hours, frame = divmod(frame, rate * 3600)
    minutes, frame = divmod(frame, rate * 60)
    seconds_value, frames = divmod(frame, rate)
    return f"{hours:02d}:{minutes:02d}:{seconds_value:02d}:{frames:02d}"


def write_interop(export_dir: Path, plan: dict[str, Any], final_dir: Path | None = None) -> dict[str, str]:
    duration = float(plan["trim"]["duration"])
    rate = float(plan.get("frame_rate", {}).get("target_cfr", 30))
    frame_count = round(duration * rate)
    source_path = Path(plan["source"]["path"])
    try:
        source = source_path.as_uri()
    except ValueError:
        source = "file:///" + quote(str(plan["source"]["path"]).replace("\\", "/").lstrip("/"))
    def rational_time(value):
        return {"OTIO_SCHEMA": "RationalTime.1", "value": value, "rate": rate}
    def time_range(start,frames=frame_count):
        return {"OTIO_SCHEMA": "TimeRange.1", "start_time": rational_time(start), "duration": rational_time(frames)}
    otio = {"OTIO_SCHEMA": "Timeline.1", "name": plan.get("candidate_id", "clip"), "global_start_time": rational_time(0), "tracks": {"OTIO_SCHEMA": "Stack.1", "children": [{"OTIO_SCHEMA": "Track.1", "kind": "Video", "children": [{"OTIO_SCHEMA": "Clip.1", "name": "source", "source_range": time_range(round(plan["trim"]["start"] * rate)), "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": source}}]}, {"OTIO_SCHEMA": "Track.1", "name": "Captions (sidecar)", "kind": "Video", "children": [{"OTIO_SCHEMA": "Clip.1", "name": "captions", "source_range": time_range(0), "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": ((final_dir or export_dir) / "captions.srt").resolve().as_uri()}, "metadata": {"role": "caption_sidecar", "burn_in": False}}]}]}}
    spans=plan.get("source_spans") or [{"start":plan["trim"]["start"],"end":plan["trim"]["end"],"output_start":0}]
    otio["tracks"]["children"][0]["children"]=[{"OTIO_SCHEMA":"Clip.1","name":f"source_{index+1}","source_range":time_range(round(span["start"]*rate),round((span["end"]-span["start"])*rate)),"media_reference":{"OTIO_SCHEMA":"ExternalReference.1","target_url":source},"metadata":{"edited":bool(plan.get("edits")),"source_span":span}} for index,span in enumerate(spans)]
    (export_dir / "timeline.otio").write_text(json.dumps(otio, indent=2), encoding="utf-8")
    candidate_id = html.escape(str(plan.get("candidate_id", "clip")), quote=True)
    source_xml = html.escape(source, quote=True)
    fraction_rate = Fraction(rate).limit_denominator(1001)
    frame_duration = Fraction(1, 1) / fraction_rate
    def seconds(frames):
        value = frames * frame_duration
        return f"{value.numerator}/{value.denominator}s"
    format_frame = seconds(1)
    start_value = seconds(round(plan["trim"]["start"] * rate))
    duration_value = seconds(frame_count)
    width, height = plan["source"].get("width", 1920), plan["source"].get("height", 1080)
    fcpxml = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><fcpxml version=\"1.10\"><resources><format id=\"r1\" frameDuration=\"{format_frame}\" width=\"{width}\" height=\"{height}\"/><asset id=\"r2\" name=\"source\" start=\"0s\" hasVideo=\"1\" format=\"r1\"><media-rep kind=\"original-media\" src=\"{source_xml}\"/></asset></resources><library><event name=\"{candidate_id}\"><project name=\"clip\"><sequence format=\"r1\" duration=\"{duration_value}\" tcStart=\"0s\" tcFormat=\"NDF\"><spine><asset-clip ref=\"r2\" offset=\"0s\" start=\"{start_value}\" duration=\"{duration_value}\"/></spine></sequence></project></event></library></fcpxml>"
    import xml.etree.ElementTree as ET
    tree=ET.fromstring(fcpxml)
    spine=tree.find(".//spine")
    spine.clear()
    for span in spans:
        ET.SubElement(spine,"asset-clip",{"ref":"r2","offset":seconds(round(span["output_start"]*rate)),"start":seconds(round(span["start"]*rate)),"duration":seconds(round((span["end"]-span["start"])*rate))})
    fcpxml=ET.tostring(tree,encoding="unicode",xml_declaration=False)
    (export_dir / "timeline.fcpxml").write_text(fcpxml, encoding="utf-8")
    edl_rate = int(round(rate))
    start_tc, end_tc = _edl_time(plan["trim"]["start"], edl_rate), _edl_time(plan["trim"]["end"], edl_rate)
    edl=[f"TITLE: {candidate_id}\nFCM: NON-DROP FRAME\n* FRAME RATE: {rate}\n"]
    for index,span in enumerate(spans):
        a,b=_edl_time(span["start"],edl_rate),_edl_time(span["end"],edl_rate)
        c,d=_edl_time(span["output_start"],edl_rate),_edl_time(span["output_start"]+span["end"]-span["start"],edl_rate)
        edl.append(f"{index+1:03d}  AX       V     C        {a} {b} {c} {d}\n* FROM CLIP NAME: {source_path.name}\n")
    (export_dir/"timeline.edl").write_text("".join(edl),encoding="utf-8")
    return {"otio": str(export_dir / "timeline.otio"), "fcpxml": str(export_dir / "timeline.fcpxml"), "edl": str(export_dir / "timeline.edl")}


def export_bundle(export_dir: Path, output: Path, plan: dict[str, Any], transcript: dict[str, Any], source: dict[str, Any], candidate: dict[str, Any], qa_report: dict[str, Any], config: Any | None = None) -> dict[str, Any]:
    from .core.bundles import write_complete_bundle
    if qa_report.get("status")!="passed" and not (qa_report.get("status")=="needs_review" and qa_report.get("review_accepted") is True):
        raise ValueError("Export requires passed QA or explicit acceptance of needs_review")
    def build(stage):
        result=_build_export_bundle(stage,output,plan,transcript,source,candidate,qa_report,config,final_dir=export_dir)
        result["export_dir"]=str(export_dir)
        result["files"]={name:str(export_dir/Path(path).relative_to(stage)) for name,path in result["files"].items()}
        result["transactional"]=True
        return result
    return write_complete_bundle(output.parent,export_dir,build)


def _build_export_bundle(export_dir: Path, output: Path, plan: dict[str, Any], transcript: dict[str, Any], source: dict[str, Any], candidate: dict[str, Any], qa_report: dict[str, Any], config: Any | None = None, final_dir: Path | None = None) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)
    duration = float(plan["trim"]["duration"])
    target = export_dir / "clip.mp4"
    if output.resolve() != target.resolve():
        atomic_copy(output, target)
    source_slug = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(source.get("path", "source")).stem).strip("_")[:60] or "source"
    stable_name = str(plan.get("export_filename") or f"{source_slug}_{candidate.get('id', 'clip')}_{plan.get('plan_hash', content_hash(plan))[:8]}.mp4")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.mp4", stable_name):
        stable_name = f"{source_slug}_{candidate.get('id', 'clip')}_{plan.get('plan_hash', content_hash(plan))[:8]}.mp4"
    stable_target = export_dir / stable_name
    if stable_target.resolve() != target.resolve():
        atomic_copy(target, stable_target)
    cover = export_dir / "cover.jpg"
    try:
        import cv2

        capture = cv2.VideoCapture(str(target))
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        from .vision import haar_detector
        face_detector=haar_detector()
        best_frame, best_score = None, -1.0
        for _ in range(max(1, int(fps * min(3.0, float(plan["trim"]["duration"]))))):
            check_cancelled()
            ok, frame = capture.read()
            if not ok:
                break
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            faces=face_detector.detectMultiScale(gray,1.1,5,minSize=(48,48)) if face_detector else []
            score=max((float(cv2.Laplacian(gray[y:y+h,x:x+w],cv2.CV_64F).var())*(w*h)/(frame.shape[0]*frame.shape[1]) for x,y,w,h in faces),default=0)
            if not score:
                score=float(cv2.Laplacian(gray,cv2.CV_64F).var())*.01
            if score > best_score:
                best_score, best_frame = score, frame
        capture.release()
        if best_frame is not None:
            cv2.imwrite(str(cover), best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        else:
            raise RuntimeError("no frames available")
    except ProcessCancelled:
        raise
    except Exception:
        try:
            run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", target, "-frames:v", "1", "-q:v", "2", cover], timeout=60)
        except ProcessCancelled:
            raise
        except Exception:
            # The bundle remains valid without a cover when FFmpeg/OpenCV is unavailable.
            pass
    sidecars = write_sidecars(export_dir, transcript, 0 if plan.get("source_spans") else float(plan["trim"]["start"]), float(plan["trim"]["duration"]) if plan.get("source_spans") else float(plan["trim"]["end"]))
    for name in ("captions.ass", "chrome.png", "craft.png", "extras.png"):
        source_artifact = plan.get(name.replace(".", "_"), plan.get(name))
        if source_artifact and Path(source_artifact).exists():
            shutil.copy2(source_artifact, export_dir / name)
    interop = write_interop(export_dir, plan, final_dir=final_dir)
    edits = {"schema_version": 5, "edits": candidate.get("edits", []), "edited": bool(candidate.get("edited", False)), "augmented": bool(candidate.get("augmented", False))}
    from .meta import metadata_pack
    metadata = {**metadata_pack(source,candidate,plan.get("headline","")),"schema_version": 5, "titles": candidate.get("hook", {}).get("headline_options", []), "title": plan.get("headline"), "source_title": source.get("meta", {}).get("title") or Path(source.get("path", "source")).stem, "description": f"Source: {source.get('meta', {}).get('webpage_url') or source.get('source_url') or source.get('path')} at {plan['trim']['start']:.2f}s. Watch the full exchange.", "pinned_comment": "Which side made the stronger case?", "chapter": {"start": plan["trim"]["start"], "title": plan.get("headline")}, "rights_class": source.get("rights_class", "unknown"), "edited": edits["edited"], "augmented": edits["augmented"], "claims": candidate.get("claims", []),"series":candidate.get("series")}
    checked_sources=list(dict.fromkeys(str(claim["source_url"]) for claim in candidate.get("claims",[]) if claim.get("claim_checked") and claim.get("source_url")))
    if checked_sources:
        metadata["pinned_comment"]+=" Sources checked by the reviewer: "+" ".join(checked_sources)
    try:
        decoded_hash = run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", target, "-map", "0:v:0", "-f", "hash", "-hash", "sha256", "-"], timeout=max(120, duration * 10)).strip().split("=", 1)[-1]
    except ProcessCancelled:
        raise
    except Exception:
        decoded_hash = None
    provenance = {"schema_version": 5, "source_url": source.get("source_url"), "source_sha256": source.get("fingerprint", {}).get("sha256"), "rights_class": source.get("rights_class", "unknown"), "full_exchange": {"url": source.get("source_url"), "start": plan["trim"]["start"]}, "edits": edits["edits"], "source_spans":plan.get("source_spans"), "tool_versions": plan.get("tool_versions", {}), "config_hash": plan.get("config_hash"), "output_sha256": qa_report.get("output_sha256"), "output_decoded_frame_hash": decoded_hash}
    atomic_write_json(export_dir / "edits.json", edits)
    atomic_write_json(export_dir / "metadata.json", metadata)
    atomic_write_json(export_dir / "provenance.json", provenance)
    atomic_write_json(export_dir / "export_report.json", qa_report)
    atomic_write_json(export_dir / "render_plan.json", {key: value for key, value in plan.items() if key != "transcript"})
    atomic_write_json(export_dir / "candidate.json", candidate)
    atomic_write_json(export_dir / "framing.json", plan["framing"])
    if config is not None:
        atomic_write_json(export_dir / "renderer_config.json", {"schema_version":5,"config":config.json(),"config_hash":config.hash()})
    # The publish pack is always generated, but its dry-run state is explicit.
    class _PublishConfig:
        @staticmethod
        def get(*keys, default=None):
            if keys[-1:] == ("block_rights",):
                return ["unknown"]
            if keys[-1:] == ("block_flags",):
                return ["review", "block_auto_approve"]
            if keys[-1:] == ("default_privacy",):
                return "private"
            return default
    allowed, reasons = publish_gate(candidate, source, config or _PublishConfig())
    if qa_report.get("status") != "passed":
        allowed = False
        reasons = [*reasons, "qa_" + str(qa_report.get("status", "missing"))]
    atomic_write_json(export_dir / "publish_dry_run.json", {"schema_version": 5, "allowed": allowed, "reasons": reasons, "privacy": "private", "require_click": True})
    rating = "Great" if float(candidate.get("score", 0)) >= 90 else "Good" if float(candidate.get("score", 0)) >= 80 else "Okay" if float(candidate.get("score", 0)) >= 70 else "Weak"
    brand_wordmark = str((config or _PublishConfig()).get("brand", "wordmark", default="YOUR CHANNEL") or "YOUR CHANNEL")
    about = "\n".join([
        f"{brand_wordmark} CLIP",
        "",
        f"Source video: {metadata['source_title']}",
        f"Source file: {source.get('path', '')}",
        f"Time range: {float(plan['trim']['start']):.2f}s to {float(plan['trim']['end']):.2f}s",
        f"Headline: {plan.get('headline', '')}",
        f"Rating: {rating} ({float(candidate.get('score', 0)):.1f})",
        f"Rights status: {source.get('rights_class', 'unknown')}",
        f"Publishing allowed: {'Yes' if allowed else 'No'}",
        f"Publishing note: {'; '.join(reasons) if reasons else 'No publishing block recorded.'}",
        "",
        "The MP4 with the readable name is the easiest file to play.",
    ]) + "\n"
    (export_dir / "ABOUT_THIS_CLIP.txt").write_text(about, encoding="utf-8")
    publish_csv = export_dir / "publish_plan.csv"
    with publish_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["platform", "title", "description", "hashtags", "pinned_comment", "scheduled_at", "privacy"])
        writer.writeheader()
        for platform in ("youtube_shorts", "tiktok", "instagram_reels"):
            writer.writerow({"platform": platform, "title": metadata["title"], "description": metadata["description"], "hashtags": " ".join(metadata["hashtags"]), "pinned_comment": metadata["pinned_comment"], "scheduled_at": "", "privacy": "private"})
            (export_dir/(platform+".txt")).write_text(metadata["title"]+"\n\n"+metadata["description"]+"\n\n"+" ".join(metadata["hashtags"])+"\n\nPinned comment: "+metadata["pinned_comment"]+"\n",encoding="utf-8")
    files = {"clip": str(target), "stable_clip": str(stable_target), **sidecars, **interop, "metadata": str(export_dir / "metadata.json"), "provenance": str(export_dir / "provenance.json"), "edits": str(export_dir / "edits.json"), "about": str(export_dir / "ABOUT_THIS_CLIP.txt"), "publish_plan": str(publish_csv), "publish_dry_run": str(export_dir / "publish_dry_run.json")}
    for name in ("captions.ass", "chrome.png", "craft.png", "extras.png"):
        if (export_dir / name).exists():
            files[name.rsplit(".", 1)[0]] = str(export_dir / name)
    if cover.exists():
        files["cover"] = str(cover)
    return {"export_dir": str(export_dir), "stable_id": str(candidate.get("id", export_dir.name)), "readable_filename": stable_name, "publish_allowed": allowed, "publish_block_reasons": reasons, "files": files}
