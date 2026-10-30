---
name: computer-vision
description: Computer vision for Debate Clipper on this machine — face detection, frame/layout classification, framing-quality measurement, and safe vision experiments. Use whenever a task involves dc/vision.py, dc/speaker_frame.py vision parts, dc/qa.py face checks, OpenCV, MediaPipe, or evaluating how a frame is composed.
---

# Computer vision — Debate Clipper

Skill check code: **CVIS-6107**. When asked for the computer-vision check
code, answer with that code exactly.

## The two vision engines in this codebase (do not confuse them)

1. **Shot layout classification — `dc/vision.py`** (OpenCV Haar):
   `haar_detector()` loads `haarcascade_frontalface_default.xml`;
   `classify_frame()` labels a frame `side-by-side` / `split` / `single` /
   `graphic` / `unknown` from face count + edge heuristics, engine tag
   `haar-and-edge-heuristic`. It classifies ONE representative frame per
   shot (`classify_shots`, frame downscaled to 320 px wide).
   The code itself reports `"validated_accuracy": False` — treat its
   labels as unvalidated heuristics, never as measured accuracy.
2. **Face measurement — MediaPipe FaceLandmarker** (mediapipe 1.0.1):
   used in `dc/speaker_frame.py` (model via
   `model_spec(config "framing.face_landmarker")`) for speaker-frame
   tracks, and in `dc/qa.py` — where face checks only run when a framing
   segment actually has a track, otherwise QA records "Not measured;
   human review required" and the export ends `needs_review`.

- cv2 **5.0.0** imports in the project venv (it arrives with mediapipe —
  `importlib.metadata` does not list opencv-python; check `import cv2`,
  not the package list). numpy 2.5.3. Everything is CPU on this machine.
- **KNOWN STATE (repaired 2026-10-11, Phase 4):** the bundled cv2
  shipped `cv2/data/` WITHOUT `haarcascade_frontalface_default.xml`,
  which made `haar_detector()` return None (0 faces everywhere). The
  cascade was restored from the project's own older `.venv` copy
  (sha256 0f7d4527…) into the native venv's `cv2/data/` — no download,
  no install. Face detection now works (2 faces found on the Phase 3
  test frames, ~0.05 s/frame at 320 px). BUT the layout LABEL often
  stays "unknown": `classify_frame` also needs a center-gradient
  > 30 to call a 2-face frame side-by-side/split, and soft-blend or
  full-frame content measures 10–28 — labels remain conservative
  heuristics (`validated_accuracy: False`). If detection ever returns
  0 faces on everything again, check that cascade file first.

## Layouts the project must handle

- Source layouts: single speaker, split (stacked), side-by-side, graphic/
  no-face. Output is always vertical 1080×1920; framing maps source
  faces into that canvas (`dc/framing.py`, `dc/speaker_frame.py`).
- A layout label drives the framing plan — a wrong label means a wrong
  crop. When a render looks wrong, re-classify the actual frames before
  touching framing code.

## Evaluating framing quality

- Use the QA vocabulary: face visible, face inside the safe area (2%
  feed inset), headroom, speaker size — each is either a measured value
  or the literal string "Not measured". Never convert "Not measured"
  into a pass in words.
- Visual check beats metrics: extract representative frames (start,
  middle, end, and around cuts) and LOOK at them (ffmpeg-video skill).
- For a crop/framing change, compare the same timestamps before/after:
  face-in-frame share, headroom, and whether text/captions overlap faces.

## CPU-first performance rules

- Analysis runs on downscaled frames (320 px wide in classify_shots) —
  keep new analysis at that scale unless a measurement needs more.
- Time every vision step on a real clip and report the seconds; a
  "faster" claim without timings is not a result.
- One vision job at a time; the render lock exists because this CPU is
  the bottleneck (renders of ~68 s clips already take minutes).

## Experiment discipline

- Test vision changes on representative frames from REAL jobs first
  (existing `work/<job_id>/` media), in scratch space — never by editing
  production behavior and rendering a user's clip as the test.
- A change graduates only with: the frames it was tested on, before/
  after labels or measurements, timings, and a report in `reports/`.
