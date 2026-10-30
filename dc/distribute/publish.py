from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..integrity import publish_gate


def dry_run(candidate: dict[str, Any], source: dict[str, Any], config) -> dict[str, Any]:
    allowed, reasons = publish_gate(candidate, source, config)
    return {"schema_version": 5, "allowed": allowed, "reasons": reasons, "privacy": config.get("distribution", "publish", "default_privacy", default="private"), "require_click": True}


def append_publish_log(path: Path, platform: str, clip_id: str, privacy: str = "private") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "platform": platform, "clip_id": clip_id, "privacy": privacy}, ensure_ascii=False) + "\n")
