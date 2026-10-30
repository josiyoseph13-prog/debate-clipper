"""Strict, dependency-free contracts for job requests and stage artifacts."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .core.security import validate_id


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _number(value: Any, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def validate_job_spec(spec: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Validate the JSON job contract before queueing or rendering.

    This deliberately validates meaning and bounds, not every future optional
    feature. Unknown optional keys survive so saved requests remain forwards
    compatible, while unsafe paths and collisions are rejected.
    """
    spec = _mapping(spec, "job spec")
    if int(spec.get("schema_version", 0)) != 5:
        raise ValueError("job spec schema_version must be 5")
    job_id = str(spec.get("job_id", "auto"))
    if job_id != "auto":
        validate_id(job_id)
    source = _mapping(spec.get("source"), "source")
    path, url = source.get("path"), source.get("url")
    if bool(path) == bool(url):
        raise ValueError("source must contain exactly one of path or url")
    if path:
        source_path = Path(str(path))
        if root is not None and source_path.is_absolute() and not source_path.exists():
            raise ValueError("source path does not exist")
    candidate = _mapping(spec.get("candidate"), "candidate")
    validate_id(str(candidate.get("id", "")))
    start = _number(candidate.get("start"), "candidate.start", 0)
    end = _number(candidate.get("end"), "candidate.end", 0)
    if end <= start:
        raise ValueError("candidate.end must be after candidate.start")
    edits = candidate.get("edits", [])
    if not isinstance(edits, list):
        raise ValueError("candidate.edits must be a list")
    for edit in edits:
        row = _mapping(edit, "candidate edit")
        a, b = _number(row.get("start"), "edit.start", 0), _number(row.get("end"), "edit.end", 0)
        if b <= a or a < start or b > end:
            raise ValueError("edit must be inside candidate and have positive duration")
    preset = str(spec.get("preset", ""))
    validate_id(preset)
    headline = _mapping(spec.get("headline", {}), "headline")
    if headline.get("text") is not None and len(str(headline["text"])) > 78:
        raise ValueError("headline exceeds the hard 78-character limit")
    output = _mapping(spec.get("output", {}), "output")
    if output.get("crf") is not None and not 0 <= _number(output["crf"], "output.crf") <= 51:
        raise ValueError("output.crf must be between 0 and 51")
    if output.get("fps") not in (None, "source_capped"):
        fps = _number(output["fps"], "output.fps", 1)
        if fps > 120:
            raise ValueError("output.fps is outside the supported range")
    layout = _mapping(spec.get("layout", {}), "layout")
    if layout.get("mode") not in {None, "auto", "manual", "SINGLE", "DUAL", "WIDE"}:
        raise ValueError("unsupported layout mode")
    return spec


def validate_render_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan = _mapping(plan, "render plan")
    if int(plan.get("schema_version", 0)) != 5:
        raise ValueError("render plan schema_version must be 5")
    source = _mapping(plan.get("source"), "render plan source")
    for key in ("path", "source_id", "sha256", "width", "height"):
        if not source.get(key):
            raise ValueError(f"render plan source.{key} is required")
    trim = _mapping(plan.get("trim"), "render plan trim")
    start, end = _number(trim.get("start"), "trim.start", 0), _number(trim.get("end"), "trim.end", 0)
    duration = _number(trim.get("duration"), "trim.duration", 0)
    source_span_duration = None
    if isinstance(plan.get("source_spans"), list) and plan["source_spans"]:
        try:
            source_span_duration = sum(float(span["end"]) - float(span["start"]) for span in plan["source_spans"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("render plan source_spans are invalid")
    duration_matches = abs(duration - (end - start)) <= .001 or source_span_duration is not None and abs(duration - source_span_duration) <= .001
    if end <= start or not duration_matches:
        raise ValueError("render plan trim duration does not match start/end")
    if not isinstance(plan.get("framing"), dict) or not plan["framing"].get("path"):
        raise ValueError("render plan needs a framing path")
    if not plan.get("config_hash") or not plan.get("plan_hash"):
        raise ValueError("render plan needs config_hash and plan_hash")
    return plan


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    report = _mapping(report, "report")
    if int(report.get("schema_version", 0)) != 5:
        raise ValueError("report schema_version must be 5")
    if report.get("status") not in {"passed", "needs_review", "failed"}:
        raise ValueError("report status is invalid")
    checks = report.get("checks")
    if not isinstance(checks, list):
        raise ValueError("report checks must be a list")
    for check in checks:
        row = _mapping(check, "report check")
        if not isinstance(row.get("name"), str) or not isinstance(row.get("passed"), bool):
            raise ValueError("each report check needs a name and boolean passed field")
    return report


def validate_artifact(name: str, artifact: dict[str, Any]) -> dict[str, Any]:
    validate_id(name)
    artifact = _mapping(artifact, name)
    if int(artifact.get("schema_version", 0)) != 5:
        raise ValueError(f"{name} artifact schema_version must be 5")
    if name in {"shots", "signals", "acoustics", "turns", "receipt"} and not artifact.get("cache_key"):
        raise ValueError(f"{name} artifact needs cache_key")
    if name == "shots" and not isinstance(artifact.get("shots"), list):
        raise ValueError("shots artifact needs a shots list")
    if name == "signals" and not isinstance(artifact.get("reaction_events", []), list):
        raise ValueError("signals reaction_events must be a list")
    if name == "turns" and not isinstance(artifact.get("turns"), list):
        raise ValueError("turns artifact needs a turns list")
    return artifact
