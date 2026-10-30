import base64
import hashlib
import json
import math
import mimetypes
import ipaddress
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..core.config import ROOT, load_config
from ..core.decisions import latest_decision, record_decision
from ..core.io import atomic_write_bytes, atomic_write_json, read_json
from ..core.jobs import JobStore
from ..core.locking import ResourceBusy
from ..core.security import escape_text, new_token, origin_is_local, validate_id
from ..export_catalog import catalog, find_export
from .review_exports import ReviewExports, edit_revision


def _candidate_records() -> list[dict]:
    records = []
    for candidate_file in sorted((ROOT / "work").glob("*/candidates.json")):
        job_dir = candidate_file.parent
        if job_dir.is_symlink():
            continue
        job_id = job_dir.name
        artifact = read_json(candidate_file, {}) or {}
        source = read_json(job_dir / "source.json", {}) or {}
        group = read_json(job_dir / "source_group.json", {}) or {}
        source_id = source.get("source_id") or source.get("fingerprint", {}).get("sha256") or group.get("group_id") or f"job:{job_id}"
        source_group_id = group.get("group_id") or source_id
        source_group_title = group.get("title") or source.get("meta", {}).get("title") or Path(str(source.get("path", "source"))).stem
        run_created_at = group.get("created_at")
        transcript = read_json(job_dir / "transcript.json", {}) or {}
        render_plan = read_json(job_dir / "render_plan.json", {}) or {}
        polish = read_json(job_dir / "polish.json", {}) or {}
        for candidate in artifact.get("candidates", []):
            words = [word for segment in transcript.get("segments", []) for word in segment.get("words", []) if float(word.get("end", 0)) > float(candidate.get("start", 0)) and float(word.get("start", 0)) < float(candidate.get("end", 0))]
            from ..captions import transcript_words
            global_words = transcript_words(transcript)
            record_words = [word for word in global_words if float(candidate.get("start",0))-3 <= word["start"] <= float(candidate.get("end",0))+3]
            decision = latest_decision(ROOT, job_id, candidate["id"])
            from ..integrity import verify_claims
            reviewed = verify_claims(candidate, decision.get("claim_checks", {}))
            saved = render_plan if render_plan.get("candidate_id") == candidate["id"] else {}
            changes = sorted({0.0, *[float(segment["t0"]) for segment in saved.get("framing", {}).get("segments", [])], *[float(item["start"]) for item in saved.get("craft", {}).values() if isinstance(item, dict) and "start" in item], *[float(item["t"]) for item in polish.get("punch_ins", []) if saved and "t" in item]})
            duration = float(saved.get("trim", {}).get("duration", candidate.get("duration", 0)))
            gaps = [[a,b] for a,b in zip(changes,changes[1:]+[duration]) if b-a>6]
            records.append({**reviewed, "job_id": job_id, "run_id": job_id, "source_id": source_id, "source_group_id": source_group_id, "decision": decision, "words": record_words, "framing": saved.get("framing"), "visual_changes": changes, "pacing_gaps": gaps, "source": {"title": source_group_title, "duration": source.get("duration"), "width":source.get("width"), "height":source.get("height"), "rights_class": source.get("rights_class", "unknown"), "source_id": source_id, "source_group_id": source_group_id, "run_id": job_id, "run_created_at": run_created_at}})
    exports = {}
    for row in catalog(ROOT / "exports"):
        exports.setdefault(row.get("stable_id"), row)
    for record in records:
        record["export"] = exports.get(record.get("id"))
        record["export_report"] = (record["export"] or {}).get("report")
        record["edit_revision"] = edit_revision(record, record.get("decision", {}))
    return records


def _candidate_file(file_id: str) -> Path | None:
    try:
        validate_id(file_id)
    except ValueError:
        return None
    roots = [ROOT / "work", ROOT / "exports"]
    for root in roots:
        if not root.exists():
            continue
        for folder in root.iterdir():
            if not folder.is_dir() or folder.is_symlink():
                continue
            path = folder / file_id
            if path.is_file() and not path.is_symlink() and path.resolve().parent == folder.resolve():
                return path
    return None


def _job_progress(job_id: str, state: str, stage: str) -> dict:
    """Expose only work that the job store has actually completed.

    The pipeline does not expose frame-level progress for every stage.  In that
    case the Studio reports the current stage and an indeterminate state instead
    of inventing a percentage.  The UI can therefore show honest activity while
    the job continues in the background.
    """
    labels = {
        "queued": "Starting",
        "ingest": "Checking your video",
        "transcribe": "Listening to the debate",
        "select": "Finding the best moments",
        "review": "Preparing your clips",
        "render": "Making your video",
        "qa": "Checking the finished video",
        "failed": "Something went wrong",
        "cancel": "Stopped",
    }
    stages = ["ingest", "transcribe", "select", "review"]
    if state in {"awaiting_review", "passed"}:
        return {"percent": None, "known": False, "label": "Done", "stage": "review", "stage_index": len(stages), "stage_count": len(stages)}
    current = stage if stage in stages else "queued" if state == "queued" else stage
    if state in {"failed", "cancelled"}:
        label = "Stopped" if state == "cancelled" else labels.get(current, "Something went wrong")
    else:
        label = labels.get(current, "Working")
    return {
        "percent": None,
        "known": False,
        "label": label,
        "stage": current,
        "stage_index": stages.index(current) + 1 if current in stages else 0,
        "stage_count": len(stages),
    }


def _youtube_video_id(value: str) -> str | None:
    """Return a structurally valid YouTube video ID, or None.

    Studio accepts normal watch, short, embed, live, and youtu.be links. This
    is intentionally an offline structural check; the downloader remains the
    source of truth for whether the video is currently reachable.
    """
    try:
        url = urlparse(value)
        host = (url.hostname or "").lower().removeprefix("www.")
        if url.scheme not in {"http", "https"}:
            return None
        if host == "youtu.be":
            candidate = url.path.strip("/").split("/", 1)[0]
        elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
            candidate = parse_qs(url.query).get("v", [""])[0]
            if not candidate:
                parts = [part for part in url.path.split("/") if part]
                if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                    candidate = parts[1]
        else:
            return None
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None
    except (TypeError, ValueError):
        return None


