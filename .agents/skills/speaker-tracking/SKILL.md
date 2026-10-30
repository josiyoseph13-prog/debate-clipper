---
name: speaker-tracking
description: Speaker tracking and active-speaker framing for Debate Clipper — the Director state machine, speaker-frame tracks, diarization evidence, camera smoothing, and recovery from missed detections. Use whenever a task involves who is on screen, dc/speaker_frame.py, dc/framing.py, dc/diarization.py, or framing that follows speakers.
---

# Speaker tracking — Debate Clipper

Skill check code: **SPKTRK-8253**. When asked for the speaker-tracking
check code, answer with that code exactly.

## Where tracking lives

- `dc/vision.py` — `Director`: a conservative camera state machine
  (starts `WIDE`; holds a current track; a candidate change sits in
  `pending` until it persists — this hysteresis is what prevents jumpy
  reframing). Inputs: per-time probabilities, crosstalk, feasibility.
- `dc/speaker_frame.py` — `build_framing(spec, source, duration, config,
  turns, cuts, observations)` builds per-segment framing from speaker
  boxes/tracks; `compose_frame` renders a segment; boxes are validated
  by `validate_speaker_frame`.
- `dc/framing.py` — `smooth_path(points, tau=0.35)` smooths the camera
  path; `framing_quality` reports movement. Export QA enforces camera
  limits: **≤180 px/second** pan and **≤0.18 fraction/second** zoom —
  a track that violates these fails QA, by design.
- `dc/diarization.py` — who-spoke-when. `diarize_audio()` uses
  sherpa-onnx 1.13.8 (pyannote segmentation + speaker embeddings,
  2 threads, mono audio at model rate). **Current state: no diarization
  model is configured** (`diarization.model` unset), so turns carry
  speaker `"unknown"` and diarization returns the transcript unchanged.

## Rules for active-speaker decisions

- Claim an active speaker ONLY from evidence: diarization turns, a
  face track, or the user's manual assignment. With speakers "unknown",
  the honest output is a wide/both framing or a stated guess — never a
  confident single-speaker crop.
- **Manual always wins**: a speaker the user assigned in Studio
  (Speaker A/B, pins) overrides any detector output, per the product
  rules. Detector output is a suggestion.
- Crosstalk and rapid exchanges: prefer holding the current framing
  (Director pending state) over chasing every switch; sub-second
  switches are a QA and comfort failure, not responsiveness.

## Occlusion, missed detections, recovery

- A face that disappears for a few frames is an occlusion until proven
  otherwise: hold the last good track/box; do not reframe on a single
  missed detection.
- When a track is truly lost, fall back to the wider framing for that
  segment rather than freezing a stale crop on the wrong person.
- Recovery = reacquire the face, then let `smooth_path` ease the camera
  back — never a hard jump cut to the new box (QA camera limits).

## Evaluating tracking — the A/B protocol

- Use a real sample: `D:\capcut finished project\charlie kirk\political
  lens55.mp4` (39.2 s, 1080×1920) — take the SAME 10–15 s window through
  the current production framing and the candidate change.
- Compare: face-in-frame share per speaker, number of camera moves,
  max px/second vs the 180 limit, and frames at 3–4 timestamps viewed
  side by side.
- Experiments stay OUT of the production renderer until this comparison
  exists in a `reports/` file with timings. An experiment that only ran
  on a synthetic clip proves nothing about real debates.

## Reporting

- State what evidence each framing decision used (diarization /
  detection / manual / none). "Not measured" is a valid, required
  answer when it is the truth.
