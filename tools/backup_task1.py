"""Copy the working Task 1 code/assets and verify every copied file hash."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.hashing import file_hash
from dc.core.io import atomic_copy,atomic_write_json
from dc.core.config import load_config


def main():
    task=int(sys.argv[1]) if len(sys.argv)>1 else 1
    if task not in {1,2,3}:
        raise ValueError("Task must be 1, 2, or 3")
    destination=ROOT/f"backups/after_task_{task}"
    if destination.is_symlink():
        raise ValueError("Invalid backup path")
    destination.mkdir(parents=True,exist_ok=True)
    sources=[]
    suffixes={".py",".json",".md",".ps1",".txt",".in",".lock",".ini",".js",".cjs",".html",".css"}
    sources.extend(path for path in ROOT.iterdir() if path.is_file() and (path.suffix in suffixes or path.name==".gitignore"))
    for name in ("dc","config","tests","tools","docs","assets"):
        sources.extend(path for path in (ROOT/name).rglob("*") if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"))
    sources.append(ROOT/f"reports/checkpoints/CHECKPOINT_{task}.md")
    watch=ROOT/({1:"reports/fix3/WATCH_TASK_1.html",2:"reports/speaker_frame/WATCH_TASK_2.html",3:"reports/duo_style/WATCH_TASK_3.html"}[task])
    if watch.is_file():sources.append(watch)
    sources.append(ROOT/load_config().get("header","logo","file"))
    rows=[]
    for source in sorted(set(sources)):
        relative=source.relative_to(ROOT)
        target=destination/relative
        if source.is_symlink():
            raise ValueError(f"Unexpected symlink in backup source: {relative}")
        digest=file_hash(source)
        if target.exists():
            if file_hash(target)!=digest:
                raise ValueError(f"Existing backup differs; refusing to overwrite: {relative}")
        else:
            atomic_copy(source,target)
        if file_hash(target)!=digest:
            raise ValueError(f"Backup hash mismatch: {relative}")
        rows.append({"path":relative.as_posix(),"sha256":digest,"size_bytes":source.stat().st_size})
    result={"task":task,"verified":True,"files":rows,"file_count":len(rows),"total_bytes":sum(row["size_bytes"] for row in rows),"note":"Working code, tests, configuration, tools, documents, and assets. Media inputs, exports, runtime environments, and job state are outside this code snapshot."}
    atomic_write_json(destination/"BACKUP_MANIFEST.json",result)
    print(json.dumps({key:result[key] for key in ("task","verified","file_count","total_bytes")},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
