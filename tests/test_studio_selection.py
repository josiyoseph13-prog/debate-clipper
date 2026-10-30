"""Regression tests for the wrong-job selection bug (2026-10-12).

Two jobs built from the same source share candidate IDs. The Studio
data layer must keep the two jobs' records and decisions strictly
separate, a decision saved for one job must never touch the other,
and the served studio.js must resolve the selected clip by
job + candidate ID (never by candidate ID alone, never with a
silent first-record fallback).

Report: reports/WRONG_JOB_SELECTION_BUG.md
"""

import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from dc.studio import server
    from dc.studio.server import create_app
except Exception:  # optional web dependencies are checked by doctor
    TestClient = None
    server = None
    create_app = None

STUDIO_JS = Path(__file__).resolve().parent.parent / "dc" / "studio" / "static" / "studio.js"


def _write_job(root: Path, job_id: str, headline: str, start: float, end: float) -> Path:
    job_dir = root / "work" / job_id
    job_dir.mkdir(parents=True)
    words = [
        {"start": float(i), "end": float(i) + 0.4, "word": f" w{i}"}
        for i in range(0, 100)
    ]
    (job_dir / "transcript.json").write_text(json.dumps({"segments": [{"words": words}]}))
    (job_dir / "source.json").write_text(json.dumps({
        "source_id": "src_same", "duration": 100.0,
        "path": "same_source.mp4", "meta": {"title": "Same Source"},
    }))
    (job_dir / "candidates.json").write_text(json.dumps({"candidates": [
        {"id": "c_dup", "start": 10.0, "end": 40.0, "score": 50.0, "title": "Dup clip"},
    ]}))
    (job_dir / "decisions.json").write_text(json.dumps({"schema_version": 5, "decisions": [
        {"job_id": job_id, "candidate_id": "c_dup", "action": "save",
         "headline": headline, "edits": {"start": start, "end": end}},
    ]}))
    return job_dir


@unittest.skipUnless(TestClient and create_app, "FastAPI test dependencies are optional")
class StudioSelectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "work").mkdir(parents=True)
        (self.root / "exports").mkdir(parents=True)
        self.job_a = _write_job(self.root, "job_a", "JOB A HEADLINE", 11.0, 39.4)
        self.job_b = _write_job(self.root, "job_b", "JOB B HEADLINE", 12.0, 37.4)
        self._real_root = server.ROOT
        server.ROOT = self.root

    def tearDown(self):
        server.ROOT = self._real_root
        self._tmp.cleanup()

    def _records_for_dup(self):
        return [r for r in server._candidate_records() if r.get("id") == "c_dup"]

    def test_colliding_ids_stay_separate_per_job(self):
        records = self._records_for_dup()
        self.assertEqual(len(records), 2)
        by_job = {r["job_id"]: r for r in records}
        self.assertEqual(set(by_job), {"job_a", "job_b"})
        self.assertEqual(by_job["job_a"]["decision"].get("headline"), "JOB A HEADLINE")
        self.assertEqual(by_job["job_b"]["decision"].get("headline"), "JOB B HEADLINE")
        self.assertEqual(by_job["job_a"]["decision"].get("edits"), {"start": 11.0, "end": 39.4})
        self.assertEqual(by_job["job_b"]["decision"].get("edits"), {"start": 12.0, "end": 37.4})

    def test_save_routes_to_intended_job_only(self):
        before_a = (self.job_a / "decisions.json").read_bytes()
        app, token = create_app(lan=False)
        client = TestClient(app, base_url="http://127.0.0.1")
        payload = {
            "job_id": "job_b", "candidate_id": "c_dup", "action": "save",
            "headline": "JOB B EDITED", "edits": {"start": 13.0, "end": 36.4},
        }
        response = client.post("/api/decisions", json=payload, headers={"Origin": "http://127.0.0.1", "X-DC-Token": token})
        self.assertEqual(response.status_code, 200, response.text)
        # The other job's decisions file is byte-identical.
        self.assertEqual((self.job_a / "decisions.json").read_bytes(), before_a)
        # Reloaded records: only job_b reflects the edit.
        by_job = {r["job_id"]: r for r in self._records_for_dup()}
        self.assertEqual(by_job["job_b"]["decision"].get("headline"), "JOB B EDITED")
        self.assertEqual(by_job["job_b"]["decision"].get("edits"), {"start": 13.0, "end": 36.4})
        self.assertEqual(by_job["job_a"]["decision"].get("headline"), "JOB A HEADLINE")
        self.assertEqual(by_job["job_a"]["decision"].get("edits"), {"start": 11.0, "end": 39.4})


class StudioSelectionClientContractTests(unittest.TestCase):
    """Pin the client-side contract the data layer relies on: the
    served studio.js must carry the job through selection and must
    not resolve a selected clip by candidate ID alone."""

    @classmethod
    def setUpClass(cls):
        cls.js = STUDIO_JS.read_text(encoding="utf-8")

    def test_row_click_preserves_job(self):
        self.assertIn("state.selectedJobId = item.job_id", self.js)

    def test_resolution_matches_job_and_id(self):
        self.assertIn("recordForSelection", self.js)
        self.assertIn("record.job_id === jobId", self.js)

    def test_no_silent_first_record_fallback(self):
        self.assertNotIn("|| records[0]", self.js)
        self.assertNotIn("records.find(record => record.id === id)", self.js)

    def test_missing_or_ambiguous_selection_shows_error(self):
        self.assertIn("selectionError", self.js)
        self.assertIn("Nothing was opened", self.js)


if __name__ == "__main__":
    unittest.main()
