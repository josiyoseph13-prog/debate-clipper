"""Phase 4D (Captions, master plan Section 12.5) tests.

- /api/decisions caption_controls: the new "enabled" flag must be a
  real boolean; the vertical (position) safe range is +/-320 so the
  Top/Bottom presets (+/-300) fit; the other bounds are unchanged.
- GET /caption-cues: the clip's own word-timed cues built by the
  production caption builder with the saved settings applied, so the
  Edit preview is the export's own data; honest unavailable states.
- Captions off: build_captions(suppress=...) empties the export's
  caption events, and the cli -> config -> renderer wire exists.
- Client contract: the Captions group is the new editor (slider,
  swatches incl. white, toggle, position), not the old buttons.
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
PROJECT = Path(__file__).resolve().parent.parent

WORDS = ["Hello", "world", "this", "is", "a", "test", "of", "the", "caption", "system", "no", "retreat", "in", "2024", "we", "hold"]


def _write_job(root: Path, job_id: str, with_transcript: bool = True) -> Path:
    job_dir = root / "work" / job_id
    job_dir.mkdir(parents=True)
    if with_transcript:
        words = [
            {"start": float(i), "end": float(i) + 0.4, "word": f" {WORDS[i % len(WORDS)]}"}
            for i in range(0, 100)
        ]
        (job_dir / "transcript.json").write_text(json.dumps({"segments": [{"words": words}]}))
    (job_dir / "source.json").write_text(json.dumps({
        "source_id": "src_cap", "duration": 100.0,
        "path": "cap_source.mp4", "meta": {"title": "Caption Source"},
    }))
    (job_dir / "candidates.json").write_text(json.dumps({"candidates": [
        {"id": "c_cap", "start": 10.0, "end": 40.0, "score": 50.0, "title": "Caption clip"},
    ]}))
    (job_dir / "decisions.json").write_text(json.dumps({"schema_version": 5, "decisions": []}))
    return job_dir


class CaptionStudioBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "work").mkdir(parents=True)
        (self.root / "exports").mkdir(parents=True)
        self.job = _write_job(self.root, "job_cap")
        self.job_no_transcript = _write_job(self.root, "job_bare", with_transcript=False)
        self._real_root = server.ROOT
        server.ROOT = self.root
        app, self.token = create_app(lan=False)
        self.client = TestClient(app, base_url="http://127.0.0.1")

    def tearDown(self):
        server.ROOT = self._real_root
        self._tmp.cleanup()

    def headers(self):
        return {"Origin": "http://127.0.0.1", "X-DC-Token": self.token}

    def save_captions(self, controls, job_id="job_cap"):
        payload = {"job_id": job_id, "candidate_id": "c_cap", "action": "save", "caption_controls": controls}
        return self.client.post("/api/decisions", json=payload, headers=self.headers())

    def cues(self, job_id="job_cap", query=""):
        return self.client.get(f"/api/candidates/{job_id}/c_cap/caption-cues{query}", headers=self.headers())


@unittest.skipUnless(TestClient and create_app, "FastAPI test dependencies are optional")
class CaptionControlsValidationTests(CaptionStudioBase):
    def test_enabled_round_trip(self):
        response = self.save_captions({"enabled": False, "size_delta": 5, "vertical_delta": 300, "highlight_color": "#FFFFFF", "style": "gravitas"})
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["caption_controls"]
        self.assertEqual(saved["enabled"], False)
        self.assertEqual(saved["vertical_delta"], 300.0)
        self.assertEqual(saved["highlight_color"], "#FFFFFF")
        self.assertEqual(saved["style"], "gravitas")

    def test_enabled_must_be_boolean(self):
        for bad in ("yes", 1, 0, None):
            response = self.save_captions({"enabled": bad})
            self.assertEqual(response.status_code, 400, f"enabled={bad!r} must be refused")

    def test_vertical_range_widened_but_bounded(self):
        self.assertEqual(self.save_captions({"vertical_delta": -320}).status_code, 200)
        self.assertEqual(self.save_captions({"vertical_delta": 320}).status_code, 200)
        self.assertEqual(self.save_captions({"vertical_delta": 321}).status_code, 400)
        self.assertEqual(self.save_captions({"vertical_delta": -321}).status_code, 400)

    def test_other_bounds_unchanged(self):
        self.assertEqual(self.save_captions({"size_delta": 31}).status_code, 400)
        self.assertEqual(self.save_captions({"style": "neon"}).status_code, 400)
        self.assertEqual(self.save_captions({"highlight_color": "white"}).status_code, 400)


@unittest.skipUnless(TestClient and create_app, "FastAPI test dependencies are optional")
class CaptionCuesEndpointTests(CaptionStudioBase):
    def test_cues_are_the_clips_own_words(self):
        response = self.cues()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["available"], data)
        self.assertEqual(data["style"], "hormozi_glow")
        self.assertTrue(data["words"])
        self.assertTrue(data["groups"])
        self.assertTrue(data["events"])
        first = min(word["start"] for word in data["words"].values())
        self.assertGreaterEqual(first, 0.0)
        self.assertLess(first, 1.0)  # clip-relative: candidate starts at 10s
        for event in data["events"]:
            self.assertGreater(event["fs"], 0)
            self.assertLess(event["start"], event["end"])
        a_word = next(iter(data["words"].values()))
        self.assertEqual(a_word["display"], a_word["display"].upper())  # hormozi display is uppercased

    def test_saved_settings_shape_the_cues(self):
        self.assertEqual(self.save_captions({"enabled": True, "size_delta": 10, "vertical_delta": 300, "highlight_color": "#FFE14D", "style": "gravitas"}).status_code, 200)
        data = self.cues().json()
        self.assertEqual(data["style"], "gravitas")
        self.assertEqual(float(data["dy"]), 300.0)  # dy_override is absolute, as in the render
        self.assertEqual(float(data["font_size"]), 120.0)  # 110 + size_delta

    def test_session_trim_query_params(self):
        full = self.cues().json()
        narrow = self.cues(query="?start=20&end=25").json()
        self.assertTrue(narrow["available"])
        self.assertLess(len(narrow["words"]), len(full["words"]))

    def test_live_params_override_saved_settings(self):
        # The Edit preview passes the session's unsaved look/size; the
        # endpoint must honour them over the saved decision (Phase 4D
        # follow-up found by the caps1 Studio trace).
        data = self.cues(query="?style=gravitas&size_delta=20").json()
        self.assertEqual(data["style"], "gravitas")
        self.assertEqual(float(data["font_size"]), 130.0)
        bad = self.client.get("/api/candidates/job_cap/c_cap/caption-cues?style=neon", headers=self.headers())
        self.assertEqual(bad.status_code, 400)
        bad_size = self.client.get("/api/candidates/job_cap/c_cap/caption-cues?size_delta=99", headers=self.headers())
        self.assertEqual(bad_size.status_code, 400)

    def test_unavailable_is_honest(self):
        data = self.cues(job_id="job_bare").json()
        self.assertFalse(data["available"])
        self.assertTrue(data["reason"])
        missing = self.client.get("/api/candidates/job_cap/c_nope/caption-cues", headers=self.headers())
        self.assertEqual(missing.status_code, 404)


class CaptionsOffRenderTests(unittest.TestCase):
    def test_suppress_empties_export_captions(self):
        from dc.core.config import load_config
        from dc.captions import build_captions
        transcript = {"segments": [{"words": [
            {"start": float(i), "end": float(i) + 0.4, "word": f" word{i}"} for i in range(0, 30)
        ]}]}
        with tempfile.TemporaryDirectory() as tmp:
            ass_path = Path(tmp) / "captions.ass"
            plan = build_captions(transcript, 0.0, 30.0, load_config(), ass_path,
                                  suppress=True, suppress_reason="Captions turned off for this clip by the user")
            self.assertTrue(plan["suppressed"])
            self.assertEqual(plan["suppression_reason"], "Captions turned off for this clip by the user")
            self.assertEqual(plan["events"], [])
            self.assertNotIn("Dialogue: 2", ass_path.read_text(encoding="utf-8"))

    def test_qa_predicted_box_follows_dy(self):
        # Regression: caption_lossless_ab predicted the caption box from
        # the slot alone, so a user-moved caption position (dy) failed
        # the export QA even though the captions were drawn exactly
        # where the settings put them (Phase 4D render B evidence).
        qa = (PROJECT / "dc" / "qa.py").read_text(encoding="utf-8")
        self.assertIn('dy = float(caption_plan.get("dy", 0) or 0)', qa)
        self.assertIn("int(y - h - halo + dy)", qa)
        self.assertIn("int(y + 2 * h + halo + dy)", qa)
        # The box also scales with the plan's font-size ratio (probe on
        # render B: at size 130 a 298 px sliver legitimately passed the
        # default-calibrated right edge).
        self.assertIn('ratio = max(1.0, float(caption_plan.get("font_size", base_fs) or base_fs) / base_fs)', qa)

    def test_user_disabled_wire_exists(self):
        cli = (PROJECT / "dc" / "cli.py").read_text(encoding="utf-8")
        renderer = (PROJECT / "dc" / "renderer.py").read_text(encoding="utf-8")
        self.assertIn('"user_disabled"', cli)
        self.assertIn('config.get("captions","user_disabled"', renderer)


class CaptionClientContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = STUDIO_JS.read_text(encoding="utf-8")

    def test_new_editor_present(self):
        for needle in ("buildCaptionsGroup", "caption-size-slider", "caption-swatch",
                       "caption-cues", "Captions on", "Captions off", "#FFFFFF",
                       "Caption preview is not available for this clip",
                       "Change frame here"):  # Phase 4C regression guard
            self.assertIn(needle, self.js)

    def test_old_caption_buttons_gone(self):
        self.assertNotIn('[-8, "Smaller"]', self.js)
        self.assertNotIn('"Bigger"', self.js)
        self.assertNotIn('"Highlight color"', self.js)  # old US-spelling section is replaced


if __name__ == "__main__":
    unittest.main()
