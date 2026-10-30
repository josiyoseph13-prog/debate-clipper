"""APEX ASD integration tests (2026-10-15).

Covers the pure parts of dc/asd.py (canonical merge, slice probabilities,
plan building) and the flag discipline: default ON since jo's
2026-10-16 decision, and directed_framing
untouched when no ASD payload is present. The torch worker itself is
exercised by the lab regression harness, not unit tests.
"""
import math

import pytest

from dc import asd
from dc.core.config import load_config, load_preset


def _obs(track, t, box):
    return {"t": t, "track": track, "x": box[0], "y": box[1], "w": box[2], "h": box[3],
            "mouth": None, "speech": False, "source_box": list(box)}


def test_canonical_map_merges_close_fragments():
    observations = []
    for i in range(20):
        observations.append(_obs("0", i * 0.25, [100, 100, 80, 80]))
    for i in range(10):
        observations.append(_obs("1", 5.4 + i * 0.25, [110, 105, 80, 80]))
    for i in range(10):
        observations.append(_obs("2", i * 0.25, [2000, 800, 80, 80]))
    cmap = asd.canonical_map(observations, 2560, 1440)
    assert cmap["1"] == "0"          # fragment merged into the longer track
    assert cmap["2"] == "2"          # distant person stays separate
    rows = asd.canonical_rows(observations, cmap)
    assert len(rows["0"]) == 30 and len(rows["2"]) == 10


def test_slice_probabilities_temperature():
    scores = {"a": [2.0] * 100, "b": [0.0] * 100}
    probs = asd.slice_probabilities(scores, 0.0, 0.5)
    assert probs["a"] == pytest.approx(1 / (1 + math.exp(-4.0)), abs=1e-6)
    assert probs["a"] + probs["b"] == pytest.approx(1.0)


def _two_people_observations(duration=12.0):
    observations = []
    t = 0.0
    while t < duration:
        observations.append(_obs("0", round(t, 2), [300, 200, 120, 120]))
        observations.append(_obs("1", round(t, 2), [1500, 200, 120, 120]))
        t += 0.25
    return observations


def test_build_plan_follows_asd_scores():
    config = load_preset("political_lens")
    source = {"width": 2560, "height": 1440, "path": "unused.mp4"}
    n = int(12.0 * 25)
    scores = {"0": [2.0] * (n // 2) + [-2.0] * (n - n // 2),
              "1": [-2.0] * (n // 2) + [2.0] * (n - n // 2)}
    payload = {"engine": "lr_asd", "temperature": 0.5, "scores": scores,
               "canonical_of": {"0": "0", "1": "1"}}
    plan = asd.build_plan(payload, _two_people_observations(), source, 12.0, config)
    assert plan is not None
    assert plan["schema_version"] == 5
    singles = [s for s in plan["segments"] if s["mode"] == "SINGLE"]
    assert {s["track"] for s in singles} == {"0", "1"}
    assert plan["debug"]["engine"] == "lr_asd"


def test_build_plan_none_when_scores_flat():
    config = load_preset("political_lens")
    source = {"width": 2560, "height": 1440, "path": "unused.mp4"}
    n = int(12.0 * 25)
    payload = {"engine": "lr_asd", "temperature": 0.5,
               "scores": {"0": [-2.0] * n, "1": [-2.0] * n},
               "canonical_of": {"0": "0", "1": "1"}}
    plan = asd.build_plan(payload, _two_people_observations(), source, 12.0, config)
    assert plan is None  # no SINGLE ever chosen -> caller keeps the fallback


def test_asd_enabled_by_default_and_score_window_noop_when_disabled():
    # jo's decision (2026-10-16): the speaker brain is ON by default.
    config = load_preset("political_lens")
    assert asd.enabled(config) is True
    off = load_config(overrides={"asd": {"enabled": False}})
    payload, reason = asd.score_window({"width": 100, "height": 100, "path": "x"},
                                       0, 10, [], off, ".")
    assert payload is None and reason == "asd disabled"


def test_directed_framing_without_asd_payload_is_pre_asd_behaviour():
    from dc.vision import directed_framing
    config = load_preset("political_lens")
    source = {"width": 2560, "height": 1440, "path": "unused.mp4"}
    # No observations / no asd key: must not raise, must not invent a plan
    # from ASD (returns the classic fallback result or None as before).
    result = directed_framing({"observations": [], "tracks": {}, "correlations": {}},
                              source, 10.0, config, {})
    assert result is None or result["debug"].get("fallback") == "local_mouth_motion"


def test_canonical_map_guard_stops_panel_chaining():
    """Exp 31-33: A (cx500) and B (cx780) sit together the whole time; a
    bridge fragment (cx640) from another shot is within 150 px of both.
    Plain single-linkage would chain all three into one fake person; the
    co-visibility guard must keep B separate."""
    observations = []
    for i in range(80):
        observations.append(_obs("0", i * 0.25, [460, 100, 80, 80]))       # A, t 0-19.75
    for i in range(80):
        observations.append(_obs("1", 21.0 + i * 0.25, [600, 100, 80, 80]))  # bridge, t 21-40.75
    for i in range(80):
        observations.append(_obs("2", i * 0.25, [740, 100, 80, 80]))         # B, t 0-19.75
    cmap = asd.canonical_map(observations, 1920, 1080)
    assert cmap["1"] == cmap["0"]   # bridge joins A (never on screen together)
    assert cmap["2"] == "2"         # B stays its own person despite the chain


def test_canonical_map_guard_noise_fragment_cannot_veto():
    """Exp 32 lesson (W2): a small fragment (21 obs) seen at the same time
    as a big one must NOT veto a legitimate merge chain - only pairs of
    substantial fragments (>= 60 obs) can veto."""
    observations = []
    for i in range(80):
        observations.append(_obs("0", i * 0.25, [314, 100, 80, 80]))         # big, cx354, t 0-19.75
    for i in range(21):
        observations.append(_obs("6", 3.0 + i * 0.1, [486, 100, 80, 80]))    # noise, cx526, t 3-5
    for i in range(80):
        observations.append(_obs("9", 58.0 + i * 0.25, [491, 100, 80, 80]))  # big, cx531, t 58-77.75
    for i in range(80):
        observations.append(_obs("5", 21.0 + i * 0.25, [400, 100, 80, 80]))  # big, cx440, t 21-40.75
    cmap = asd.canonical_map(observations, 1920, 1080)
    assert cmap["9"] == cmap["0"]   # the whole chain still merges into one person
    assert cmap["5"] == cmap["0"] and cmap["6"] == cmap["0"]


def test_smooth_within_segments_keeps_switch_instant():
    """Exp 35-37: smoothing must never smear across a segment switch -
    the first path row of a new segment is that segment's raw rect, so
    the rate limiter can pass the switch as an authored cut."""
    pts = [{"t": 0.0, "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0},
           {"t": 0.5, "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0},
           {"t": 1.0, "x": 900.0, "y": 0.0, "w": 100.0, "h": 100.0},
           {"t": 1.5, "x": 900.0, "y": 0.0, "w": 100.0, "h": 100.0}]
    segs = [{"t0": 0.0, "t1": 1.0}, {"t0": 1.0, "t1": 2.0}]
    out = asd._smooth_within_segments(pts, segs, 0.35)
    assert out[0]["x"] == 0.0 and out[1]["x"] == 0.0
    assert out[2]["x"] == 900.0   # no crawl: the switch lands instantly
    assert out[3]["x"] == 900.0
