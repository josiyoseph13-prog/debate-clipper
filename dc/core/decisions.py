from __future__ import annotations

from pathlib import Path
from typing import Any
import threading
_DECISION_LOCK=threading.RLock()

from .io import atomic_write_json, read_json


def decisions_path(root: Path) -> Path:
    return root / "work" / "decisions.json"


def job_decisions_path(root: Path, job_id: str) -> Path:
    return root / "work" / job_id / "decisions.json"


def record_decision(root: Path, decision: dict[str, Any]) -> dict[str, Any]:
    from .locking import exclusive_file
    with _DECISION_LOCK:
        with exclusive_file(root/"work"/"decisions.lock",blocking=True):
            return _record_decision(root,decision)


def _record_decision(root: Path, decision: dict[str, Any]) -> dict[str, Any]:
    path = decisions_path(root)
    artifact = read_json(path, {"schema_version": 5, "decisions": []}) or {"schema_version": 5, "decisions": []}
    artifact.setdefault("decisions", []).append(decision)
    atomic_write_json(path, artifact)
    job_id = str(decision.get("job_id", ""))
    if job_id:
        job_path = job_decisions_path(root, job_id)
        job_artifact = read_json(job_path, {"schema_version": 5, "decisions": []}) or {"schema_version": 5, "decisions": []}
        job_artifact.setdefault("decisions", []).append(decision)
        atomic_write_json(job_path, job_artifact)
    return decision


def latest_decision(root: Path, job_id: str, candidate_id: str) -> dict[str, Any]:
    artifact = read_json(job_decisions_path(root, job_id), {"decisions": []}) or {"decisions": []}
    matches = [row for row in artifact.get("decisions", []) if row.get("candidate_id") == candidate_id]
    if not matches:
        return {}
    result: dict[str, Any] = {}
    claim_checks: dict[str, Any] = {}
    for row in matches:
        # A save records edit fields without changing the clip's review decision.
        # Keep the most recent approve/reject action authoritative for badges/counts.
        if row.get("action") in {"approve", "reject"}:
            result["action"] = row["action"]
        if "headline" in row:
            result["headline"] = row["headline"]
        if isinstance(row.get("edits"), dict):
            result.setdefault("edits", {}).update(row["edits"])
        for key in ("layout", "crop", "palette", "caption_mode", "speaker_labels", "framing_controls", "caption_controls", "accept_review", "speaker_frame"):
            if key in row:
                if key in {"speaker_labels", "framing_controls", "caption_controls"}:
                    result.setdefault(key, {}).update(row[key])
                else:
                    result[key] = row[key]
        if "framing_pins" in row:
            if row["framing_pins"]:
                result["framing_pins"] = row["framing_pins"]
            else:
                result.pop("framing_pins", None)
        if "framing_shape" in row:
            if row["framing_shape"]:
                result["framing_shape"] = row["framing_shape"]
            else:
                result.pop("framing_shape", None)
        if isinstance(row.get("claim_checks"), dict):
            claim_checks.update(row["claim_checks"])
        result["time"] = row.get("time")
    if claim_checks:
        result["claim_checks"] = claim_checks
    return result
