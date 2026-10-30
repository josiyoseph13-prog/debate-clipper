# TOOL RESEARCH — Apex Evolution Mission (Stage D, per directive Part 5.3)
Researched 2026-10-15. Rule: no tool enters production on reputation — each must beat the
measured baseline on the labelled golden windows (Stage E harness) or it is rejected.

## Candidate 0 — Complete the built-in gate (no external tool)
- Problem: the measured AV-correlation Director in dc/vision.py never runs because
  reports/framing_gate.json was never produced; production always uses mouth-motion fallback.
- Evidence available today: analysis already computes per-track mouth/audio correlations;
  the diarization ONNX weights are already on disk (assets/models/duo_diarization).
- Integration: label golden windows -> measure both built-in directors -> write an honest
  gate file. Effort: low-medium. Risk: near zero (deleting the file reverts). Maintenance: ours.
- Verdict: DO FIRST. It creates the measurement harness every other candidate needs.

## Candidate 1 — LR-ASD (successor of Light-ASD), Junhua-Liao/LR-ASD (+ Light-ASD)
- Problem solved: true audio-visual active-speaker scoring per face track (who is talking),
  replacing/augmenting the mouth-std heuristic and the crude corrcoef correlation.
- Evidence: CVPR 2023 (Light-ASD) + IJCV 2025 (LR-ASD); ~94.1% mAP on AVA-ActiveSpeaker;
  1.0M parameters (~23x smaller than TalkNet-class), 0.6 GFLOPs — built for weak hardware.
- Licence: MIT (code + released weights, per repo LICENSE and third-party notices).
- Maintenance: repo last pushed ~2025 (571 days ago at check); small, stable codebase.
- Requirements: PyTorch; face tracks as input (ours exist); a Columbia-style demo runs
  end-to-end on an arbitrary mp4 (S3FD detect -> track -> per-track scores).
- Fit on this PC: best of the ASD candidates (MX450 2 GB / CPU inference plausible).
- Speed: unmeasured here — must benchmark on golden windows before any adoption.
- Failure modes: off-screen speakers, profile faces, very small faces, dubbed audio.
- Integration cost: medium — a scoring sidecar that emits per-track probabilities into
  analysis["correlations"]/probabilities shape the Director already consumes.
- Verdict: PRIMARY ASD candidate if the built-in correlation director fails the gate.

## Candidate 2 — TalkNet-ASD (TaoRuijie/TalkNet-ASD)
- Problem solved: same as LR-ASD; the classic reference implementation.
- Evidence: widely used (incl. a similar clipping tool, clips-studio, which vendored it
  unmodified under MIT and reports it decisively beating mouth-motion scoring, whose
  talker/listener signals measured nearly identical: 0.0746 vs 0.0801 on their clip).
- Licence: MIT (c) 2021 Tao Ruijie (per clips-studio NOTICE vendoring).
- Requirements: PyTorch + S3FD detector; heavier than LR-ASD (22.5M params class).
- Fit on this PC: workable on CPU but slower; second choice behind LR-ASD.
- Verdict: fallback ASD candidate / cross-check reference.

## Candidate 3 — YuNet face detector (OpenCV Zoo)
- Problem solved: replace weak Haar detection on the analysis path (profiles, small faces).
- Licence: MIT. Maintenance: OpenCV official model zoo. Requirements: none new
  (cv2.FaceDetectorYN ships inside opencv-python already installed).
- Integration cost: low (detector swap inside analyze_window; tracks/landmarks unchanged).
- Verdict: test as a one-variable experiment AFTER the gate harness exists, so its effect
  on wrong-speaker fraction is measured, not assumed.

## Candidate 4 — sherpa-onnx diarization (weights already on disk)
- Problem solved: real speaker turns for the transcript (today every speaker is "unknown"),
  giving the camera a voice-activity signal and enabling speaker-labelled captions later.
- Evidence: segmentation.onnx (5.99 MB) + embedding.onnx (28.3 MB) present since 2026-10-07
  with licence + model cards in assets/models/duo_diarization; dc/diarization.py already
  implements the sherpa path. MODELS.md still lists it "disabled until installed" — stale.
- Integration cost: low-medium (config/registry enablement + a DER-style check on labelled
  windows; cluster labels are NOT identities and must stay labelled as such).
- Verdict: enable in the lab after the gate harness; measure before any production use.

## Rejected at desk stage
- Commercial APIs / cloud ASD: excluded by the directive (Part 19) and unnecessary.
- Full framework replacements (new editors/renderers): the renderer + camera path are
  sound; the defect is speaker evidence, not the framework (Part 5.2 smallest replacement).
