"""Phase 4C tests: framing pins (master plan Sections 12.2-12.3).

Covers pin normalization, pin -> framing segment math, face presets
from tracking, decision persistence (including per-job isolation and
the empty-list clear), the edited-since-export snapshot, and the
Studio client contract (rejected controls gone, pin editor present).
"""

import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from dc.studio import server
    from dc.studio.server import create_app
except Exception:
    TestClient = None
    server = None
    create_app = None

from dc.core.config import load_config
from dc.core.decisions import latest_decision
from dc.framing_pins import normalize_pins, pin_crop_rect, pins_to_framing, presets_from_tracking, default_pin, shape_feed_config
from dc.layout import crop_rect
from dc.studio.review_exports import edit_revision

STUDIO_JS = Path(__file__).resolve().parent.parent / "dc" / "studio" / "static" / "studio.js"
CLI_PY = Path(__file__).resolve().parent.parent / "dc" / "cli.py"


class NormalizePinsTests(unittest.TestCase):
    def test_empty_stays_empty(self):
        self.assertEqual(normalize_pins([], 60), [])
        self.assertEqual(normalize_pins(None, 60), [])

    def test_clamps_and_guarantees_zero_pin(self):
        pins = normalize_pins([{"t": 20, "zoom": 9, "move_x": 3, "move_y": -3, "preset": "a"}], 60)
        self.assertEqual(pins[0], default_pin(0.0))
        self.assertEqual(pins[1]["t"], 20.0)
        self.assertEqual(pins[1]["zoom"], 2.5)
        self.assertEqual(pins[1]["move_x"], 1.0)
        self.assertEqual(pins[1]["move_y"], -1.0)

    def test_time_clamped_to_duration_and_deduped(self):
        pins = normalize_pins([
            {"t": 0, "zoom": 1.0, "move_x": 0, "move_y": 0, "preset": "auto"},
            {"t": 90, "zoom": 1.5, "move_x": 0, "move_y": 0, "preset": "wide"},
            {"t": 90, "zoom": 2.0, "move_x": 0, "move_y": 0, "preset": "custom"},
        ], 60)
        times = [pin["t"] for pin in pins]
        self.assertEqual(times, [0.0, 60.0])
        self.assertEqual(pins[1]["zoom"], 2.0)

    def test_bad_rows_skipped(self):
        pins = normalize_pins([{"t": "x"}, "junk", {"t": 5, "zoom": 1.2, "move_x": 0, "move_y": 0}], 60)
        self.assertEqual([pin["t"] for pin in pins], [0.0, 5.0])


class FramingMathTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_default_pin_rect_matches_crop_rect(self):
        rect = pin_crop_rect(default_pin(), 1920, 1080, self.config)
        expected = crop_rect(1920, 1080, self.config)
        for key in ("x", "y", "w", "h"):
            self.assertAlmostEqual(rect[key], float(expected[key]), places=6)

    def test_move_shifts_centre_like_static_controls(self):
        base = pin_crop_rect(default_pin(), 1920, 1080, self.config)
        moved = pin_crop_rect({**default_pin(), "move_x": 1.0}, 1920, 1080, self.config)
        self.assertGreater(moved["x"], base["x"])
        self.assertLessEqual(moved["x"] + moved["w"], 1920.0)

    def test_segments_cover_duration_and_switch_at_pins(self):
        pins = normalize_pins([
            {"t": 0, "zoom": 1.0, "move_x": 0, "move_y": 0, "preset": "auto"},
            {"t": 10, "zoom": 2.0, "move_x": 0.2, "move_y": 0, "preset": "a"},
            {"t": 35, "zoom": 1.0, "move_x": 0, "move_y": 0, "preset": "wide"},
        ], 60)
        framing = pins_to_framing(pins, 1920, 1080, 60.0, self.config)
        segments = framing["segments"]
        self.assertEqual([(s["t0"], s["t1"]) for s in segments], [(0.0, 10.0), (10.0, 35.0), (35.0, 60.0)])
        self.assertTrue(all(s["mode"] == "MANUAL" for s in segments))
        self.assertLess(segments[1]["regions"][0]["w"], segments[0]["regions"][0]["w"])
        path_times = [point["t"] for point in framing["path"]]
        self.assertEqual(path_times, [0.0, 10.0, 10.0, 35.0, 35.0, 60.0])


class ShapeFeedConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_default_shape_unchanged(self):
        self.assertIs(shape_feed_config(self.config, "9:16"), self.config)

    def test_square_feed_geometry(self):
        variant = shape_feed_config(self.config, "1:1")
        feed = variant.regions["feed"]
        self.assertEqual(feed["w"], 1080)
        self.assertEqual(feed["h"], 1080)
        self.assertEqual(feed["y"], self.config.regions["feed"]["y"])
        bottom = variant.regions["bottom_white"]
        self.assertEqual(bottom["y"] + bottom["h"], 1920)
        self.assertEqual(self.config.regions["feed"]["h"], 1216)  # original untouched

    def test_wide_feed_geometry(self):
        variant = shape_feed_config(self.config, "16:9")
        self.assertEqual(variant.regions["feed"]["h"], 608)


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.observations = []
        for i in range(40):
            self.observations.append({"t": i * 0.5, "track": "0", "source_box": [300, 200, 180, 220]})
            self.observations.append({"t": i * 0.5, "track": "1", "source_box": [1300, 210, 170, 210]})

    def test_presets_from_two_tracks(self):
        result = presets_from_tracking(self.observations, 10.0, 1920, 1080, self.config)
        self.assertTrue(result["available"])
        self.assertIsNotNone(result["a"])
        self.assertIsNotNone(result["b"])
        self.assertIsNotNone(result["both"])
        self.assertLess(result["a"]["move_x"], 0)   # person A is left of centre
        self.assertGreater(result["b"]["move_x"], 0)
        self.assertLessEqual(result["both"]["zoom"], result["a"]["zoom"])

    def test_no_tracking_is_honest(self):
        self.assertFalse(presets_from_tracking([], 5.0, 1920, 1080, self.config)["available"])
        self.assertFalse(presets_from_tracking(self.observations, 500.0, 1920, 1080, self.config)["available"])


