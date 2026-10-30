# APEX - LR-ASD integration design (DRAFT for controlled implementation)

Evidence (lab, hand-labelled windows, same scorer per window):
- W1 (split-screen, 64.5 s labelled): production fallback correct 38.0%, WRONG 43.4%, wide 14.0%. LR-ASD + Director (temp 0.5): correct 52.7%, WRONG 7.8%, wide 39.5%.
- W2 (single camera, 54.0 s labelled): production correct 53.7%, WRONG 32.4%, wide 13.9%. LR-ASD + Director (temp 0.5): correct 51.9%, WRONG 7.4%, wide 40.7%.
- Primary win on BOTH windows: wrong-person time collapses (43->8, 32->7). Cost: more wide (safe) time. Signal readout separates speakers cleanly on both windows; bystander control track stays flat/low.

Design:
1. New module dc/asd.py. Runs LR-ASD (MIT, Junhua-Liao) in the same native-venv worker pattern the app already uses for MediaPipe (config/local_tools.json). Weights + minimal model code vendored under assets/models/lr_asd/ with licence + attribution. No new runtime downloads.
2. analyze_window: after tracking, merge fragments into canonical persons (union-find: centre <150px, temporal overlap <=25% of shorter span - lab-proven). Score EVERY canonical track with >=30 observations (lab filter of 120 starved W2 stage shots; inactive frames use clamped last box, as in the lab).
3. Per 1/6 s slice: slice-mean logits -> softmax with temperature 0.5 -> the EXISTING Director state machine decides SINGLE/WIDE/DUAL. Crop math unchanged (fallback path functions).
4. Gate: preset flag asd.enabled (default OFF). When off, when the worker is missing, or when ASD fails for any reason, behaviour is EXACTLY today (mouth-motion fallback). framing_gate.json stays absent. Failure must be loud in the job report, never silent.
5. Report active_speaker evidence in export_report when ASD ran (scores summary), so QA can see which brain framed the clip.

Main open risk - SPEED: lab run took ~8 min per ~65 s window on this CPU (sequential decode + 11-duration ensemble + per-track passes). Before production use, run experiment E7: reduced ensemble {1,2,3} and shared frame decode across tracks; accept only if accuracy holds on W1+W2 and time drops materially. Analysis already takes minutes per window, but 8 min per candidate window is too slow for multi-candidate jobs without the optimisation.

Rollout discipline: implement behind the flag -> pytest (151) green -> lab harness re-run on W1+W2 against production code path -> one real job render with flag ON, QA frames checked -> only then consider default ON. Rollback = flag off.
