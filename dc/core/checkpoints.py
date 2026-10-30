"""Hash-verified, job-local stage commits; incomplete stages are never hits."""
from __future__ import annotations
from pathlib import Path
from .hashing import file_hash
from .io import atomic_write_json,read_json
from .security import validate_id


class StageCheckpoints:
    def __init__(self,job:Path):
        self.job=Path(job)

    def _path(self,name):
        path=self.job/name
        if path.is_symlink() or not path.resolve().is_relative_to(self.job.resolve()):
            raise ValueError("Checkpoint artifact escapes its job")
        return path

    def valid(self,stage:str,key:str,names:list[str])->bool:
        validate_id(stage)
        try:
            record=read_json(self._path(f"checkpoint_{stage}.json"),{}) or {}
            if not isinstance(record,dict) or not isinstance(record.get("files"),dict):return False
            if record.get("schema_version")!=5 or record.get("cache_key")!=key or set(record.get("files",{}))!=set(names):return False
            return all(self._path(name).is_file() and file_hash(self._path(name))==record["files"][name] for name in names)
        except (OSError,ValueError,TypeError):
            return False

    def commit(self,stage:str,key:str,names:list[str])->dict:
        validate_id(stage)
        if not names:raise ValueError("A checkpoint needs at least one artifact")
        files={name:file_hash(self._path(name)) for name in names}
        record={"schema_version":5,"stage":stage,"cache_key":key,"files":files}
        atomic_write_json(self._path(f"checkpoint_{stage}.json"),record)
        return record
