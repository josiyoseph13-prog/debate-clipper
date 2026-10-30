"""Complete-directory export handoff and hash-checked interrupted recovery."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from .hashing import file_hash
from .io import atomic_write_json,read_json
from .locking import exclusive_file
from .process import check_cancelled
from .security import validate_id


def _complete(folder: Path, manifest_hash: str | None = None) -> bool:
    manifest=folder/"bundle_manifest.json"
    if not manifest.is_file() or (manifest_hash and file_hash(manifest)!=manifest_hash):return False
    record=read_json(manifest,{}) or {}
    if not record.get("complete") or not record.get("files"):return False
    for name,digest in record["files"].items():
        path=folder/name
        if not path.resolve().is_relative_to(folder.resolve()) or path.is_symlink() or not path.is_file() or file_hash(path)!=digest:return False
    return True


def _recover(job: Path, exports: Path) -> list[dict]:
    recovered=[]
    for journal in job.glob("bundle_transaction_*.json"):
        record=read_json(journal,{}) or {}
        if record.get("phase") not in {"ready","previous_moved"}:continue
        target=Path(record["target"])
        stage=Path(record["stage"])
        backup=Path(record["backup"])
        if target.resolve().parent!=exports.resolve() or target.is_symlink() or stage.resolve().parent!=job.resolve() or backup.resolve().parent!=job.resolve():
            raise ValueError("Export journal paths escape their owned folders")
        expected=record.get("manifest_sha256")
        if _complete(target,expected):
            action="complete_bundle_already_present"
        elif _complete(stage,expected):
            if target.exists():
                if backup.exists():raise RuntimeError("Both prior export locations exist; preserve them for review")
                os.replace(target,backup)
            os.replace(stage,target)
            action="promoted_complete_bundle"
        elif not target.exists() and backup.exists():
            os.replace(backup,target)
            action="restored_previous_bundle"
        else:
            action="needs_rebuild_previous_preserved"
        record.update({"phase":"committed" if _complete(target,expected) else "needs_rebuild","recovery":action})
        atomic_write_json(journal,record)
        recovered.append({"target":str(target),"action":action})
    return recovered


def recover_export_bundles(job: Path, exports: Path) -> list[dict]:
    with exclusive_file(job/"bundle_execution.lock"):
        return _recover(job,exports)


def write_complete_bundle(job: Path, target: Path, build):
    """Build in work, journal, then move a complete directory into exports.

    Prior bundles are retained in work. A crash after moving the old directory
    is recovered from the ready journal; no partially built files enter exports.
    """
    validate_id(target.name)
    job.mkdir(parents=True,exist_ok=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():raise ValueError("Export target must not be a symlink")
    with exclusive_file(job/"bundle_execution.lock"):
        _recover(job,target.parent)
        stage=Path(tempfile.mkdtemp(prefix="bundle_stage_",dir=job))
        backup=job/("bundle_previous_"+stage.name.removeprefix("bundle_stage_"))
        journal=job/f"bundle_transaction_{target.name}.json"
        record={"schema_version":5,"phase":"building","stage":str(stage.resolve()),"target":str(target.resolve()),"backup":str(backup.resolve())}
        atomic_write_json(journal,record)
        result=build(stage)
        if not isinstance(result, dict):
            result={"result": result}
        files={str(path.relative_to(stage)):file_hash(path) for path in stage.rglob("*") if path.is_file()}
        if not files or any(name.endswith(".part") for name in files):raise ValueError("Bundle contains incomplete output")
        atomic_write_json(stage/"bundle_manifest.json",{"schema_version":5,"complete":True,"stable_id":result.get("stable_id", target.name),"created_at":datetime.now(timezone.utc).isoformat(),"files":files})
        if not _complete(stage):raise ValueError("Export bundle hash verification failed")
        check_cancelled()
        record.update({"phase":"ready","manifest_sha256":file_hash(stage/"bundle_manifest.json")})
        atomic_write_json(journal,record)
        try:
            if target.exists():
                os.replace(target,backup)
                record["phase"]="previous_moved"
                atomic_write_json(journal,record)
            os.replace(stage,target)
        except BaseException:
            if not target.exists() and backup.exists():os.replace(backup,target)
            raise
        record["phase"]="committed"
        atomic_write_json(journal,record)
        return result
