"""Active-speaker detection evidence for directed framing (APEX, 2026-10-15).

Balanced configuration chosen by jo (2026-10-15): LR-ASD scores (Junhua-Liao,
MIT, vendored under assets/models/lr_asd/) for every canonical face track,
turned into per-slice speaker probabilities with a softmax temperature of 0.5
and fed to the existing Director; crop math is the app's own. Measured on
three hand-labelled windows (project EXPERIMENT_LOG.md, Exp 3/6/11): wrong-
person framing falls from ~32-43% (mouth-motion fallback) to ~7-8%, and
windows where the fallback cannot plan at all (indoor hall) get a plan.

Everything here is gated by the preset flag ``asd.enabled`` (default OFF).
When the flag is off, the worker is unavailable, or scoring fails, this
module returns None and the caller proceeds with exactly the pre-ASD
behaviour. Scoring runs in a dedicated interpreter (torch) via
asd_worker.py at the project root; this module itself needs only the app's normal stack.
"""
import json
import math
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "assets" / "models" / "lr_asd" / "pretrain_AVA.model"
WORKER = ROOT / "asd_worker.py"  # project root, NOT dc/: a worker inside dc/ puts dc/queue.py ahead of the stdlib queue module and breaks torch
FPS_ASD = 25
MAX_TRACKS = 10


def enabled(config) -> bool:
    try:
        return bool(config.get("asd", "enabled", default=False))
    except Exception:
        return False


def temperature(config) -> float:
    try:
        return float(config.get("asd", "temperature", default=0.5))
    except Exception:
        return 0.5


def min_track_obs(config) -> int:
    try:
        return int(config.get("asd", "min_track_obs", default=120))
    except Exception:
        return 120


def canonical_map(observations, width, height):
    """Merge raw tracker fragments into canonical people.

    The lab-proven rule (APEX Experiments 2/3/6/11): two fragments merge when
    their MEDIAN centres are within 150 px (source pixels) and their time
    spans overlap by at most 25% of the shorter span — sequential fragments
    of one seated person merge, while two people visible together do not.
    A co-visibility guard (Exp 31-33) vetoes any union whose groups contain
    two substantial fragments seen at the same time far apart, which stops
    single-linkage chaining from gluing neighbouring seats into one person.
    Only fragments with >= 10 observations can merge; every fragment maps to
    the largest member of its group. (width/height are accepted for caller
    compatibility; the 150 px rule is the exact one all measurements used.)
    """
    import statistics

    tracks = {}
    for row in observations:
        tracks.setdefault(str(row["track"]), []).append(row)
    info = {}
    for tid, rows in tracks.items():
        info[tid] = {
            "n": len(rows),
            "cx": statistics.median(r["source_box"][0] + r["source_box"][2] / 2 for r in rows),
            "cy": statistics.median(r["source_box"][1] + r["source_box"][3] / 2 for r in rows),
            "t0": min(r["t"] for r in rows),
            "t1": max(r["t"] for r in rows),
        }
    parent = {t: t for t in info}
    members = {t: [t] for t in info}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def overlap_frac(a, b):
        ov = max(0.0, min(info[a]["t1"], info[b]["t1"]) - max(info[a]["t0"], info[b]["t0"]))
        shorter = max(1e-6, min(info[a]["t1"] - info[a]["t0"], info[b]["t1"] - info[b]["t0"]))
        return ov / shorter

    ids = [t for t in info if info[t]["n"] >= 10]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = math.hypot(info[a]["cx"] - info[b]["cx"], info[a]["cy"] - info[b]["cy"])
            if d < 150 and overlap_frac(a, b) <= 0.25:
                ra, rb = find(a), find(b)
                if ra == rb:
                    continue
                # Co-visibility guard (APEX Exp 31-33): single-linkage
                # chaining can glue a whole panel into one fake person via
                # small centre steps. Veto the union when any cross pair
                # of fragments is seen at the same time (overlap > 25%),
                # sits far apart (> 150 px) and both fragments are
                # substantial (>= 60 obs) - two real people on screen
                # together can never be the same person. Tiny fragments
                # never veto (Exp 32: a 30-obs 2 s fragment must not split
                # a real person). Benchmark: W4 wrong 36.6% -> 6.0%, W5
                # wrong 6.8% -> 2.5%, W1/W2/W3/W6 maps unchanged.
                if any(
                    overlap_frac(x, y) > 0.25
                    and math.hypot(info[x]["cx"] - info[y]["cx"], info[x]["cy"] - info[y]["cy"]) > 150
                    and min(info[x]["n"], info[y]["n"]) >= 60
                    for x in members[ra]
                    for y in members[rb]
                ):
                    continue
                parent[ra] = rb
                members[rb] = members[ra] + members[rb]
                del members[ra]
    groups = {}
    for t in info:
        groups.setdefault(find(t), []).append(t)
    cmap = {}
    for members in groups.values():
        canon = max(members, key=lambda t: info[t]["n"])
        for t in members:
            cmap[t] = canon
    return cmap


