# Implementation status — Political Lens v5 (2026-10-05)

**Current status:** engineering continues; full `MASTER_BUILD_PLAN_V5.md`
acceptance is incomplete. The current pass is documented in
`reports/M13_report.md`; `reports/requirements_traceability.md` and
`reports/open_gaps_ABC.md` list remaining engineering (A), user inputs (B), and
unproven quality (C). Historical reports remain an audit trail.

## Shared-core mechanisms (remaining contracts are in traceability)

- Versioned PL-2 configuration, schema validation, cache/hash primitives,
  SQLite job state, atomic artifacts, safe subprocess wrapper and doctor.
- Deterministic chrome/headline fitter with `brand_check` default, the original
  supplied Political Lens emblem, measured hook ink and wordmark-fallback warning.
- Feed-local kinetic ASS captions, BGR colour conversion, grouping, slot
  collision solver, glow layers, and caption plans.
- Ingest/source fingerprint, metadata/rights classification, faster-whisper
  adapter, VAD-compatible guards, glossary correction, audio helpers and
  offline diarization fallback.
- L0 debate graph, Q&A/challenge/concession/evasion candidates, context-aware
  boundaries, explainable component scores, diversity, prompt search,
  fairness, crowd/source-hygiene null-safe hooks, and integrity claims.
- Conservative crop math, WIDE fallback, smoothing/interpolation and
  sub-pixel OpenCV warp helper.
- Windows-safe FFmpeg graph with audio trims/fades/loudnorm, CFR cap,
  BT.709/tv output tags, atomic render output and deterministic QA report.
- Question chips, evidence cards, receipts safety record, tight-cut/punch-in
  planning, metadata, provenance, edits, cover extraction, SRT/VTT/ASS,
  OTIO/FCPXML/EDL, publish CSV and publish dry-run gate.
- CLI includes run/find/render/validate/preview/receipts/series, batch/worker/
  watch/cancel/resume, Studio, learning/analytics/evaluation and diagnostics.
- Local FastAPI Review Studio baseline with localhost binding, Origin/LAN
  token checks, ID-only file lookup, CSP, and text-node rendering.
- Proposal-only logistic taste/ridge analytics models with sample/CV gates;
  production learned layers remain off. Registered MIT Whisper-base weights
  are available for actual offline ASR verification, not a production-quality claim.
- OS-owned execution/decision locks, persistent child ownership, cooperative
  cancellation, identity-checked orphan recovery, and hash-pinned core install.

## Verification level

- Latest frozen-tree run: **76pytest passes on Linux and native Windows**;
  the same76unittest cases are OK/no skips on Linux. Linux summary is passed,
  native summary is passed_automated_scope; both changed-input flags are false.
  One Starlette/httpx deprecation warning remains in each pytest run.
- Current Linux suites/standalone real-output QA:
  `reports/current_checks_final/summary.json` and raw logs. Native tests/actual
  real moving render/QA/cancel/priority/awake release:
  `reports/native_windows/summary.json`. Only the final passing status with
  unchanged-input flags is acceptance for that automated scope.
- Actual PowerShell setup/Studio HTTP loopback/token/Origin/CSP/teardown:
  `reports/native_windows/setup.txt`, `studio.json`. Human clicking/phone/video
  review is still open.
- Supplied emblem identity/twelve-frame chrome, all five header/hook bboxes
  within10px, closest-tested licensed Montserrat fallback/calibrated RIGHT/glow:
  `reports/supplied_media/`. Exact CapCut identity/human equivalence is unproven.
- Actual120s offline-model ASR kill/resume/baseline hash parity and real complete
  export-bundle worker-kill recovery: `reports/native_windows/asr_recovery.json`,
  `bundle_recovery.json`. No hand-labeled word or model-accuracy claim.
- T-19 one-sided full-source response/I-2/Auto regression and T-22 real
  absent/notdef-font drop/reason persistence are in the current suites.
- T-14 now flags all six actual encoded faults, including wrong-BGR text over
  green footage. Physical4px in-feed guards pass all12real/pattern boundary
  cases/72samples at CRF18/20/23, without relaxing white/chrome thresholds;
  the failed pre-guard high-contrast case remains recorded.
- Current real static output: `work/job_current_static/clip.mp4`, planned33.45s,
  with saved transcript-bearing plan. Historical Poppins export remains at
  `exports/c_3c6c100b3289/`; its65-test suite/old metrics are historical evidence.
- Historical actual browser, decoded subpixel pan, colour, OTIO and render-crash
  results remain in `reports/verification_v5/`. Official FCPXML1.10DTD real/25/30fps
  validation is in `reports/current_checks/fcpxml.json`; NLE app imports unverified.

The real source `xmp4EdJvPfo` is1173.654s, SHA256
`40101663d58eba7684ee89629ae616f8707fc4d4c2f3ac88eabb6064fca0cb42`.
Rights remain **unknown** and publishing is blocked. Five images, six reference
videos and seven golden shorts are available and inspected. The separate
production wordmark/clean full-size frame, genuine raw-source mappings/rights/
labels/raters/platform/account inputs and human review remain. Optional-stack
implementation, full stage contracts and other listed A work remain engineering.
No V4, superiority, or full-project completion claim has been made.
The requested short report is `OMNIRUSH_FINAL_REPORT.md`; the regenerated
audited list retains97A/45B/40Ctagged entries with overlap, not independent
task counts. Group A remains unfinished.
