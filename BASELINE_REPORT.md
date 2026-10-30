# BASELINE REPORT — Apex Evolution Mission (Stage B audit + Stage C baseline)
Date: 2026-10-15. Code state: app exactly as found (post Phase 4D restore). Nothing changed yet.

## How the camera actually works today (read from code, dc/vision.py + dc/framing.py + dc/cli.py)
1. analyze_window: proxy frames (15 fps with the MediaPipe face landmarker, configured in
   config/political_lens.json; 6 fps otherwise). Haar cascade finds faces on the proxy;
   MediaPipe landmarks give mouth movement per face track. Scene cuts from frame-diff.
2. directed_framing has TWO directors:
   a. The MEASURED director: softmax over audio-visual correlation scores, switch margin 0.30,
      dwell/hold gates. It runs ONLY if reports/framing_gate.json exists and passes
      (enabled, wrong_speaker_fraction <= 0.15, face_safe_fraction >= 0.98).
   b. The FALLBACK director (mouth motion): per-track mouth-movement std in a +/-1.5 s window;
      winner needs std >= 0.012 AND >= 2x the runner-up, else WIDE (AMBIGUOUS_SPEAKER);
      switch hold 0.6 s, min dwell 1.5 s, evidence older than 3 s drops the selection.
3. Camera path: smooth_path (tau_follow 0.35 gated / tau_slow 0.8 fallback) + rate_limit_path
   (max pan 180 px/s, max zoom 0.18/s, deadband available, cuts snap). Sub-pixel warp renderer.
4. Diarization (dc/diarization.py): sherpa_onnx / pyannote engines exist in code, but the
   project LEDGER records L1/L2 models + diarization as V0 "Disabled pending licensed weights
   and golden-set gates". Live jobs show every speaker as "unknown".

## Confirmed defects / gaps (evidence in brackets)
D1. reports/framing_gate.json DOES NOT EXIST -> the measured director NEVER runs in
    production; every auto export uses the mouth-motion fallback. [file check 2026-10-15]
D2. Speaker accuracy is never measured anywhere ("Not measured" in plan debug + QA;
    framing_quality face fields all "Not measured"). [dc/framing.py, dc/vision.py, dc/qa.py]
D3. Diarization off (V0) -> transcript speakers all "unknown"; no voice evidence feeds the
    camera at all in the live path. [LEDGER.md; job_7f53eed224b2/turns.json]
D4. Face detection on the analysis path is OpenCV Haar (weak on profiles/small faces) at
    640 px proxy width; MediaPipe landmarks mitigate but tracking quality is unmeasured.
D5. Political Lens assets/wordmark.png MISSING (only the Open Debate wordmark exists);
    PL exports fall back to drawn text. [assets/ listing 2026-10-15]
D6. No labelled golden set with independent raters exists (project open_gaps_ABC.md asks
    for reports/golden/raters.json, 2 raters, blind clips) -> no regression gate is possible
    until a labelled set exists. The "golden accuracy video" folder holds 7 finished shorts
    (kirks13 + political lens 17/20/27/70/78/86) — usable as references, not as labels.

## Baseline measurements (Stage C — filled as runs complete)
- Test suite (pytest, unchanged code): **151 passed, 0 failed** in 120.10 s (reports/apex/pytest_baseline.log).
- Baseline render (existing job job_7f53eed224b2, candidate c_a117ced1c94c, layout auto,
  Pittsburgh source U_BY2ENwPyA, window 348.64-411.42 s, 62.78 s): RUNNING
  -> reports/apex/render_baseline.log
- That job's saved fallback plan (from jo's own session): 13 segments / 62.78 s —
  9 SINGLE (LOCAL_MOUTH_MOTION, confidence 0.5), 4 WIDE (AMBIGUOUS_SPEAKER);
  390 path points at 6 decisions/s. This is the behaviour the baseline render reproduces.

## Baseline render result (2026-10-15, unchanged pipeline)
- Artifact: work/job_7f53eed224b2/c_a117ced1c94c.mp4 (34.5 MB, 62.78 s) + proxy.
- App QA (export_report.json): status **needs_review**.
- Rendered-face measurement (measure_rendered_faces, 12 samples): face found 9/12;
  all 9 inside the safe area; headroom fraction 0.102-0.236; face height fraction
  0.184-0.206 (design target 0.20 — the geometry lands as designed); centre offset
  <= 0.047. Camera: 9 moves, 12 clean cuts, max pan 140.26 px/s (limit 180) — PASS.
- active_speaker_accuracy: "Not measured" — the 3 unmeasured samples and every SINGLE
  choice remain unverified as to PERSON. Geometry is proven; identity is not.

## FIRST MEASURED SPEAKER SCORES (Stage E, window W1, 2026-10-15)
Window W1: Pittsburgh source 2560-2635 s (75 s; 64.5 s hand-labelled by Pax from the
transcript + 13 inspected frames; speakers: Questioner / Vivek / Kirk; split-screen).
Scorer + labels + plans: work/apex_lab/ (gate_lab.py, score_W1.py, W1/).
- PRODUCTION (mouth-motion fallback): correct speaker 38.0% of labelled time,
  WRONG speaker 43.4%, wide/ambiguous 14.0%, crowd/other face 4.7%; 20 switches/75 s.
- GATED correlation director (force-enabled in lab only): correct 0.0%, wide 91.5%.
  Its per-track correlations on this window were noise (true speakers 0.06/0.07/-0.02;
  max 0.26 on a crowd fragment) and its probabilities are static per window, so it
  cannot follow turn changes. VERDICT: do NOT write framing_gate.json; the gate stays
  closed as a MEASURED decision. The fallback is also far below an acceptable bar.
- Track fragmentation (same analysis): 29 track ids for 3 speakers; the questioner
  alone is split across 8 ids (2,3,4,6,10,14,17,21). Fragments compete with each
  other in every per-track score, corrupting both directors.
Fix order decided from this evidence: (1) repair/merge fragmented tracks,
re-measure the fallback; (2) per-time-slice ASD scores (LR-ASD, MIT) into the
existing Director if (1) is not enough; (3) keep the Director state machine.
