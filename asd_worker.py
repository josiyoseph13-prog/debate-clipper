# ASD worker (production) - v3 speed build, adopted 2026-10-16 (Exp 30).
# Proven EXACT vs the original worker on W2 (6,200/6,200 values, Exp 24)
# and it completes long splice windows the original never finished (Exp 25).
# Built from v2 (weighted durations + chunk batching, Exp 21 exact) plus:
#  - ONE decode pass builds every track's crops (production/v2 re-pad the
#    full 1920x1080 frame for every frame of every track: ~75 s/track).
#  - Crops are cut from the raw frame with border fill 110 applied only to
#    the small crop window. Window indices use the production expressions
#    (int(cy+bsi-bs)-bsi etc.) so the pixels are identical by construction.
# Verification gate: Exp 24 must reproduce the W2 production payload
# EXACTLY (6,200 values) before any other use.
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "assets" / "models" / "lr_asd"
sys.path.insert(0, str(PKG))

import torch  # noqa: E402

torch.nn.Module.cuda = lambda self, *a, **k: self
_orig_load = torch.load
torch.load = lambda p, *a, **k: _orig_load(p, map_location="cpu", weights_only=False)

import cv2  # noqa: E402
import python_speech_features  # noqa: E402
from scipy.io import wavfile  # noqa: E402
from scipy.signal import medfilt  # noqa: E402

FPS_ASD = 25
DUR_W = ((1, 3), (2, 3), (3, 2), (4, 1), (5, 1), (6, 1))
CS = 0.40


