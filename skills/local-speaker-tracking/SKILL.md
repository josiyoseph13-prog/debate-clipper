# speaker-tracking (Pax — independent verification)

## The project's tracking stack (what is being verified)

- `dc/vision.py` `Director` — conservative camera state machine (starts
  WIDE; a new track waits in `pending` before taking over — hysteresis
  against jumpy reframing).
- `dc/speaker_frame.py` `build_framing(...)` — per-segment framing from
  speaker boxes/tracks, turns, cuts, observations; MediaPipe
  FaceLandmarker supplies measurements.
- `dc/framing.py` — `smooth_path(tau=0.35)` camera smoothing;
  `framing_quality` movement stats. Export QA limits: camera
  **≤180 px/s**, zoom **≤0.18 fraction/s**.
- `dc/diarization.py` — sherpa-onnx 1.13.8 `diarize_audio` (pyannote
  segmentation + embeddings). **Not configured** (`diarization.model`
  unset): today's transcripts/turns carry speaker `"unknown"`. Any
  active-speaker claim that cites diarization is therefore false today;
  claims must rest on face tracks or manual assignment.
- Product rule (jo): manual speaker assignment ALWAYS wins over
  auto-detection; detectors suggest, the user decides.

## Verification protocol

1. Evidence first: for any "follows the speaker" claim, pull the frame
   series (every ~2 s plus at speaker changes) from the actual render
   and look: right person framed? switches late/early? jumps?
2. Numbers second: `export_report.json` QA (camera_jump px/s vs the
   180 limit, zoom vs 0.18, clean cuts), the plan's framing segments
   and track data, `turns.json` speaker values.
3. Occlusion/missed-detection behavior: find a moment a face leaves or
   is covered — the framing must hold or widen, not snap to a wrong
   face or freeze a stale crop.
4. A/B changes the honest way: same 10–15 s window of a real clip —
   `D:\capcut finished project\charlie kirk\political lens55.mp4`
   (39.2 s, 1080×1920) is the standing sample — production vs candidate,
   compared on face-in-frame share, camera-move count, limit
   compliance, and viewed frames. Experiments stay out of the
   production renderer until that comparison exists.
5. Distinguish in every report: measured / observed-by-eye /
   not measured / blocked (and by what).

## Rules

- Never present diarization as working until a real job's turns carry
  non-"unknown" speakers from the project's own pipeline.
- A skill describing tracking is not tracking accuracy — verification
  is per-output, per-clip, with frames as evidence.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
