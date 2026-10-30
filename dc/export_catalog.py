"""Human-readable export names and a safe local export catalog."""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slug(value: object, fallback: str = "clip", limit: int = 64) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "")).strip("-").lower()
    return (text[:limit].strip("-") or fallback)


def _time_label(seconds: float) -> str:
    value = max(0, int(round(float(seconds))))
    return f"{value // 60}m{value % 60:02d}s"


def _short_title(headline: object, candidate: dict[str, Any]) -> str:
    return str(headline or candidate.get("hook", {}).get("headline_options", ["Untitled clip"])[0])


def export_names(
    exports_root: Path,
    job_id: str,
    source: dict[str, Any],
    candidate: dict[str, Any],
    headline: str,
    rank: int,
    plan_hash: str,
) -> tuple[Path, str]:
    """Return a deterministic, safe folder and readable MP4 filename."""
    date = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    source_name = source.get("meta", {}).get("title") or Path(str(source.get("path", "source"))).stem
    source_folder = f"{date}_{_slug(source_name, 'source', 48)}"
    start = _time_label(float(candidate.get("start", 0)))
    end = _time_label(float(candidate.get("end", 0)))
    title = _slug(_short_title(headline, candidate), "clip", 56)
    clip_folder = f"clip_{int(rank):02d}_{title}_{start}-{end}_{str(candidate.get('id', 'clip'))}_{plan_hash[:8]}"
    file_name = f"{int(rank):02d}_{title}.mp4"
    target = exports_root / source_folder / clip_folder
    return target, file_name


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _safe_export_folder(root: Path, key: str) -> Path | None:
    parts = [part for part in str(key).replace("\\", "/").split("/") if part]
    if not parts or any(part in {".", "..", "_LATEST"} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", part) for part in parts):
        return None
    folder = (root.joinpath(*parts)).resolve()
    root = root.resolve()
    if root not in folder.parents or not folder.is_dir() or folder.is_symlink():
        return None
    return folder


def _relative_key(root: Path, folder: Path) -> str:
    return folder.resolve().relative_to(root.resolve()).as_posix()


def _clip_file(folder: Path) -> Path | None:
    preferred = [path for path in folder.glob("*.mp4") if path.name != "clip.mp4" and not path.is_symlink()]
    if preferred:
        return sorted(preferred)[0]
    fallback = folder / "clip.mp4"
    return fallback if fallback.is_file() and not fallback.is_symlink() else None


def catalog(exports_root: Path) -> list[dict[str, Any]]:
    """Read old and new exports without changing or deleting them."""
    if not exports_root.is_dir():
        return []
    folders: list[Path] = []
    for child in exports_root.iterdir():
        if child.name.startswith("_") or child.is_symlink() or not child.is_dir():
            continue
        if (child / "bundle_manifest.json").is_file():
            folders.append(child)
        else:
            folders.extend(folder for folder in child.iterdir() if folder.is_dir() and not folder.is_symlink() and (folder / "bundle_manifest.json").is_file())
    rows = []
    for folder in folders:
        clip = _clip_file(folder)
        if not clip:
            continue
        metadata = _read_json(folder / "metadata.json")
        candidate = _read_json(folder / "candidate.json")
        report = _read_json(folder / "export_report.json")
        source_title = metadata.get("source_title") or metadata.get("source") or "Source video"
        title = metadata.get("title") or candidate.get("hook", {}).get("headline_options", [folder.name])[0]
        plan = _read_json(folder / "render_plan.json")
        trim = plan.get("trim", {})
        manifest = _read_json(folder / "bundle_manifest.json")
        key = _relative_key(exports_root, folder)
        rows.append({
            "key": key,
            "stable_id": manifest.get("stable_id") or candidate.get("id") or folder.name,
            "export_id": plan.get("export_id"),
            "edit_revision": _edit_revision(candidate, plan),
            "folder": str(folder.resolve()),
            "clip": str(clip.resolve()),
            "clip_name": clip.name,
            "cover": f"/api/exports/{key}/cover" if (folder / "cover.jpg").is_file() else None,
            "file_url": f"/api/exports/{key}/media",
            "title": str(title),
            "source_title": str(source_title),
            "start": float(trim.get("start", candidate.get("start", 0)) or 0),
            "end": float(trim.get("end", candidate.get("end", 0)) or 0),
            "date": datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
            "size": clip.stat().st_size,
            "status": report.get("status", "finished"),
            "report": report,
            "publish_allowed": bool(_read_json(folder / "publish_dry_run.json").get("allowed", False)),
        })
    return sorted(rows, key=lambda row: (row["date"], row["key"]), reverse=True)


def _edit_revision(candidate: dict, plan: dict) -> str | None:
    if not plan.get("decision"):
        return None
    from .studio.review_exports import edit_revision
    return edit_revision(candidate, plan["decision"])


def refresh_export_catalog(exports_root: Path) -> list[dict[str, Any]]:
    """Refresh INDEX.html and the newest readable MP4 copies."""
    exports_root.mkdir(parents=True, exist_ok=True)
    rows = catalog(exports_root)
    latest = exports_root / "_LATEST"
    latest.mkdir(exist_ok=True)
    for path in latest.iterdir():
        if path.is_file() and not path.is_symlink():
            path.unlink()
    for row in rows[:20]:
        source = Path(row["clip"])
        if source.is_file() and not source.is_symlink():
            shutil.copy2(source, latest / source.name)
    entries = []
    for row in rows:
        try:
            local_clip = Path(row["clip"]).as_uri()
        except ValueError:
            local_clip = "file:///" + str(row["clip"]).replace("\\", "/").lstrip("/")
        cover_path = Path(row["folder"]) / "cover.jpg"
        try:
            local_cover = cover_path.as_uri()
        except ValueError:
            local_cover = "file:///" + str(cover_path).replace("\\", "/").lstrip("/")
        cover = f'<img src="{html.escape(local_cover, quote=True)}" alt="" loading="lazy">' if row["cover"] else ""
        entries.append(
            "<article>"
            f"{cover}<h2>{html.escape(row['title'])}</h2>"
            f"<p>{html.escape(row['source_title'])} · {row['start']:.2f}s to {row['end']:.2f}s · {html.escape(row['date'])}</p>"
            f"<p>Status: {html.escape(str(row['status']))}</p>"
            f'<a href="{html.escape(local_clip, quote=True)}">Open video</a>'
            "</article>"
        )
    document = "<!doctype html><meta charset='utf-8'><title>Debate Clipper exports</title><style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;background:#f6f8fb}article{background:white;border:1px solid #e3e8ef;border-radius:14px;padding:1rem;margin:1rem 0}img{width:120px;max-height:210px;object-fit:cover;float:left;margin-right:1rem}h1{color:#1f385e}</style><h1>Debate Clipper exports</h1>" + "".join(entries)
    (exports_root / "INDEX.html").write_text(document, encoding="utf-8")
    return rows


def find_export(exports_root: Path, key: str) -> Path | None:
    return _safe_export_folder(exports_root, key)