def box_at(rows, t):
    if t < rows[0][0] - 0.75 or t > rows[-1][0] + 0.75:
        return None
    prev = None
    nxt = None
    for r in rows:
        if r[0] <= t:
            prev = r
        if r[0] >= t and nxt is None:
            nxt = r
    if prev is None:
        return nxt[1:]
    if nxt is None or nxt is prev:
        return prev[1:]
    if nxt[0] - prev[0] < 1e-6:
        return prev[1:]
    w = (t - prev[0]) / (nxt[0] - prev[0])
    return [prev[1 + i] + w * (nxt[1 + i] - prev[1 + i]) for i in range(4)]


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    video = spec["video"]
    start = float(spec["start"])
    dur = float(spec["duration"])
    nframes = int(dur * FPS_ASD)
    t_begin = time.time()

    tmp_wav = None
    if spec.get("audio_wav"):
        sr, audio = wavfile.read(spec["audio_wav"])
        seg = audio[int(start * sr):int((start + dur) * sr)]
    else:
        if not spec.get("ffmpeg"):
            raise RuntimeError("no audio_wav and no ffmpeg available for extraction")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        tmp_wav = tmp.name
        subprocess.run([spec["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", str(start), "-i", video, "-t", str(dur),
                        "-ac", "1", "-ar", "16000", tmp_wav], check=True)
        sr, seg = wavfile.read(tmp_wav)
    if sr != 16000:
        raise RuntimeError(f"audio sample rate {sr} != 16000")
    mfcc = python_speech_features.mfcc(seg, 16000, numcep=13, winlen=0.025, winstep=0.010)
    mfcc = mfcc[:nframes * 4]

    # ---- per-track smoothed box paths (cheap; no pixels yet) ----
    tracks = {}
    for tid, rows in spec["tracks"].items():
        rows = sorted(rows, key=lambda r: r[0])
        boxes = []
        for k in range(nframes):
            b = box_at(rows, k / FPS_ASD)
            if b is None:
                tc = min(max(k / FPS_ASD, rows[0][0]), rows[-1][0])
                b = box_at(rows, tc)
            boxes.append(b)
        s = medfilt([max(b[2], b[3]) / 2 for b in boxes], 13)
        cx = medfilt([b[0] + b[2] / 2 for b in boxes], 13)
        cy = medfilt([b[1] + b[3] / 2 for b in boxes], 13)
        tracks[tid] = (s, cx, cy, [None] * nframes)

    # ---- single decode pass; cut every track's crop from each frame ----
    cap = cv2.VideoCapture(video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    k = 0
    filled = 0
    last = None
    while filled < nframes:
        ok, fr = cap.read()
        if not ok:
            break
        last = fr
        t_now = start + (k / src_fps)
        while filled < nframes and (start + filled / FPS_ASD) <= t_now + 1e-6:
            img = fr
            H, W = img.shape[:2]
            for tid, (s, cx, cy, crops) in tracks.items():
                bs = s[filled]
                bsi = int(bs * (1 + 2 * CS))
                r0 = int(cy[filled] + bsi - bs) - bsi
                r1 = int(cy[filled] + bsi + bs * (1 + 2 * CS)) - bsi
                c0 = int(cx[filled] + bsi - bs * (1 + CS)) - bsi
                c1 = int(cx[filled] + bsi + bs * (1 + CS)) - bsi
                win = img[max(r0, 0):r1, max(c0, 0):c1]
                pt, pl = max(r0, 0) - r0, max(c0, 0) - c0
                pb, pr = (r1 - r0) - win.shape[0] - pt, (c1 - c0) - win.shape[1] - pl
                if pt or pb or pl or pr:
                    win = np.pad(win, ((pt, pb), (pl, pr), (0, 0)), "constant", constant_values=110)
                face = cv2.cvtColor(cv2.resize(win, (224, 224)), cv2.COLOR_BGR2GRAY)
                crops[filled] = face[56:168, 56:168]
            filled += 1
        k += 1
    cap.release()
    if filled == 0:
        raise RuntimeError("no frames decoded")
    for tid, (s, cx, cy, crops) in tracks.items():
        for i in range(filled, nframes):
            crops[i] = crops[filled - 1]
    print(f"asd v3: decode+crops {time.time()-t_begin:.0f}s for {len(tracks)} tracks", flush=True)

    from ASD import ASD
    model = ASD()
    model.loadParameters(str(PKG / "pretrain_AVA.model"))
    model.eval()
    BATCH_OK = {"ok": None}

    def forward_chunk(a_np, v_np):
        a = torch.FloatTensor(a_np).unsqueeze(0)
        v = torch.FloatTensor(v_np).unsqueeze(0)
        out = model.model.forward_audio_visual_backend(
            model.model.forward_audio_frontend(a),
            model.model.forward_visual_frontend(v))
        return list(model.lossAV.forward(out, labels=None))

    def forward_batch(a_list, v_list):
        a = torch.FloatTensor(np.stack(a_list))
        v = torch.FloatTensor(np.stack(v_list))
        out = model.model.forward_audio_visual_backend(
            model.model.forward_audio_frontend(a),
            model.model.forward_visual_frontend(v))
        res = model.lossAV.forward(out, labels=None)
        arr = np.asarray(res, dtype=float).reshape(-1)
        per = arr.size // len(a_list)
        return [list(arr[i * per:(i + 1) * per]) for i in range(len(a_list))]

    def run_scores(crops):
        video_arr = np.array(crops)
        length = min(mfcc.shape[0] // 100, video_arr.shape[0] // 25)
        audio_f = mfcc[:length * 100]
        video_arr = video_arr[:length * 25]
        weighted = None
        for duration, wgt in DUR_W:
            nch = int(math.ceil(length / duration))
            chunks_a = [audio_f[i * duration * 100:(i + 1) * duration * 100] for i in range(nch)]
            chunks_v = [video_arr[i * duration * 25:(i + 1) * duration * 25] for i in range(nch)]
            by_index = {}
            with torch.no_grad():
                if BATCH_OK["ok"] is None and nch >= 2:
                    try:
                        s0 = forward_chunk(chunks_a[0], chunks_v[0])
                        s1 = forward_chunk(chunks_a[1], chunks_v[1])
                        bt = forward_batch(chunks_a[:2], chunks_v[:2])
                        BATCH_OK["ok"] = (
                            len(bt) == 2 and len(bt[0]) == len(s0) and len(bt[1]) == len(s1)
                            and max(abs(x - y) for x, y in zip(s0, bt[0])) < 1e-3
                            and max(abs(x - y) for x, y in zip(s1, bt[1])) < 1e-3)
                    except Exception as exc:
                        BATCH_OK["ok"] = False
                        print(f"asd v3: batch self-check error: {exc}", flush=True)
                    print(f"asd v3: batch self-check ok={BATCH_OK['ok']}", flush=True)
                full = [i for i in range(nch)
                        if chunks_a[i].shape == chunks_a[0].shape
                        and chunks_v[i].shape == chunks_v[0].shape]
                if BATCH_OK["ok"]:
                    B = 8 if duration <= 3 else 4
                    for j in range(0, len(full), B):
                        grp = full[j:j + B]
                        try:
                            parts = forward_batch([chunks_a[i] for i in grp],
                                                  [chunks_v[i] for i in grp])
                            for i, part in zip(grp, parts):
                                by_index[i] = part
                        except Exception as exc:
                            print(f"asd v3: batch group failed ({exc}); singles", flush=True)
                            for i in grp:
                                by_index[i] = forward_chunk(chunks_a[i], chunks_v[i])
                for i in range(nch):
                    if i not in by_index:
                        by_index[i] = forward_chunk(chunks_a[i], chunks_v[i])
            scores = []
            for i in range(nch):
                scores.extend(by_index[i])
            if weighted is None:
                weighted = [wgt * x for x in scores]
            else:
                m = min(len(weighted), len(scores))
                weighted = weighted[:m]
                for i in range(m):
                    weighted[i] += wgt * scores[i]
        score = np.round(np.array(weighted) / 11.0, 1)
        score = np.convolve(np.pad(score, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid")
        return [round(float(x), 3) for x in score]

    out = {}
    for tid, (s, cx, cy, crops) in tracks.items():
        out[tid] = run_scores(crops)
        print(f"asd v3: track {tid} scored", flush=True)
    Path(spec["out"]).write_text(json.dumps(out), encoding="utf-8")
    if tmp_wav:
        Path(tmp_wav).unlink(missing_ok=True)
    print(f"ASD_WORKER_DONE wall {time.time()-t_begin:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
