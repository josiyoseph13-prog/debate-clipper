from __future__ import annotations

from pathlib import Path
from .core.hashing import content_hash
from .core.io import read_json, atomic_write_json


class ArtifactCache:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: object, suffix: str = ".json") -> Path:
        return self.root / f"{content_hash(key)}{suffix}"

    def get(self, key: object):
        return read_json(self.path(key))

    def put(self, key: object, value: object) -> Path:
        path = self.path(key)
        atomic_write_json(path, value)
        return path