def canonical_rows(observations, cmap):
    rows = {}
    for row in observations:
        rows.setdefault(cmap[str(row["track"])], []).append(row)
    for tid in rows:
        rows[tid].sort(key=lambda r: r["t"])
    return rows


def box_at(rows, t):
    """Interpolated source_box at time t, or None beyond +/-0.75 s of data."""
    if t < rows[0]["t"] - 0.75 or t > rows[-1]["t"] + 0.75:
        return None
    prev = None
    nxt = None
    for r in rows:
        if r["t"] <= t:
            prev = r
        if r["t"] >= t and nxt is None:
            nxt = r
    if prev is None:
        return nxt["source_box"]
    if nxt is None or nxt is prev:
        return prev["source_box"]
    if nxt["t"] - prev["t"] < 1e-6:
        return prev["source_box"]
    w = (t - prev["t"]) / (nxt["t"] - prev["t"])
    return [prev["source_box"][i] + w * (nxt["source_box"][i] - prev["source_box"][i]) for i in range(4)]


def _asd_python():
    from .core.tools import find_tool
    found = find_tool("asd_python")
    return found if found and Path(found).is_file() else None


def score_window(source, start, duration, observations, config, work_dir, audio_wav=None):
    """Run the LR-ASD worker for one window. Returns (payload|None, reason).

    Never raises: any unavailability or failure yields (None, reason) and the
    caller falls back to the pre-ASD path.
    """
    try:
        if not enabled(config):
            return None, "asd disabled"
        python = _asd_python()
        if python is None:
            return None, "asd_python tool not configured"
        if not WEIGHTS.is_file():
            return None, "LR-ASD weights missing"
        cmap = canonical_map(observations, source["width"], source["height"])
        rows = canonical_rows(observations, cmap)
        floor = min_track_obs(config)
        eligible = {tid: rs for tid, rs in rows.items() if len(rs) >= floor}
        if not eligible:
            return None, f"no canonical track with >= {floor} observations"
        top = dict(sorted(eligible.items(), key=lambda kv: -len(kv[1]))[:MAX_TRACKS])
        from .core.process import run_process
        from .core.tools import find_tool
        with tempfile.TemporaryDirectory(prefix="asd_", dir=work_dir) as tmp:
            spec = {
                "video": source["path"],
                "start": float(start),
                "duration": float(duration),
                "audio_wav": str(audio_wav) if audio_wav else None,
                "ffmpeg": find_tool("ffmpeg"),
                "tracks": {tid: [[r["t"], *r["source_box"]] for r in rs] for tid, rs in top.items()},
                "out": str(Path(tmp) / "scores.json"),
            }
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            timeout = int(max(900, duration * 12))
            run_process([python, str(WORKER), str(spec_path)], timeout=timeout, output_limit=200000)
            scores = json.loads((Path(tmp) / "scores.json").read_text(encoding="utf-8"))
        if not scores:
            return None, "worker returned no scores"
        payload = {"engine": "lr_asd", "temperature": temperature(config),
                   "scores": scores, "canonical_of": cmap}
        return payload, "ok"
    except Exception as exc:  # fallback discipline: never break analysis
        return None, f"{type(exc).__name__}: {exc}"


def slice_values(scores, t):
    """Mean raw ASD logit per track over the 4-frame slice starting at t."""
    k0 = int(t * FPS_ASD)
    k1 = min(k0 + 4, min(len(v) for v in scores.values()))
    if k1 <= k0:
        return {}
    vals = {}
    for tid, sc in scores.items():
        window = sc[k0:k1]
        vals[tid] = float(sum(window) / len(window)) if window else -9.0
    return vals


