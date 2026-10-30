from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_QUERY = re.compile(r"(https?://[^\s?]+)\?[^\s]+", re.I)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _QUERY.sub(r"\1?[REDACTED]", value)
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if any(part in str(key).lower() for part in ("token", "secret", "password", "api_key")) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def log_event(path: Path, job_id: str, stage: str, event: str, **fields: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema_version":5,"time": datetime.now(timezone.utc).isoformat(), "job_id": job_id, "correlation_id":job_id,"stage": stage, "event": event, **fields}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(row), ensure_ascii=False) + "\n")
