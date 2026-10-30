from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


STATES = {"queued", "running", "awaiting_review", "rendering", "passed", "needs_review", "failed", "cancelled"}
TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"running", "awaiting_review", "failed", "cancelled"},
    "awaiting_review": {"rendering", "cancelled", "failed"},
    "rendering": {"passed", "needs_review", "failed", "cancelled"},
    "passed": {"rendering", "cancelled"},
    "needs_review": {"rendering", "passed", "cancelled"},
    "failed": {"queued", "running", "cancelled"},
    "cancelled": {"queued", "running"},
}


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self,*arguments):
        try:
            return super().__exit__(*arguments)
        finally:
            self.close()


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL, stage TEXT, payload TEXT NOT NULL, heartbeat TEXT NOT NULL, stage_started_at TEXT, started_at TEXT)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            if "stage_started_at" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN stage_started_at TEXT")
            if "started_at" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN started_at TEXT")
            db.execute("CREATE TABLE IF NOT EXISTS labels (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, candidate_id TEXT, action TEXT, payload TEXT, created_at TEXT)")

    def connect(self):
        db = sqlite3.connect(self.path,factory=_ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def upsert(self, job_id: str, state: str, payload: str, stage: str = "") -> None:
        if state not in STATES:
            raise ValueError(f"Unknown job state: {state}")
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            previous = db.execute("SELECT stage,stage_started_at,started_at FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            stage_started_at = now if not previous or previous[0] != stage else previous[1] or now
            started_at = previous[2] if previous and previous[2] else now
            db.execute("INSERT INTO jobs(job_id,state,stage,payload,heartbeat,stage_started_at,started_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET state=excluded.state,stage=excluded.stage,payload=excluded.payload,heartbeat=excluded.heartbeat,stage_started_at=excluded.stage_started_at,started_at=excluded.started_at", (job_id, state, stage, payload, now, stage_started_at, started_at))

    def get(self, job_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def transition(self, job_id: str, state: str, payload: str = "{}", stage: str = "") -> None:
        current = self.get(job_id)
        if current and state not in TRANSITIONS.get(current["state"], set()):
            raise ValueError(f"Invalid job transition: {current['state']} -> {state}")
        self.upsert(job_id, state, payload, stage)

    def heartbeat(self, job_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE jobs SET heartbeat=? WHERE job_id=?",(datetime.now(timezone.utc).isoformat(),job_id))

    def label(self, job_id: str, candidate_id: str, action: str, payload: str) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO labels(job_id,candidate_id,action,payload,created_at) VALUES(?,?,?,?,?)", (job_id, candidate_id, action, payload, datetime.now(timezone.utc).isoformat()))