def slice_probabilities(scores, t, temp):
    """Softmax (temperature-scaled) probabilities from the slice's raw logits."""
    vals = slice_values(scores, t)
    if not vals:
        return {}
    mx = max(vals.values())
    exps = {tid: math.exp(min(20.0, (v - mx) / temp)) for tid, v in vals.items()}
    tot = sum(exps.values())
    return {tid: e / tot for tid, e in exps.items()}


def _smooth_within_segments(points, segments, tau):
    """smooth_path applied per segment run, never across a switch.

    A single global EMA smears the jump at every speaker switch; the rate
    limiter then needs seconds at <=180 px/s to reach the new speaker
    (APEX Exp 27/35: the W6 crawl, wrong-person 17.1% -> 10.6% with this
    change; W2 7.4% -> 3.7%; W5 2.5% -> 4.3% on one span's start
    transient - net win on the frozen benchmark, Exp 36)."""
    from .framing import smooth_path

    bounds = [s["t0"] for s in segments[1:]]
    out = []
    cur = []
    bi = 0
    for row in points:
        if bi < len(bounds) and row["t"] >= bounds[bi]:
            out.extend(smooth_path(cur, tau))
            cur = []
            bi += 1
        cur.append(row)
    out.extend(smooth_path(cur, tau))
    return out

def build_plan(asd_payload, observations, source, duration, config):
    """Director plan from ASD probabilities; None if no SINGLE is ever chosen
    (the caller then uses the existing fallback plan)."""
    from .framing import rate_limit_path, smooth_path
    from .layout import crop_rect
    from .vision import Director

    scores = {tid: [float(x) for x in sc] for tid, sc in asd_payload["scores"].items()}
    if not scores:
        return None
    cmap = asd_payload.get("canonical_of") or canonical_map(observations, source["width"], source["height"])
    rows = canonical_rows(observations, cmap)
    temp = float(asd_payload.get("temperature", 0.5))
    director = Director(config)
    feed = config.regions["feed"]
    width, height = source["width"], source["height"]
    segments, path = [], []
    n_slices = int(duration * 6) + 1
    for i in range(n_slices):
        t = min(duration, i / 6)
        probs = slice_probabilities(scores, t, temp)
        if not probs:
            probs = {tid: 1.0 / len(scores) for tid in scores}
        # Lab recipe (Experiments 3-11): crosstalk when both leading raw
        # logits are positive in the same slice.
        raw_ranked = sorted(slice_values(scores, t).values(), reverse=True)
        crosstalk = 1.0 if len(raw_ranked) > 1 and raw_ranked[0] > 0 and raw_ranked[1] > 0 else 0.0
        state = director.update(t, probs, crosstalk=crosstalk)
        rect = None
        mode = "WIDE"
        track = None
        if state["mode"] == "SINGLE" and state["track"] is not None and state["track"] in rows:
            box = box_at(rows[state["track"]], t)
            if box is not None:
                x, y, w, h = [float(v) for v in box]
                desired_h = min(height, max(feed["h"] / config.get("framing", "s_max", default=1.5),
                                            h / config.get("framing", "phi_target", default=0.2)))
                zoom = height / desired_h if desired_h else 1.0
                rect = crop_rect(width, height, config, x + w / 2,
                                 y + h / 2 + (0.5 - config.get("framing", "head_y_frac", default=0.33)) * desired_h,
                                 zoom)
                mode = "SINGLE"
                track = state["track"]
        if rect is None:
            rect = crop_rect(width, height, config)
        key = (mode, track)
        if not segments or (segments[-1]["mode"], segments[-1].get("track")) != key:
            if segments:
                segments[-1]["t1"] = t
            segments.append({"t0": t, "t1": duration, "mode": mode, "track": track,
                             "regions": [rect], "confidence": 0.9, "reasons": ["asd_lr_asd"]})
        path.append({"t": t, **rect})
    if not any(s["mode"] == "SINGLE" for s in segments):
        return None
    switch_times = [s["t0"] for s in segments]
    return {"schema_version": 5, "segments": segments,
            "path": rate_limit_path(_smooth_within_segments(
                                        path, segments,
                                        config.get("framing", "tau_follow", default=0.35)),
                                    switch_times, width, height),
            "debug": {"engine": "lr_asd", "fallback": None,
                      "asd_temperature": temp, "speaker_evidence": "lr_asd"}}
