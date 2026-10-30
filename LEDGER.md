# Verification ledger

| Feature | Level | Evidence |
|---|---|---|
| Config loader, schema, safe paths | V1 | `tests/test_core.py` |
| PL-2 layout validator and headline fitter | V1 | `tests/test_layout.py`; real headline overflow fixed during V3 render |
| ASS colour conversion, grouping and slot solver | V2 | `tests/test_captions.py`, `work/job_1a214ca47eba/captions_plan.json` |
| Chrome builder | V3 | `work/job_verify_v5/chrome.png`, `exports/c_3c6c100b3289/chrome.png`, `work/job_verify_v5/export_report.json` |
| FFmpeg renderer, WIDE graph, audio limiter and QA | V3 | `work/job_verify_v5/render.graph`, `exports/c_3c6c100b3289/clip.mp4`, `work/job_verify_v5/export_report.json` |
| Sub-pixel renderer, decoded pan smoothness | V2 | `tests/test_render_acceptance.py`, `reports/verification_v5/subpixel.json`; no labelled real-face gate |
| L0 debate graph, scoring, boundaries and integrity flags | V3 | `tests/test_selection.py`, `work/job_verify_v5/candidates.json`; accuracy/calibration remains unmeasured |
| Glossary correction and claim gate | V1 | `tests/test_integrity.py` |
| Export sidecars, stable filename and publish dry-run | V3 | `exports/c_3c6c100b3289/` |
| Studio request hardening and editing | V2 | `tests/test_studio_security.py`, `tests/test_ops_hardening.py`, `reports/verification_v5/browser.txt`; real phone unmeasured |
| Scene/audio analysis artifacts and bounded long-source scan | V3 | `work/job_verify_v5/shots.json`, `acoustics.json`, `signals.json` |
| Historical verification suite | V1/V2 | 65 pytest passes; same65 unittest cases OK; `reports/verification_v5/summary.json`; current checks below supersede this snapshot |
| Historical Poppins libass calibration | V2 | `reports/verification_v5/caption_calibration.json`: RIGHT172×44; current Montserrat evidence below supersedes default-font choice |
| Noto Emoji glyph, negative fallback and 30-headline fitter | V2 native/Linux | `reports/native_windows/doctor.txt`, `tests/test_extended_requirements.py`, `tests/test_emoji_fallback.py`: absent/notdef fonts drop glyph and save reason; actual fonts/Pillow, not mocks |
| Caption modes, timed evidence/progress, silence edits, audio mixing, variants | V2 | `tests/test_feature_rendering.py`; actual FFmpeg graphs |
| Render crash recovery and deterministic artifacts | V2 | `reports/verification_v5/recovery.json`; real-model ASR recovery is separately measured below |
| Requirement/subsection and T-01–T-36 traceability | documentation | `reports/requirements_traceability.md`; this is not an acceptance pass |
| Proposal-only taste/analytics training | V1/V2 | `tests/test_learning.py`; actual CV on synthetic fixtures, not channel labels |
| Default vs fast-glow real benchmark | V3 | `reports/verification_v5/bench_render.json`; ASS faster on this clip, alternative default remains off |
| Hash-pinned core/native ASR profiles | V2 native/Linux | `requirements.lock`, `reports/windows_install.txt`, `reports/verification_v5/lock_install.txt`; actual core installs both OSes; `requirements-asr-windows.lock` and `reports/native_windows/asr_wheel_hashes.txt` resolve all51optional-profile wheels with hashes |
| Actual CLI render cancellation | V2 | `reports/verification_v5/cancel.json`: cancelled state, exit 130, no surviving owned child |
| Real explicit manual moving path | V3 | `reports/verification_v5/real_moving.json`: real source trim/audio/loudnorm/subpixel path QA passed; automatic framing unverified |
| RGB/BT.709 patch accuracy | V2 | `reports/verification_v5/colour.json`: maximum Delta E76 1.542896≤3 |
| Sampled real bottom bleed | V3 | `reports/verification_v5/bleed.json`: CRF18/20/23, configured guard 4 px holds on the sampled interval |
| Actual OTIO parser round-trip | V2/V3 | `reports/verification_v5/nle.json`: Python3.12.15/OpenTimelineIO0.18.1; actual NLE application import unverified |
| Private publisher stub/gates | V1 | `reports/verification_v5/publish_stub.json`; no live upload |
| L1/L2 models, diarization, reaction classifier, translation | V0 | Disabled pending licensed weights and golden-set gates |
| Real-footage quality targets and competitor bake-off | V0 | Seven supplied finished shorts inventoried; genuine raw-source relationships, independent labels/raters and commercial exports remain absent; `reports/supplied_media/golden_requirements.md` |
| Supplied original Political Lens emblem | V3 | `reports/supplied_media/logo_render.json`: original-artwork identity and12-frame whole-chrome MAE; adjoining live wordmark remains a fallback |
| Current reference study/header/hook bbox | V2/V3 sampled | `reports/supplied_media/style_measurements.json`, `reference_bbox.json`: five images/six videos studied, all five bbox errors<=10px; no human/SSIM claim |
| Current Montserrat/libass RIGHT/glow | V2 | `reports/supplied_media/current_caption.json`: unchanged size/centre/halo gates; legal closest tested fallback, not identified CapCut font |
| Current acceptance suites | V1/V2 | `reports/current_checks_final/summary.json`, `pytest.txt`, `unittest.txt`; `reports/native_windows/summary.json`, `pytest.txt`; start/end hashes include tests/tools/config/fonts/locks |
| Actual native moving real render/QA | V3 | `reports/native_windows/summary.json`, `work/job_native_windows_acceptance/`; explicit manual path, unknown rights, no automatic-speaker accuracy claim |
| Current Linux static real render/QA | V3 | `reports/current_checks/real_static.json`, `reports/current_checks_final/real_qa.json`, `work/job_current_static/`; saved transcript-bearing plan |
| Native setup and actual Studio launcher/HTTP | V2 | `reports/native_windows/setup.txt`, `studio.json`, token-redacted launcher log; actual PowerShell/native loopback listener/CSP/403/owned-tree teardown, not human clicking |
| Actual native cancellation/priority/awake release | V2/V3 scoped | `reports/native_windows/summary.json`: isolated cancel job/exit130/no owned survivors/below-normal; low-battery/overnight human scenario not induced |
| Verification-only offline Whisper ASR recovery | V3 | `reports/native_windows/asr_recovery.json`: real120s source excerpt, actual mid-inference controller kill/resume/baseline, identical transcript/graph/candidate hashes/no owned survivors; speech coverage is not word accuracy |
| Complete export-bundle transaction/recovery | V1/V3 | `tests/test_bundle_transactions.py`, `reports/native_windows/bundle_recovery.json`: real sidecar/metadata worker kills at disclosed barriers, previous bundle retained/all recovered file hashes equal uninterrupted build |
| Strict export QA acceptance | V1 | `test_hard_qa_failure_cannot_be_overridden_by_review_acceptance`: literal true only for needs_review; no hard-failure export |
| Hash-verified analysis/selection checkpoints | V1 | `tests/test_checkpoints.py`: corrupt/malformed/path artifacts rejected; actual heatmap/word/rights/rejection keys invalidate; palette/mode/CRF reuse; full ASR/render-stage contracts remain partial |
| Excluded identifiable opponent/I-2/Auto block | V1 synthetic transcript | `tests/test_selection.py::SelectionTests::test_one_sided_clip_flags_identifiable_response_cut_from_full_source`; exact full-source response evidence within15s; unknown/distant negative cases; golden fairness unproven |
| Full official FCPXML1.10DTD acceptance | V2/V3 format | `reports/current_checks/fcpxml.json`: real libxml2/official DTD, real and25/30fps timeline fixtures valid/missing-ref negative rejected; actual NLE application imports unverified |
| Current public vendor/platform recheck | documentation | `reports/release_policy_recheck.md`: fetched official YouTube/TikTok developer text; inaccessible Instagram/TikTok community pages explicit; no account audit or superiority claim |
| QA six actual encoded negative faults | V2 | `reports/current_checks/qa_negatives.json`: all6flagged/positive control passed/unchanged core; active-glyph mask fixes wrong-BGR false pass; original saved plans/hash-verified actual encodes reused |
| Physical guard/both-boundary bleed acceptance | V2/V3 sampled | `reports/current_checks/bleed.json`:12guarded real/high-contrast CRF18/20/23renders/72samples pass, top extent=-1/bottom max3fits unchanged4px allowance; initial CRF23distance5failure kept in `bleed_pre_physical_guard.json`; old RenderPlans retain original behavior |

Historical Poppins export/source/rights evidence remains in
`reports/verification_v5/current_export_report.json` and `export_hashes.json`.
Current-font/native evidence is cited above. Check each summary's final status
and changed-input flags, not only its test count. All `[assumed]`
selection/performance/retention priors remain assumed unless a cited measurement
explicitly replaces them. `reports/requirements_traceability.md` and
`reports/open_gaps_ABC.md` retain uncompleted engineering as A; no V4 or full
project-acceptance claim is made.
