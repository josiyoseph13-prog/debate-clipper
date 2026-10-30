import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from dc.audio import probe_frame_rate
from dc.captions import build_captions, transcript_words
from dc.core.config import load_config
from dc.core.decisions import latest_decision, record_decision
from dc.core.jobs import JobStore
from dc.core.process import ProcessCancelled, job_processes, run_process
from dc.integrity import publish_gate, verify_claims


class RegressionTests(unittest.TestCase):
    def test_word_indices_are_global_even_with_segment_local_asr_ids(self):
        transcript = {"segments": [
            {"words": [{"i": 0, "text": "one", "start": 1, "end": 2}]},
            {"words": [{"i": 0, "text": "two", "start": 3, "end": 4}]},
        ]}
        self.assertEqual([word["i"] for word in transcript_words(transcript)], [0, 1])

    def test_caption_color_states_do_not_overlap_during_fast_speech(self):
        words = [{"text": text, "start": .1 + i * .12, "end": .22 + i * .12} for i, text in enumerate(("Climate", "change", "affects", "families"))]
        with tempfile.TemporaryDirectory() as folder:
            plan = build_captions({"words": words}, 0, 2, load_config(), Path(folder) / "captions.ass")
        self.assertTrue(plan["events"])
        for left, right in zip(plan["events"], plan["events"][1:]):
            self.assertLessEqual(left["end"], right["start"] + 1e-6)
        self.assertEqual(" ".join(word["text"] for word in plan["words"]), "Climate change affects families")

    def test_frame_rate_preserves_25_and_fractional_and_honors_60_cap(self):
        def probe(rate, cap=30, average=None):
            return probe_frame_rate({"streams": [{"codec_type": "video", "r_frame_rate": rate, "avg_frame_rate": average or rate}]}, cap)
        self.assertEqual(probe("25/1")["target_cfr"], 25)
        self.assertAlmostEqual(probe("24000/1001")["target_cfr"], 24000 / 1001)
        self.assertEqual(probe("60/1")["target_cfr"], 30)
        self.assertEqual(probe("60/1", 60)["target_cfr"], 60)
        self.assertTrue(probe("30/1", average="299/10")["normalise"])

    def test_claim_checks_survive_subsequent_approve_and_preserve_trim(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = {"job_id": "job_test", "candidate_id": "c_test"}
            record_decision(root, {**base, "action": "save", "headline": "The data question", "edits": {"start": 2}})
            record_decision(root, {**base, "action": "claim_check", "claim_checks": {"1": {"claim_checked": True, "source_url": "https://example.org/source"}}})
            record_decision(root, {**base, "action": "approve", "edits": {"end": 5}})
            decision = latest_decision(root, "job_test", "c_test")
            self.assertEqual(decision["action"], "approve")
            self.assertEqual(decision["edits"], {"start": 2, "end": 5})
            checked = verify_claims({"claims": [{"word_i": 1, "text": "90%"}], "integrity_flags": []}, decision["claim_checks"])
            self.assertTrue(checked["claim_checked"])
            self.assertFalse(publish_gate(checked, {"rights_class": "unknown"}, load_config())[0])

    def test_cancel_interrupts_real_child_with_bounded_wait(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            job = root / "job_test"
            job.mkdir()
            store = JobStore(root / "jobs.sqlite")
            store.upsert("job_test", "rendering", "{}")
            timer = threading.Timer(.25, lambda: (job / "cancel.request").write_text("cancel", encoding="utf-8"))
            timer.start()
            start = time.monotonic()
            try:
                with job_processes(job, store, "job_test"):
                    with self.assertRaises(ProcessCancelled):
                        run_process([sys.executable, "-c", "import time; time.sleep(30)"], cwd=job, timeout=10)
            finally:
                timer.cancel()
            self.assertLess(time.monotonic() - start, 5)


@unittest.skipUnless(importlib.util.find_spec("fastapi") and (importlib.util.find_spec("httpx") or importlib.util.find_spec("httpx2")), "Studio dependencies unavailable")
class StudioRegressionTests(unittest.TestCase):
    def test_local_token_host_and_port_are_enforced(self):
        from fastapi.testclient import TestClient
        from dc.studio.server import create_app
        app, token = create_app()
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        payload = {"job_id": "job_missing", "candidate_id": "c_missing", "action": "save"}
        self.assertEqual(client.post("/api/decisions", json=payload).status_code, 403)
        self.assertEqual(client.get("/api/health", headers={"Host": "attacker.invalid"}).status_code, 403)
        self.assertEqual(client.post("/api/decisions", json=payload, headers={"X-DC-Token": token, "Origin": "http://127.0.0.1:9999"}).status_code, 403)
        self.assertEqual(client.post("/api/decisions", json=payload, headers={"X-DC-Token": token, "Origin": "http://127.0.0.1:8765"}).status_code, 404)