def _write_job(root: Path, job_id: str) -> Path:
    job_dir = root / "work" / job_id
    job_dir.mkdir(parents=True)
    words = [{"start": float(i), "end": float(i) + 0.4, "word": f" w{i}"} for i in range(0, 100)]
    (job_dir / "transcript.json").write_text(json.dumps({"segments": [{"words": words}]}))
    (job_dir / "source.json").write_text(json.dumps({
        "source_id": "src_same", "duration": 100.0, "width": 1920, "height": 1080,
        "path": "same_source.mp4", "meta": {"title": "Same Source"},
    }))
    (job_dir / "candidates.json").write_text(json.dumps({"candidates": [
        {"id": "c_dup", "start": 10.0, "end": 40.0, "score": 50.0, "title": "Dup clip"},
    ]}))
    (job_dir / "decisions.json").write_text(json.dumps({"schema_version": 5, "decisions": [
        {"job_id": job_id, "candidate_id": "c_dup", "action": "save", "headline": "H", "edits": {"start": 10.0, "end": 40.0}},
    ]}))
    return job_dir


@unittest.skipUnless(TestClient and create_app, "FastAPI test dependencies are optional")
class PinPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "work").mkdir(parents=True)
        (self.root / "exports").mkdir(parents=True)
        self.job_a = _write_job(self.root, "job_a")
        self.job_b = _write_job(self.root, "job_b")
        self._old_root = server.ROOT
        server.ROOT = self.root
        app, token = create_app(lan=False)
        self.client = TestClient(app, base_url="http://127.0.0.1")
        self.headers = {"Origin": "http://127.0.0.1", "X-DC-Token": token}

    def tearDown(self):
        server.ROOT = self._old_root
        self.client.close()
        self._tmp.cleanup()

    def _post(self, job_id, **extra):
        payload = {"job_id": job_id, "candidate_id": "c_dup", "action": "save",
                   "headline": "H", "edits": {"start": 10.0, "end": 40.0}, **extra}
        return self.client.post("/api/decisions", json=payload, headers=self.headers)

    def test_pins_round_trip_and_job_isolation(self):
        pins = [{"t": 0, "zoom": 1.0, "move_x": 0, "move_y": 0, "preset": "auto"},
                {"t": 12, "zoom": 2.0, "move_x": 0.3, "move_y": 0, "preset": "a"}]
        response = self._post("job_b", framing_pins=pins, framing_shape="1:1")
        self.assertEqual(response.status_code, 200, response.text)
        merged = latest_decision(self.root, "job_b", "c_dup")
        self.assertEqual(len(merged.get("framing_pins", [])), 2)
        self.assertEqual(merged["framing_pins"][1]["zoom"], 2.0)
        self.assertEqual(merged.get("framing_shape"), "1:1")
        other = latest_decision(self.root, "job_a", "c_dup")
        self.assertNotIn("framing_pins", other)

    def test_empty_pins_clear(self):
        pins = [{"t": 0, "zoom": 1.0, "move_x": 0, "move_y": 0, "preset": "auto"},
                {"t": 12, "zoom": 2.0, "move_x": 0.3, "move_y": 0, "preset": "a"}]
        self.assertEqual(self._post("job_b", framing_pins=pins).status_code, 200)
        self.assertEqual(self._post("job_b", framing_pins=[]).status_code, 200)
        self.assertNotIn("framing_pins", latest_decision(self.root, "job_b", "c_dup"))

    def test_revision_changes_with_pins(self):
        candidate = {"id": "c_dup", "start": 10.0, "end": 40.0, "hook": {"headline_options": ["H"]}}
        base = {"headline": "H", "edits": {"start": 10.0, "end": 40.0}}
        with_pins = {**base, "framing_pins": [{"t": 0.0, "zoom": 1.0, "move_x": 0.0, "move_y": 0.0, "preset": "auto"},
                                              {"t": 5.0, "zoom": 2.0, "move_x": 0.1, "move_y": 0.0, "preset": "a"}]}
        self.assertNotEqual(edit_revision(candidate, base), edit_revision(candidate, with_pins))

    def test_presets_endpoint_honest_without_tracking(self):
        response = self.client.get("/api/candidates/job_b/c_dup/framing-presets", params={"t": 5}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["available"])


class ClientContractTests(unittest.TestCase):
    def test_rejected_controls_gone(self):
        js = STUDIO_JS.read_text(encoding="utf-8")
        for banned in ("Farther", "Show more room", "Who should be on screen?", "How close should it feel?", "Move the picture"):
            self.assertNotIn(banned, js)

    def test_pin_editor_present(self):
        js = STUDIO_JS.read_text(encoding="utf-8")
        for required in ("Change frame here", "framing_pins", "framing_shape", "Editing pin:", "Could not save this pin"):
            self.assertIn(required, js)

    def test_render_wiring_present(self):
        cli = CLI_PY.read_text(encoding="utf-8")
        self.assertIn("framing_pins", cli)
        self.assertIn("pins_to_framing", cli)


if __name__ == "__main__":
    unittest.main()
