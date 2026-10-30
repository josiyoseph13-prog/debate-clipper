from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_ledger(path: Path, feature: str, level: str, evidence: str, note: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": datetime.now(timezone.utc).isoformat(), "feature": feature, "level": level, "evidence": evidence, "note": note}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
