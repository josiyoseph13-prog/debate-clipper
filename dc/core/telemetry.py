"""Durable stage timing and resource telemetry."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .io import atomic_write_json, read_json


def _resources() -> dict[str, Any]:
    result = {"cpu_count": os.cpu_count()}
    try:
        import psutil
        result.update({"rss_bytes": psutil.Process().memory_info().rss, "cpu_percent": psutil.Process().cpu_percent(None)})
    except ImportError:
        pass
    return result


@contextmanager
def stage_timer(job: Path, stage: str, *, extra: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    began = time.perf_counter()
    row = {"schema_version": 5, "stage": stage, "started": time.time(), "resources_start": _resources(), **(extra or {})}
    try:
        yield row
        row["status"] = "passed"
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = str(exc)
        raise
    finally:
        row["elapsed_s"] = round(time.perf_counter() - began, 6)
        row["resources_end"] = _resources()
        path = Path(job) / "telemetry.json"
        data = read_json(path, {}) or {}
        data.setdefault("schema_version", 5)
        data.setdefault("stages", []).append(row)
        atomic_write_json(path, data)
