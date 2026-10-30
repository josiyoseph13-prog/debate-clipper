"""Durable request identity for Review's Export button (not an export queue)."""
from datetime import datetime, timezone
from pathlib import Path

from ..core.hashing import content_hash
from ..core.io import atomic_write_json, read_json
from ..core.security import validate_id


FRAMING_DEFAULTS = {"layout": "auto", "zoom": 1.0, "move_x": 0.0, "move_y": 0.0}
CAPTION_DEFAULTS = {"size_delta": 0.0, "vertical_delta": 0.0, "highlight_color": "#B4F83D", "style": "hormozi_glow"}


def edit_snapshot(candidate: dict, decision: dict) -> dict:
    """Approval timestamps/actions do not change the exported edit revision."""
    edits = decision.get("edits", {}) or {}
    snapshot = {
        "headline": decision["headline"] if "headline" in decision else next(iter(candidate.get("hook", {}).get("headline_options", [])), "A possible moment"),
        "edits": {key: float(edits.get(key, candidate.get(key, 0))) for key in ("start", "end")},
        "framing_controls": {**FRAMING_DEFAULTS, **(decision.get("framing_controls", {}) or {})},
        "caption_controls": {**CAPTION_DEFAULTS, **(decision.get("caption_controls", {}) or {})},
    }
    if decision.get("framing_pins"):
        snapshot["framing_pins"] = [
            {key: (round(float(value), 4) if isinstance(value, (int, float)) else value) for key, value in pin.items()}
            for pin in decision["framing_pins"] if isinstance(pin, dict)
        ]
    if decision.get("framing_shape"):
        snapshot["framing_shape"] = str(decision["framing_shape"])
    for field in ("framing_controls", "caption_controls"):
        snapshot[field] = {key: float(value) if isinstance(value, (int, float)) else value for key, value in snapshot[field].items()}
    for key in ("layout", "crop", "palette", "caption_mode", "speaker_labels", "speaker_frame", "claim_checks", "accept_review"):
        if decision.get(key):
            snapshot[key] = decision[key]
    return snapshot


def edit_revision(candidate: dict, decision: dict) -> str:
    return content_hash(edit_snapshot(candidate, decision))


class ReviewExports:
    def __init__(self, root: Path):
        self.root = root
        self.folder = root / "work" / "review_exports"

    def get(self, export_id: str) -> dict | None:
        validate_id(export_id)
        path = self.folder / f"{export_id}.json"
        return read_json(path, None) if not path.is_symlink() else None

    def rows(self) -> list[dict]:
        if self.folder.is_symlink():
            return []
        rows = [read_json(path, {}) for path in self.folder.glob("export_*.json") if not path.is_symlink()]
        return sorted((row for row in rows if isinstance(row, dict) and row.get("export_id")), key=lambda row: row.get("started_at", ""), reverse=True)

    def save(self, row: dict) -> dict:
        export_id = validate_id(row["export_id"])
        if self.folder.is_symlink():
            raise ValueError("Export request path escapes work root")
        self.folder.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.folder / f"{export_id}.json", row)
        return row

    def create(self, export_id: str, record: dict) -> dict:
        return self.save({
            "schema_version": 1, "export_id": export_id, "job_id": record["job_id"], "candidate_id": record["id"],
            "source_id": record.get("source_id"), "source_group_id": record.get("source_group_id"),
            "title": record.get("decision", {}).get("headline") if "headline" in record.get("decision", {}) else next(iter(record.get("hook", {}).get("headline_options", [])), "Clip"),
            "source_title": record.get("source", {}).get("title", "Debate video"),
            "edit_revision": edit_revision(record, record.get("decision", {})),
            "settings": edit_snapshot(record, record.get("decision", {})),
            "decision": record.get("decision", {}), "account_snapshot": None,
            "status": "exporting", "stage": "Preparing the video", "started_at": datetime.now(timezone.utc).isoformat(),
        })

    def finish(self, row: dict, status: str, reason: str = "", export: dict | None = None) -> dict:
        return self.save({**row, "status": status, "reason": reason, "finished_at": datetime.now(timezone.utc).isoformat(), "export": export})