def create_app(lan: bool = False, token: str | None = None):
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for Review Studio") from exc

    config = load_config()
    session_token = token or new_token(int(config.get("security", "lan", "token_bytes", default=24)))
    import threading
    render_lock = threading.Lock()
    start_lock = threading.Lock()
    review_exports = ReviewExports(ROOT)
    def review_export_rows():
        rows = review_exports.rows()
        # A dead server request must not leave Review permanently locked.
        if not render_lock.locked() and any(row["status"] == "exporting" for row in rows):
            from ..core.locking import exclusive_file
            try:
                with exclusive_file(ROOT / "work" / "studio_render.lock"):
                    rows = [review_exports.finish(row, "not_finished", "The export was interrupted. Try again.") if row["status"] == "exporting" else row for row in rows]
            except ResourceBusy:
                pass
        return rows
    app = FastAPI(docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        host = request.url.hostname or ""
        permitted_host = host in {"127.0.0.1", "localhost", "::1"}
        if lan and not permitted_host:
            try:
                address = ipaddress.ip_address(host)
                permitted_host = address.is_private and not address.is_unspecified
            except ValueError:
                pass
        if not permitted_host:
            return JSONResponse({"detail": "invalid Host"}, status_code=403)
        if lan and request.method == "GET" and request.url.path not in {"/api/health"}:
            presented = request.query_params.get("token") or request.cookies.get("dc_session") or request.headers.get("x-dc-token", "")
            if not secrets.compare_digest(presented, session_token):
                return JSONResponse({"detail": "LAN session token required"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not origin_is_local(request.headers.get("origin"), request.headers.get("host"), allow_lan=lan):
                return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
            if not secrets.compare_digest(request.headers.get("x-dc-token", ""), session_token):
                return JSONResponse({"detail": "session token required"}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = config.get("security", "csp", default="default-src 'self'")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def page_html(classic: bool = False):
        token_attr = escape_text(session_token)
        if classic:
            body = """<main class='classic-shell'><h1>Political Lens</h1><p>A score ranks clips; it does not predict virality.</p><div id='system'></div><label>Search <input id='search' placeholder='Find where someone dodges a question'></label><button id='search-button' type='button'>Find</button><label><input id='label-mode' type='checkbox'>Blind Label mode</label><div id='queue' data-token='{token}' data-lan='{lan}'>Loading review queue…</div></main>"""
        else:
            body = """<main id='studio-app' data-token='{token}' data-lan='{lan}'>
              <header class='brand-bar'>
                <a class='brand' href='/' aria-label='Debate Clipper home'><span class='brand-mark' aria-hidden='true'>DC</span><span>Debate Clipper</span></a>
                 <div class='system-mini' id='system' aria-live='polite'></div>
                 <button type='button' class='header-button' id='help-button'>Help</button>
                 <button type='button' class='header-button' id='my-exports'>My exports</button>
                 <a class='classic-link' href='/classic'>Classic view</a>
              </header>
              <nav class='steps' aria-label='Studio steps'>
                <button type='button' class='step active' data-view='home'><b>1</b><span>Add video</span></button>
                <button type='button' class='step' data-view='find'><b>2</b><span>Find clips</span></button>
                <button type='button' class='step' data-view='review'><b>3</b><span>Review</span></button>
                <button type='button' class='step' data-view='export'><b>4</b><span>Export</span></button>
              </nav>
               <div id='connection-bar' class='connection-bar' hidden> The Studio stopped. Restart it in PowerShell. </div>
               <div id='app-message' class='sr-only' aria-live='polite'></div>
               <section id='home-view' class='view active-view'></section>
               <section id='find-view' class='view'></section>
               <section id='review-view' class='view'></section>
               <section id='export-view' class='view'></section>
               <section id='exports-view' class='view'></section>
            </main>"""
        static_dir = Path(__file__).parent / "static"
        def static_version(name: str) -> str:
            try:
                return hashlib.sha256((static_dir / name).read_bytes()).hexdigest()[:12]
            except OSError:
                return "1"
        script = f"/static/classic.js?v={static_version('classic.js')}" if classic else f"/static/studio.js?v={static_version('studio.js')}"
        return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='color-scheme' content='light'><link rel='stylesheet' href='/static/studio.css?v={static_version('studio.css')}'><title>Debate Clipper</title></head><body>{body.format(token=token_attr,lan=str(lan).lower())}<script src='/static/speaker-frame.js?v={static_version('speaker-frame.js')}' defer></script><script src='{script}' defer></script></body></html>"

    @app.get("/", response_class=HTMLResponse)
    async def index():
        response = HTMLResponse(page_html())
        if lan:
            response.set_cookie("dc_session", session_token, httponly=True, samesite="strict")
        return response

    @app.get("/classic", response_class=HTMLResponse)
    async def classic():
        response = HTMLResponse(page_html(classic=True))
        if lan:
            response.set_cookie("dc_session", session_token, httponly=True, samesite="strict")
        return response

    @app.get("/brand/logo")
    async def brand_logo():
        logo = ROOT / config.get("header", "logo", "file", default="assets/logo.png")
        if not logo.is_file() or logo.is_symlink():
            raise HTTPException(status_code=404, detail="brand logo unavailable")
        return FileResponse(logo, media_type=mimetypes.guess_type(logo.name)[0] or "image/jpeg")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "bind": config.get("security", "bind", default="127.0.0.1"), "lan": lan}

    @app.get("/api/system")
    async def system():
        try:
            import psutil

            return {"cpu_percent": psutil.cpu_percent(interval=None), "ram_percent": psutil.virtual_memory().percent}
        except ImportError:
            return {"cpu_percent": None, "ram_percent": None}

    @app.get("/api/jobs")
    async def jobs():
        candidates = _candidate_records()
        with JobStore(ROOT / "work" / "jobs.sqlite").connect() as db:
            states = [dict(row) for row in db.execute("SELECT job_id,state,stage,heartbeat,stage_started_at,started_at FROM jobs ORDER BY heartbeat DESC")]
        for state in states:
            try:
                state["error"] = (json.loads(state.pop("payload", "{}")) or {}).get("error")
            except (TypeError, ValueError):
                state["error"] = None
            source = read_json(ROOT / "work" / state["job_id"] / "source.json", {}) or {}
            group = read_json(ROOT / "work" / state["job_id"] / "source_group.json", {}) or {}
            state["title"] = source.get("meta", {}).get("title") or Path(str(source.get("path", state["job_id"]))).stem
            state["source_url"] = source.get("source_url")
            state["source_id"] = source.get("source_id") or source.get("fingerprint", {}).get("sha256") or group.get("group_id")
            state["source_group_id"] = group.get("group_id") or state["source_id"]
            state["run_id"] = state["job_id"]
            state["duration"] = source.get("duration")
            title_text = str(state["title"]).lower()
            state["is_test"] = any(marker in (state["job_id"].lower() + " " + title_text) for marker in ("test", "acceptance", "crash", "cancel", "fixture", "browser", "asr_source"))
            state["progress"] = _job_progress(state["job_id"], state["state"], state.get("stage", ""))
            state["progress"]["stage_started_at"] = state.get("stage_started_at")
            state["progress"]["started_at"] = state.get("started_at")
        attempts = review_export_rows()
        for record in candidates:
            record["export_attempt"] = next((row for row in attempts if row["job_id"] == record["job_id"] and row["candidate_id"] == record["id"]), None)
        return {"schema_version": 5, "jobs": states, "candidates": sorted(candidates, key=lambda row: row.get("score", 0), reverse=True), "review_exports": attempts}

    @app.get("/api/exports")
    async def exports():
        return {"exports": catalog(ROOT / "exports")}

    @app.get("/api/exports/{export_key:path}/media")
    async def export_media(export_key: str):
        folder = find_export(ROOT / "exports", export_key)
        if not folder:
            raise HTTPException(status_code=404, detail="export not found")
        candidates = [path for path in folder.glob("*.mp4") if path.name != "clip.mp4" and not path.is_symlink()]
        path = sorted(candidates)[0] if candidates else folder / "clip.mp4"
        if not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=404, detail="export video not found")
        return FileResponse(path, media_type="video/mp4", filename=path.name)

    @app.get("/api/exports/{export_key:path}/cover")
    async def export_cover(export_key: str):
        folder = find_export(ROOT / "exports", export_key)
        path = folder / "cover.jpg" if folder else None
        if not path or not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=404, detail="cover not found")
        return FileResponse(path, media_type="image/jpeg")

    @app.post("/api/exports/{export_key:path}/open-folder")
    async def open_export_folder(export_key: str):
        if lan:
            raise HTTPException(status_code=403, detail="Opening folders is available only from localhost")
        folder = find_export(ROOT / "exports", export_key)
        if not folder:
            raise HTTPException(status_code=404, detail="export not found")
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(folder))
            elif shutil.which("explorer.exe"):
                subprocess.Popen(["explorer.exe", str(folder)], cwd=str(ROOT))
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(folder)], cwd=str(ROOT))
            else:
                return {"status": "unavailable", "path": str(folder)}
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not open the folder: {exc}") from exc
        return {"status": "opened", "path": str(folder)}

    @app.get("/api/jobs/{job_id}/log")
    async def job_log(job_id: str):
        try:
            validate_id(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid job id") from exc
        path = ROOT / "work" / job_id / "studio_run.log"
        if not path.is_file() or path.is_symlink():
            path = ROOT / "work" / "events.jsonl"
        if not path.is_file() or path.is_symlink():
            return {"log": "No details are available yet."}
        return {"log": path.read_text(encoding="utf-8", errors="replace")[-20000:]}

    @app.post("/api/start-job")
    async def start_job(request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="object required")
        rights = str(payload.get("rights_class", "unknown"))
        if rights not in {"own", "permission", "public_domain_verified", "licensed", "unknown"}:
            raise HTTPException(status_code=400, detail="invalid rights choice")
        source_url = str(payload.get("source_url", "")).strip()
        file_data = str(payload.get("file_data", ""))
        raw_file = None
        filename = None
        try:
            top = int(payload.get("top", 8))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Choose 5, 8, or 12 clips") from exc
        if top not in {5, 8, 12}:
            raise HTTPException(status_code=400, detail="Choose 5, 8, or 12 clips")
        source_arg = ""
        if source_url:
            if len(source_url) > 4096 or not _youtube_video_id(source_url):
                raise HTTPException(status_code=400, detail="That link doesn't look like a YouTube video. Check the link and try again.")
            source_arg = source_url
        elif file_data:
            filename = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("file_name", "video.mp4"))).strip(".")[:100] or "video.mp4"
            if "." not in filename:
                filename += ".mp4"
            try:
                raw_file = base64.b64decode(file_data, validate=True)
            except (ValueError, base64.binascii.Error) as exc:
                raise HTTPException(status_code=400, detail="The selected file could not be read") from exc
        else:
            raise HTTPException(status_code=400, detail="Paste a video link or choose a video file")
        from ..core.hashing import content_hash
        from ..cli import _job_id
        source_key = content_hash(source_url if source_url else raw_file)
        source_group_id = f"source_{source_key[:16]}"
        if source_url:
            base_job_id = f"job_{source_key[:12]}"
        else:
            base_job_id = f"job_{source_key[:12]}"
        store = JobStore(ROOT / "work" / "jobs.sqlite")
        with start_lock:
            existing = store.get(base_job_id)
            active_states = {"queued", "running", "rendering"}
            if existing and existing["state"] in active_states:
                existing_payload = {}
                try: existing_payload = json.loads(existing.get("payload", "{}")) or {}
                except (TypeError, ValueError): pass
                return {"status": "already_running", "job_id": base_job_id, "pid": existing_payload.get("pid"), "title": existing_payload.get("title") or source_url or filename or "Video", "source_group_id": existing_payload.get("source_group_id", source_group_id), "started_at": existing.get("started_at")}
            job_id = base_job_id if not existing else f"{base_job_id}_r{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            validate_id(job_id)
            if not source_url:
                source_path = ROOT / "input" / f"studio_{source_key[:16]}_{filename}"
                if not source_path.is_file(): atomic_write_bytes(source_path, raw_file)
                source_arg = str(source_path)
            job_dir = ROOT / "work" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(job_dir / "source_group.json", {"schema_version": 1, "group_id": source_group_id, "source_key": source_key, "title": source_url or filename or "Video", "run_id": job_id, "retry_of": None, "created_at": datetime.now(timezone.utc).isoformat()})
            log_path = job_dir / "studio_run.log"
            payload_record = {"source": source_arg, "source_group_id": source_group_id, "title": source_url or filename or "Video", "rights_class": rights, "rights_note": str(payload.get("rights_note", ""))[:500], "top": top}
            store.upsert(job_id, "queued", json.dumps(payload_record), "queued")
            log_handle = log_path.open("ab")
            command = [sys.executable, "-m", "dc", "run", "--source", source_arg, "--job", job_id, "--rights-class", rights, "--rights-note", str(payload.get("rights_note", ""))[:500], "--mode", "review", "--top", str(top)]
            try:
                process = subprocess.Popen(command, cwd=str(ROOT), stdout=log_handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=os.name != "nt")
            except OSError as exc:
                log_handle.close()
                store.upsert(job_id, "failed", json.dumps({"error": str(exc)}), "failed")
                raise HTTPException(status_code=500, detail=f"The job could not start: {exc}") from exc
            log_handle.close()
            payload_record["pid"] = process.pid
            store.upsert(job_id, "queued", json.dumps(payload_record), "queued")
        def announce_completion():
            return_code = process.wait()
            if return_code == 0:
                print(f"Debate Clipper: {job_id} is ready to review.", flush=True)
            else:
                print(f"Debate Clipper: {job_id} has a problem. Read work/{job_id}/studio_run.log.", flush=True)
        threading.Thread(target=announce_completion, daemon=True).start()
        return {"status": "started", "job_id": job_id, "pid": process.pid, "title": Path(source_arg).stem if not source_url else source_url, "source_group_id": source_group_id, "started_at": store.get(job_id).get("started_at")}

    @app.get("/api/search")
    async def search(q: str="", job: str=""):
        from ..selection import prompt_search
        records = [row for row in _candidate_records() if not job or row["job_id"]==job]
        return {"candidates": prompt_search(records,q,20)}

    @app.post("/api/fit")
    async def fit(request: Request):
        from ..layout import fit_headline
        payload=await request.json()
        return fit_headline(str(payload.get("headline",""))[:500],config)

    @app.get("/api/candidates/{job_id}/{candidate_id}")
    async def candidate_detail(job_id: str, candidate_id: str):
        try:
            validate_id(job_id)
            validate_id(candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid resource id") from exc
        row = next((item for item in _candidate_records() if item["job_id"] == job_id and item["id"] == candidate_id), None)
        if not row:
            raise HTTPException(status_code=404, detail="candidate not found")
        return row

    @app.get("/api/candidates/{job_id}/{candidate_id}/framing-presets")
    async def framing_presets(job_id: str, candidate_id: str, t: float = 0.0):
        try:
            validate_id(job_id)
            validate_id(candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid resource id") from exc
        record = next((item for item in _candidate_records() if item["job_id"] == job_id and item["id"] == candidate_id), None)
        if not record:
            raise HTTPException(status_code=404, detail="candidate not found")
        tracking = read_json(ROOT / "work" / job_id / "tracking.json", {}) or {}
        observations = tracking.get("observations", []) if isinstance(tracking, dict) else []
        from ..framing_pins import presets_from_tracking
        source = record.get("source", {}) or {}
        shape = (record.get("decision", {}) or {}).get("framing_shape") or "9:16"
        return presets_from_tracking(observations, float(t), int(source.get("width", 1920)), int(source.get("height", 1080)), config, shape)

    @app.get("/api/candidates/{job_id}/{candidate_id}/caption-cues")
    async def caption_cues(job_id: str, candidate_id: str, start: float | None = None, end: float | None = None, style: str | None = None, size_delta: float | None = None):
        try:
            validate_id(job_id)
            validate_id(candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid resource id") from exc
        record = next((item for item in _candidate_records() if item["job_id"] == job_id and item["id"] == candidate_id), None)
        if not record:
            raise HTTPException(status_code=404, detail="candidate not found")
        transcript = read_json(ROOT / "work" / job_id / "transcript.json", {}) or {}
        if not transcript:
            return {"available": False, "reason": "No transcript was found for this video, so there are no caption words to preview."}
        decision = latest_decision(ROOT, job_id, candidate_id)
        edits = decision.get("edits") or {}
        try:
            clip_start = float(edits.get("start", record.get("start", 0)))
            clip_end = float(edits.get("end", record.get("end", 0)))
        except (TypeError, ValueError):
            return {"available": False, "reason": "This clip has no valid time range yet."}
        if start is not None and end is not None and end > start:
            clip_start, clip_end = float(start), float(end)
        if clip_end <= clip_start:
            return {"available": False, "reason": "This clip has no valid time range yet."}
        # Build the cues with the production caption builder itself, with the
        # clip's saved caption settings applied exactly as dc.cli applies
        # them, so the Edit preview shows the same words, timing, size and
        # position the export will use (Phase 4D, Section 12.5).
        from ..captions import build_captions as _build_captions
        from ..core.config import AppConfig as _AppConfig, _deep_merge as _dm
        overrides: dict = {}
        if decision.get("palette"):
            overrides["captions"] = {"active": decision["palette"]}
        if decision.get("caption_mode"):
            overrides["craft"] = {"caption_mode": decision["caption_mode"]}
        saved_controls = decision.get("caption_controls", {}) or {}
        # Live session values (unsaved look/size) win over the saved ones,
        # so the preview shows what the export will use once saved.
        effective_controls = dict(saved_controls)
        if style is not None:
            if style not in {"hormozi_glow", "gravitas", "karaoke_lite"}:
                raise HTTPException(status_code=400, detail="invalid caption style")
            effective_controls["style"] = style
        if size_delta is not None:
            if not -30 <= size_delta <= 30:
                raise HTTPException(status_code=400, detail="invalid caption size")
            effective_controls["size_delta"] = size_delta
        if effective_controls:
            overrides.setdefault("captions", {}).update({"font_size_override": 110 + float(effective_controls.get("size_delta", 0)), "dy_override": float(effective_controls.get("vertical_delta", 0))})
            overrides["captions"]["active"] = effective_controls.get("highlight_color", overrides["captions"].get("active", "#B4F83D"))
            overrides["craft"] = {"caption_mode": effective_controls.get("style", overrides.get("craft", {}).get("caption_mode", "hormozi_glow"))}
        cue_config = _AppConfig(_dm(config.json(), overrides), config.path) if overrides else config
        if decision.get("framing_pins") and (decision.get("framing_shape") or "9:16") != "9:16":
            from ..framing_pins import shape_feed_config as _shape_feed_config
            cue_config = _shape_feed_config(cue_config, decision.get("framing_shape"))
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ass_path = Path(tmp) / "captions.ass"
            plan = _build_captions(transcript, clip_start, clip_end, cue_config, ass_path)
            ass_text = ass_path.read_text(encoding="utf-8")
        if not plan.get("words"):
            return {"available": False, "reason": "No spoken words were found inside this clip's times."}
        # Per-event font size exactly as written into the export ASS (the
        # layer-2 Dialogue lines, in plan-event order).
        fs_values = []
        for line in ass_text.splitlines():
            if line.startswith("Dialogue: 2,"):
                match = re.search(r"\\fs([0-9.]+)", line)
                fs_values.append(float(match.group(1)) if match else float(plan.get("font_size", 110)))
        events = []
        for index, event in enumerate(plan.get("events", [])):
            events.append({"start": event["start"], "end": event["end"], "active_word": event["active_word"], "group": event["group"], "fs": fs_values[index] if index < len(fs_values) else float(plan.get("font_size", 110))})
        from ..captions import caption_text as _caption_text
        plan_style = plan.get("style", "hormozi_glow")
        words = {word["i"]: {"text": word["text"], "start": word["start"], "end": word["end"], "display": word["text"] if plan_style == "gravitas" else _caption_text(word["text"])} for word in plan.get("words", [])}
        groups = [{"start": group["start"], "end": group["end"], "word_ids": group["word_ids"], "line_breaks": group.get("line_breaks", [])} for group in plan.get("groups", [])]
        feed = cue_config.regions["feed"]
        return {"available": True, "style": plan.get("style", "hormozi_glow"), "font_size": plan.get("font_size", 110), "dy": plan.get("dy", 0), "slot": plan.get("slot", {}), "feed": {"x": feed["x"], "y": feed["y"], "w": feed["w"], "h": feed["h"]}, "canvas": {"w": cue_config.canvas["w"], "h": cue_config.canvas["h"]}, "base_color": cue_config.get("captions", "base", default="#FFFFFF"), "emphasis_color": cue_config.get("captions", "emphasis", default="#FF3B30"), "words": words, "groups": groups, "events": events}

    @app.post("/api/decisions")
    async def decisions(request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="object required")
        job_id, candidate_id = str(payload.get("job_id", "")), str(payload.get("candidate_id", ""))
        try:
            validate_id(job_id)
            validate_id(candidate_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid resource id") from exc
        record = next((row for row in _candidate_records() if row["job_id"] == job_id and row["id"] == candidate_id), None)
        if not record:
            raise HTTPException(status_code=404, detail="candidate not found")
        action = str(payload.get("action", ""))
        if action not in {"approve", "reject", "save", "claim_check"}:
            raise HTTPException(status_code=400, detail="invalid decision")
        if lan and config.get("security", "lan", "read_only_default", default=True) and action not in {"approve", "reject"}:
            raise HTTPException(status_code=403, detail="LAN review is limited to approve/reject")
        # Only a payload that actually carries a headline may set one.
        # Defaulting an omitted headline to "" and storing it made any
        # partial save (e.g. accept-review only) wipe the saved headline
        # in the merged decision (Phase 4B FIX3 follow-up, 2026-10-11).
        headline = str(payload["headline"])[:78] if payload.get("headline") is not None else None
        edits = payload.get("edits", {})
        if lan and config.get("security", "lan", "read_only_default", default=True):
            headline, edits = None, {}
        if not isinstance(edits, dict):
            raise HTTPException(status_code=400, detail="edits must be an object")
        clean_edits = {}
        for key in ("start", "end"):
            if key in edits:
                try:
                    value = float(edits[key])
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=400, detail="invalid edit time") from exc
                if not math.isfinite(value) or value < 0:
                    raise HTTPException(status_code=400, detail="invalid edit time")
                clean_edits[key] = value
        if "start" in clean_edits or "end" in clean_edits:
            start = clean_edits.get("start", float(record.get("start", 0)))
            end = clean_edits.get("end", float(record.get("end", 0)))
            source_duration = float(record.get("source", {}).get("duration") or end)
            if start >= end or end > source_duration:
                raise HTTPException(status_code=400, detail="start must be before end and inside the source video")
        if clean_edits:
            # Enforce at save time the same word-boundary rule the render
            # applies (dc/cli.py command_render), so a decision can never
            # be saved in a state that export will refuse. Without this, a
            # mid-word trim was saved silently and only failed at export
            # (Phase 4B FIX3 follow-up, 2026-10-11). The rule is identical,
            # applied earlier — not weakened.
            transcript = read_json(ROOT / "work" / job_id / "transcript.json", {}) or {}
            raw_words = transcript.get("words") or [w for seg in transcript.get("segments", []) for w in seg.get("words", [])]
            eff_start = clean_edits.get("start", float(record.get("start", 0)))
            eff_end = clean_edits.get("end", float(record.get("end", 0)))
            for w in raw_words:
                ws, we = float(w.get("start", 0)), float(w.get("end", 0))
                if ws + .04 < eff_start < we - .04 or ws + .04 < eff_end < we - .04:
                    raise HTTPException(status_code=400, detail="Review boundary cuts through a word; choose a word boundary")
        claim_checks = payload.get("claim_checks", {})
        if not isinstance(claim_checks, dict):
            raise HTTPException(status_code=400, detail="claim_checks must be an object")
        clean_claim_checks = {}
        for word_i, claim in claim_checks.items():
            if not isinstance(claim, dict) or not claim.get("claim_checked"):
                raise HTTPException(status_code=400, detail="claim check must be acknowledged")
            try:
                key = str(int(word_i))
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="invalid claim word index") from exc
            if key not in {str(item.get("word_i")) for item in record.get("claims", [])}:
                raise HTTPException(status_code=400, detail="claim word is not part of this candidate")
            clean_claim_checks[key] = {"claim_checked": True, "source_url": str(claim.get("source_url", ""))[:2048]}
        decision = {"schema_version": 5, "time": datetime.now(timezone.utc).isoformat(), "job_id": job_id, "candidate_id": candidate_id, "action": action, "edits": clean_edits, "claim_checks": clean_claim_checks}
        if headline is not None:
            decision["headline"] = headline
        if payload.get("accept_review") is True and not lan:
            decision["accept_review"]=True
        if not lan or not config.get("security","lan","read_only_default",default=True):
            layout=payload.get("layout")
            if layout is not None:
                if layout not in {"auto","dual","manual"}:
                    raise HTTPException(400,"invalid layout")
                decision["layout"]=layout
            palette=payload.get("palette")
            if palette is not None:
                if not re.fullmatch(r"#[A-Fa-f0-9]{6}",str(palette)):
                    raise HTTPException(400,"invalid palette")
                decision["palette"]=palette
            mode=payload.get("caption_mode")
            if mode is not None:
                if mode not in {"hormozi_glow","gravitas","karaoke_lite"}:
                    raise HTTPException(400,"invalid caption mode")
                decision["caption_mode"]=mode
            crop=payload.get("crop")
            if crop:
                from ..layout import validate_framing_rect
                try:
                    crop={key:float(crop[key]) for key in ("x","y","w","h")}
                    if not all(math.isfinite(value) for value in crop.values()) or not validate_framing_rect(crop,record["source"]["width"],record["source"]["height"]):
                        raise ValueError()
                except (KeyError,TypeError,ValueError):
                    raise HTTPException(400,"invalid crop")
                decision["crop"]=crop
            if "speaker_labels" in payload:
                labels=payload["speaker_labels"]
                if not isinstance(labels,dict) or any(key=="unknown" or len(str(value))>80 for key,value in labels.items()):
                    raise HTTPException(400,"invalid speaker labels")
                decision["speaker_labels"]={str(key):str(value) for key,value in labels.items()}
                transcript_path=ROOT/"work"/job_id/"transcript.json"
                transcript=read_json(transcript_path,{}) or {}
                transcript["verified_speakers"]=sorted(set(transcript.get("verified_speakers",[]))|set(labels))
                transcript["manual_speaker_labels"]=decision["speaker_labels"]
                atomic_write_json(transcript_path,transcript)
            framing_controls = payload.get("framing_controls")
            if framing_controls is not None:
                if not isinstance(framing_controls, dict):
                    raise HTTPException(400, "framing controls must be an object")
                try:
                    clean_framing = {
                        "layout": str(framing_controls.get("layout", "auto")),
                        "zoom": float(framing_controls.get("zoom", 1.0)),
                        "move_x": float(framing_controls.get("move_x", 0.0)),
                        "move_y": float(framing_controls.get("move_y", 0.0)),
                    }
                except (TypeError, ValueError) as exc:
                    raise HTTPException(400, "invalid framing controls") from exc
                if clean_framing["layout"] not in {"auto", "two", "wide"} or not all(math.isfinite(value) for key, value in clean_framing.items() if key != "layout") or not 1.0 <= clean_framing["zoom"] <= 1.5 or not -1.0 <= clean_framing["move_x"] <= 1.0 or not -1.0 <= clean_framing["move_y"] <= 1.0:
                    raise HTTPException(400, "framing controls are outside the safe range")
                decision["framing_controls"] = clean_framing
            framing_pins = payload.get("framing_pins")
            if framing_pins is not None:
                if not isinstance(framing_pins, list):
                    raise HTTPException(400, "framing pins must be a list")
                from ..framing_pins import normalize_pins as _normalize_pins
                clip_duration = max(0.0, float(record.get("end", 0)) - float(record.get("start", 0)))
                decision["framing_pins"] = _normalize_pins(framing_pins, clip_duration)
            framing_shape = payload.get("framing_shape")
            if framing_shape is not None:
                if framing_shape not in {"", "9:16", "1:1", "16:9"}:
                    raise HTTPException(400, "invalid framing shape")
                decision["framing_shape"] = framing_shape
            caption_controls = payload.get("caption_controls")
            if caption_controls is not None:
                if not isinstance(caption_controls, dict):
                    raise HTTPException(400, "caption controls must be an object")
                try:
                    clean_caption = {
                        "size_delta": float(caption_controls.get("size_delta", 0)),
                        "vertical_delta": float(caption_controls.get("vertical_delta", 0)),
                        "highlight_color": str(caption_controls.get("highlight_color", "#B4F83D")),
                        "style": str(caption_controls.get("style", "hormozi_glow")),
                    }
                except (TypeError, ValueError) as exc:
                    raise HTTPException(400, "invalid caption controls") from exc
                if "enabled" in caption_controls:
                    if not isinstance(caption_controls["enabled"], bool):
                        raise HTTPException(400, "caption enabled must be true or false")
                    clean_caption["enabled"] = caption_controls["enabled"]
                if not all(math.isfinite(value) for key, value in clean_caption.items() if key.endswith("delta")) or not -30 <= clean_caption["size_delta"] <= 30 or not -320 <= clean_caption["vertical_delta"] <= 320 or not re.fullmatch(r"#[A-Fa-f0-9]{6}", clean_caption["highlight_color"]) or clean_caption["style"] not in {"hormozi_glow", "gravitas", "karaoke_lite"}:
                    raise HTTPException(400, "caption controls are outside the safe range")
                decision["caption_controls"] = clean_caption
        record_decision(ROOT, decision)
        JobStore(ROOT / "work" / "jobs.sqlite").label(job_id, candidate_id, action, json.dumps({**decision, "components": record.get("components", {}), "text":record.get("text",""), "proposed_start": record.get("start"), "proposed_end": record.get("end")}, ensure_ascii=False))
        merged = latest_decision(ROOT, job_id, candidate_id)
        return {"status": "recorded", "job_id": job_id, "candidate_id": candidate_id, **merged, "edit_revision": edit_revision(record, merged)}

    @app.post("/api/fix-everywhere")
    async def fix_everywhere(request: Request):
        if lan and config.get("security","lan","read_only_default",default=True):
            raise HTTPException(403,"host editing required")
        payload=await request.json()
        try:
            job_id=validate_id(payload["job_id"])
            old,new=str(payload["from"]).strip(),str(payload["to"]).strip()
        except (KeyError,ValueError,TypeError):
            raise HTTPException(400,"invalid correction")
        if not old or not new or len(new)>100:
            raise HTTPException(400,"invalid correction")
        transcript_path=ROOT/"work"/job_id/"transcript.json"
        transcript=read_json(transcript_path,{}) or {}
        if not transcript:
            raise HTTPException(404,"transcript absent")
        count=0
        for segment in transcript.get("segments",[]):
            for word in segment.get("words",[]):
                key="text" if "text" in word else "word"
                if str(word.get(key,"")).strip()==old:
                    word[key]=new
                    if "word" in word: word["word"]=new
                    if "text" in word: word["text"]=new
                    count+=1
            segment["text"]=" ".join(str(word.get("text",word.get("word",""))).strip() for word in segment.get("words",[]))
        transcript.setdefault("manual_corrections",[]).append({"from":old,"to":new,"occurrences":count})
        atomic_write_json(transcript_path,transcript)
        from ..core.io import atomic_copy
        previous=ROOT/"work"/job_id/"candidates.json"
        if previous.exists():
            atomic_copy(previous,ROOT/"work"/job_id/("candidates_before_correction_"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")+".json"))
        source=read_json(ROOT/"work"/job_id/"source.json")
        from ..selection import select_candidates
        graph,candidates=select_candidates(transcript,source,config)
        atomic_write_json(ROOT/"work"/job_id/"debate_graph.json",graph)
        atomic_write_json(ROOT/"work"/job_id/"candidates.json",{"schema_version":5,"candidates":candidates,"config_hash":config.hash()})
        return {"occurrences":count,"status":"corrected_and_reselected"}

    @app.post("/api/labels")
    async def label(request: Request):
        payload=await request.json()
        try:
            job_id=validate_id(payload["job_id"])
            start,end=float(payload["start"]),float(payload["end"])
            if not math.isfinite(start+end) or start<0 or end<=start:
                raise ValueError()
        except (KeyError,TypeError,ValueError):
            raise HTTPException(400,"invalid annotation")
        rating=payload.get("rating","would_post")
        if rating not in {"would_post","as_is","trivial_trim","not_usable"}:
            raise HTTPException(400,"invalid rating")
        record={"schema_version":5,"start":start,"end":end,"rating":rating,"rater":str(payload.get("rater","local"))[:80]}
        JobStore(ROOT/"work"/"jobs.sqlite").label(job_id,str(payload.get("candidate_id","blind")),"golden_label",json.dumps(record))
        return {"status":"recorded"}

    @app.post("/api/render")
    async def render_candidate(request: Request):
        if lan and config.get("security", "lan", "read_only_default", default=True):
            raise HTTPException(status_code=403, detail="LAN review cannot render")
        try:
            payload = await request.json()
            validate_id(str(payload.get("job_id", "")))
            validate_id(str(payload.get("candidate_id", "")))
            export_id = validate_id(str(payload.get("export_id") or "export_" + secrets.token_hex(16)))
            variants = int(payload.get("variants", 1))
            if not 1 <= variants <= 3:
                raise ValueError("invalid variants")
        except (ValueError, AttributeError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="invalid render request") from exc
        from ..cli import command_render
        from argparse import Namespace
        from starlette.concurrency import run_in_threadpool

        record = next((row for row in _candidate_records() if row["job_id"] == payload["job_id"] and row["id"] == payload["candidate_id"]), None)
        if not record:
            raise HTTPException(404, "candidate not found")
        def existing_response():
            active = next((row for row in review_exports.rows() if row["status"] == "exporting"), None)
            if active and active["job_id"] == record["job_id"] and active["candidate_id"] == record["id"]:
                return {"status": "already_running", "attempt": active}
            return JSONResponse({"detail": "Another export is already running", "attempt": active}, status_code=409)
        if not render_lock.acquire(blocking=False):
            return existing_response()
        from ..core.locking import exclusive_file
        try:
            with exclusive_file(ROOT / "work" / "studio_render.lock"):
                previous = review_exports.get(export_id)
                if previous:
                    if previous["job_id"] != record["job_id"] or previous["candidate_id"] != record["id"]:
                        raise HTTPException(400, "Export request belongs to another clip")
                    return {"status": previous["status"], "attempt": previous, "export": previous.get("export")}
                for orphan in review_exports.rows():
                    if orphan["status"] == "exporting":
                        review_exports.finish(orphan, "not_finished", "The export was interrupted. Try again.")
                attempt = review_exports.create(export_id, record)
                try:
                    result = await run_in_threadpool(command_render, Namespace(job=record["job_id"], candidate=record["id"], headline=None, layout="auto", variants=variants, export_id=export_id, decision_snapshot=attempt["decision"]))
                    export = next((row for row in catalog(ROOT / "exports") if row.get("export_id") == export_id and row.get("stable_id") == record["id"]), None)
                    if result == 0 and export:
                        attempt = review_exports.finish(attempt, "exported", export=export)
                    elif result == 130:
                        attempt = review_exports.finish(attempt, "not_finished", "The export was stopped. Try again.")
                    else:
                        attempt = review_exports.finish(attempt, "failed", "The export did not produce a verified file. Check the export details and try again.")
                except ResourceBusy:
                    attempt = review_exports.finish(attempt, "failed", "Video processing is already running. Wait for it to finish, then try again.")
                except (Exception, SystemExit) as exc:
                    reason = str(exc) if isinstance(exc, SystemExit) else "The video could not be exported. Check the export details and try again."
                    attempt = review_exports.finish(attempt, "failed", reason)
                return {"status": attempt["status"], "attempt": attempt, "export": attempt.get("export")}
        except ResourceBusy:
            return existing_response()
        finally:
            render_lock.release()

    @app.post("/api/retry/{job_id}")
    async def retry(job_id:str):
        if lan and config.get("security","lan","read_only_default",default=True):
            raise HTTPException(403,"host retry required")
        try:
            validate_id(job_id)
        except ValueError:
            raise HTTPException(400,"invalid job id")
        job_dir = ROOT / "work" / job_id
        store = JobStore(ROOT / "work" / "jobs.sqlite")
        current = store.get(job_id)
        if not job_dir.is_dir() or not current:
            raise HTTPException(404, "Job not found")
        if current["state"] in {"queued", "running", "rendering"}:
            raise HTTPException(409, "This video is already being processed")
        try:
            previous_payload = json.loads(current.get("payload", "{}")) or {}
        except (TypeError, ValueError):
            previous_payload = {}
        saved_request = read_json(job_dir / "job_request.json", {}) or {}
        request = saved_request.get("request", {}) if isinstance(saved_request, dict) else {}
        source_artifact = read_json(job_dir / "source.json", {}) or {}
        source = request.get("source") or previous_payload.get("source") or source_artifact.get("path")
        if not source:
            raise HTTPException(400, "The original video source is no longer available")
        group = read_json(job_dir / "source_group.json", {}) or {}
        source_group_id = group.get("group_id") or previous_payload.get("source_group_id") or source_artifact.get("source_id")
        if not source_group_id:
            source_group_id = f"source_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        new_job_id = f"{job_id}_r{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        validate_id(new_job_id)
        new_dir = ROOT / "work" / new_job_id
        new_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(new_dir / "source_group.json", {"schema_version": 1, "group_id": source_group_id, "source_key": source_group_id, "title": group.get("title") or source_artifact.get("meta", {}).get("title") or Path(str(source)).stem, "run_id": new_job_id, "retry_of": job_id, "created_at": datetime.now(timezone.utc).isoformat()})
        log_path = new_dir / "studio_run.log"
        rights = request.get("rights_class", previous_payload.get("rights_class", source_artifact.get("rights_class", "unknown")))
        rights_note = request.get("rights_note", previous_payload.get("rights_note", source_artifact.get("rights_note", "")))
        top = int(request.get("top", previous_payload.get("top", 8)))
        command = [sys.executable, "-m", "dc", "run", "--source", str(source), "--job", new_job_id, "--rights-class", str(rights), "--rights-note", str(rights_note)[:500], "--mode", "review", "--top", str(top)]
        if request.get("preset"): command.extend(["--preset", str(request["preset"])])
        if request.get("no_network") is True: command.append("--no-network")
        payload_record = {"source": str(source), "source_group_id": source_group_id, "retry_of": job_id, "rights_class": rights, "rights_note": str(rights_note)[:500], "top": top}
        store.upsert(new_job_id, "queued", json.dumps(payload_record), "queued")
        log_handle = log_path.open("ab")
        try:
            process = subprocess.Popen(command, cwd=str(ROOT), stdout=log_handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=os.name != "nt")
        except OSError as exc:
            log_handle.close()
            store.upsert(new_job_id, "failed", json.dumps({"error": str(exc), "retry_of": job_id}), "failed")
            raise HTTPException(500, f"The retry could not start: {exc}") from exc
        log_handle.close()
        payload_record["pid"] = process.pid
        store.upsert(new_job_id, "queued", json.dumps(payload_record), "queued")
        return {"status": "started", "job_id": new_job_id, "pid": process.pid, "retry_of": job_id, "source_group_id": source_group_id, "started_at": store.get(new_job_id).get("started_at")}

    @app.post("/api/cancel/{job_id}")
    async def cancel_job(job_id: str):
        if lan and config.get("security", "lan", "read_only_default", default=True):
            raise HTTPException(status_code=403, detail="LAN review cannot cancel")
        from ..cli import command_cancel
        from argparse import Namespace
        try:
            command_cancel(Namespace(job=job_id))
        except (ValueError, SystemExit) as exc:
            raise HTTPException(status_code=400, detail="invalid job") from exc
        return {"status": "cancelled", "job_id": job_id}

    @app.post("/api/publish")
    async def publish_request(request:Request):
        if lan and config.get("security","lan","read_only_default",default=True):
            raise HTTPException(403,"host publishing required")
        payload=await request.json()
        try:
            clip_id=validate_id(payload["candidate_id"])
            from ..distribute.adapters import publish
            from starlette.concurrency import run_in_threadpool
            export_row=next((row for row in catalog(ROOT/"exports") if row.get("stable_id")==clip_id),None)
            if not export_row:
                raise ValueError("export not found")
            result=await run_in_threadpool(publish,Path(export_row["folder"]),str(payload["platform"]),config,payload.get("confirmed") is True,False)
        except (ValueError,RuntimeError,KeyError) as exc:
            raise HTTPException(400,str(exc))
        return result

    @app.get("/api/file/{file_id:path}")
    async def file_by_id(file_id: str):
        try:
            validate_id(file_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid file id")
        if "/" in file_id or "\\" in file_id or ".." in file_id:
            raise HTTPException(status_code=400, detail="invalid file id")
        path = _candidate_file(file_id)
        if not path:
            raise HTTPException(status_code=404, detail="file not found")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.get("/api/media/{job_id}/{candidate_id}/{kind}")
    async def media(job_id:str,candidate_id:str,kind:str):
        try:
            validate_id(job_id)
            validate_id(candidate_id)
        except ValueError:
            raise HTTPException(400,"invalid id")
        job=ROOT/"work"/job_id
        if job.is_symlink():
            raise HTTPException(400,"invalid job path")
        record=next((row for row in _candidate_records() if row["job_id"]==job_id and row["id"]==candidate_id),None)
        if not record:
            raise HTTPException(404,"candidate absent")
        if kind=="source":
            source=read_json(job/"source.json",{}) or {}
            path=Path(source.get("path",""))
        elif kind=="clip":
            path=job/f"{candidate_id}.mp4"
        elif kind=="cover":
            path=ROOT/"exports"/candidate_id/"cover.jpg"
        elif kind=="proxy":
            path=job/f"{candidate_id}_proxy.mp4"
        else:
            raise HTTPException(400,"invalid media kind")
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404,"media absent")
        return FileResponse(path,media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    from .speaker_frame_api import install_routes
    install_routes(app,lan,render_lock)
    return app, session_token
