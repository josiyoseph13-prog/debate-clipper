from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def content_hash(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, Path):
        return file_hash(value)
    else:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    from .process import check_cancelled
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            check_cancelled()
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    size = stat.st_size
    with path.open("rb") as handle:
        first = handle.read(min(size, 1024 * 1024))
        if size > 1024 * 1024:
            handle.seek(max(0, size - 1024 * 1024))
        last = handle.read(min(size, 1024 * 1024))
    return {
        "schema_version": 5,
        "size": size,
        "mtime_ns": stat.st_mtime_ns,
        "first_last_hash": content_hash(first + last),
        "sha256": file_hash(path),
    }
