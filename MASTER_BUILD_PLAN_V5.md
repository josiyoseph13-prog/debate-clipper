# POLITICAL LENS — MASTER BUILD PLAN v5 ("APEX-2")
### The single self-contained specification for an agent that builds the whole product from this file alone
**Brand:** POLITICAL LENS · `@_political_lens` · **Output:** 1080×1920 (9:16) H.264/AAC MP4 · TikTok / YouTube Shorts / Instagram Reels
**Product:** a local-first, headless-capable debate-shorts factory that must beat Opus Clip and Klap on (1) debate narrative selection, (2) layout/crop precision, (3) caption craft, (4) brand determinism, (5) integrity safety, (6) throughput on a modest Windows PC, (7) context-preserving craft (receipts, question chips), (8) verifiable provenance.
**Lineage:** friend's v2 (algorithms) + v3 (reference-locked geometry + kit) → v4 (audit, self-contained, Part 12 features) → **v5 (second audit: Part 1.4; competitor reality check: Part 2.2; semantic stack, signals, craft, interop, learning, security, ops, monitor protocol: Parts 19–26)**. Parts 19–26 are binding and are referenced by the milestones in 18.2.

---

# PART 0 — AGENT CHARTER (read first, obey always)

## 0.1 Your role
You are the lead engineer building this product end-to-end. This file is the only spec you have. Where it is silent, choose the simplest option that satisfies the principles in 0.3, and log it in `DECISIONS.md` (date, choice, reason, alternatives).

## 0.2 Environment assumptions (verify with `doctor`, don't assume)
- Windows 10/11, project root path **contains spaces**: `D:\charlie youtube long videos\clipping automation\debate_clipper`. Every subprocess call uses argument lists (never shell strings), FFmpeg runs with the **job folder as cwd and relative paths** for `subtitles=`/`fontsdir=`/chrome, and tests must pass on a path with spaces.
- Python 3.11+, FFmpeg full build with **libass + HarfBuzz + libx264** (e.g., gyan.dev "full"), ffprobe.
- Modest hardware (laptop-class, ~8–16 GB RAM, weak/MX450-class GPU). **CPU-first design.** GPU use only after a measured benchmark proves a win.
- Network may be off for some stages: everything except optional LLM reranking and URL download must work **offline**.

## 0.3 Principles (the "why" behind every rule)
1. A clip is a **mini-story** (setup → conflict → payoff), 20–60 s.
2. The first 1.5 s decide retention: start on a spoken line that opens a question.
3. **Never misrepresent.** Context protection and fairness checks are product features; flagged risk beats silent risk.
4. Prefer a calm, wrong-safe frame over a confident wrong crop.
5. Branding is **deterministic**: same preset → pixel-identical chrome on every clip.
6. Speed comes from not repeating work: analyze only what renders, cache by content, decode once.
7. **No claim without a measurement.** Anything marked `[assumed]` below is a prior, not a fact.

## 0.4 Honesty & verification rules (non-negotiable)
- Levels: **V0** code written · **V1** unit test passes · **V2** runs on synthetic/still data · **V3** runs on real footage with recorded command + media ID + result · **V4** human-reviewed or bake-off measured. Never describe a feature at a higher level than reached. Keep `LEDGER.md`: feature → level → evidence path.
- Never edit a threshold to make a test pass without a `DECISIONS.md` entry.
- Never report a speed number not produced by `bench` with recorded command, settings, machine state.
- Never claim "better than Opus/Klap" in any output, UI or README except from the bake-off report (Part 17.4), scoped to what was measured.
- Never invent transcript words, quotes, numbers, names in captions, headlines, metadata.
- Never overwrite a source file. Never delete outside `work/<job_id>/`.
- Use git: small commits, one feature per commit, tests green before commit.
- Stop and ask the user only for the inputs in Part 18.1 (3 required: logo/wordmark, extra caption frames, badge decision; plus optional extras) — and keep building with placeholders meanwhile.

## 0.5 Precedence
This file > any older blueprint. Within this file: Part 9 (layout) and Part 11 (captions) numbers are **measured from the user's reference** and override all other numbers. Every number is an initial tunable living in `config/political_lens.json` (Appendix A). **No pixel literals in code.**

## 0.6 Agent working agreement (v5)
1. Read the whole file. Before coding, write `PLAN_ACK.md` (≤ 1 page): your interpretation, the 10 biggest risks, any contradictions you found in this file, and the first milestone.
2. Work milestone by milestone. After each, write `reports/M<n>_report.md` (Part 26.1). Commit only when tests are green.
3. Blocked twice on the same issue ⇒ log it in `DECISIONS.md`, take the documented fallback, continue. Never silently change scope.
4. Any number in a report must be traceable to a file under `reports/` or `work/`. No invented evidence.
5. Contradictions inside this file are resolved by 0.5 precedence and logged.
6. Prefer boring: the smallest implementation that passes the test. New dependencies need a `DECISIONS.md` entry (licence, size, reason).
7. Unmeasured defaults in this file marked `[assumed]` stay `[assumed]` in `LEDGER.md` until a measurement replaces them.

---

# PART 1 — AUDIT TRAIL (v2/v3 → v4 → v5)

## 1.1 Kept (sound, build as specified here)
Archetype catalog; debate graph and Q&A pairing; context-sufficiency test; ordered boundary rules with onset/decay + next-speaker guard; per-speaker acoustic baselines capped at 5%; absolute scoring with the **precision@90 ≥ 0.70** gate; MMR diversity; hook forms with fidelity + stance guards; analysis proxy (640 px / 6 fps); AV-correlation active-speaker model; SINGLE/DUAL/WIDE state machine with dwell + interruption bypass; frame-rate-independent smoothing; static chrome PNG + feed-layer isolation; reference-measured PL-2 geometry; 3-layer ASS glow; libass size calibration; lossless A/B caption QA; 4 px chroma guard; relative-path FFmpeg on Windows.

## 1.2 Defects found and corrected in v3
| ID | Defect in v3 | Fix in v4 |
|---|---|---|
| X-1 | v3 said "v2 §1/§3/§5 stand" — a builder with one file can't follow a reference to another file | **All algorithms are inlined here** (Parts 6–13) |
| X-2 | Kit config hard-codes a **Linux** emoji font path (`/usr/share/fonts/...`) — breaks on the user's Windows PC | Bundle `assets/fonts/NotoColorEmoji.ttf` (SIL OFL); load via project-relative path; Pillow needs the CBDT bitmap strike at size **109** then resize; `doctor` renders 🎓 and fails if tofu |
| X-3 | Handle ink width: 278 px in the doc table, 285 in the config | Reference measures 278 (x303–581). Config = **278**; the fitter picks the largest integer px ≤ target |
| X-4 | Dual-mode caption claim: "clear band ≈ 400 px" | Recomputed (face φ=0.28, centre 33% of panel, exclusions per §10.7): top-face exclusion ends ≈ y859, bottom-face exclusion starts ≈ y1181 → **≈ 320 px**. Still fits a ~60 px caption + halo; but the number is `[assumed]` until measured; slot solver verifies at runtime |
| X-5 | Kit render never exercised: real trim, camera-path crop expression, real audio, loudnorm (demo uses a still image + sine tone) | Part 13 specifies the real render graph; milestone M3 must pass on real footage |
| X-6 | Production QA samples only 2 frames | ≥ 12 frames for chrome, ≥ 20 caption events for A/B (Part 13.3) |
| X-7 | Glow built from 2 extra ASS layers per word event → render time ×3 on every event with blur | Keep as default; add **fast-glow alternative** (§11.6) benchmarked at M5 and chosen by measurement |
| X-8 | No source-rights / platform-policy / political-content handling anywhere | New **Part 15 Compliance & Integrity** (attribution, fair-use posture, AI/edited labeling, election-content caution, impersonation of verified badge) |
| X-9 | No ASR/diarization stack decision, no hardware budget | Part 4.2: faster-whisper + forced alignment + optional diarization with offline fallbacks; CPU int8 default |
| X-10 | Caption Dual-mode anchored to the divider could collide with the 4 px divider line | Divider is part of the exclusion set; caption box gets a 60% black rounded plate only if the divider crosses the box (§11.5) |
| X-11 | Badge default imitates a platform "verified" mark | Keep the measured reference look **by user decision**, but `doctor` prints a visible warning and one config line switches to `brand_check`/`none` (Part 15.4) |
| X-12 | Bottom 180 px band wasted | Optional, off-by-default **source credit / progress bar** (§12.9) that never changes the reference look when disabled |

## 1.3 Added in v4 (new capability — Part 12)
Prompt-based clip search · beat-synced punch-ins · silence tightening · speaker nameplates (user-labeled only) · fairness/balance meter · burned-in-text avoidance · hook A/B variants via cached feed layer · cover-frame picker · per-platform metadata pack · analytics feedback loop · clip series splitter ("Part 1/2") · audio polish chain · Review Studio with transcript-based editing · bake-off harness.

## 1.4 Defects found in v4 and corrected in v5 (second audit, 2026-10-04)
Severity: **H** = would produce wrong/unsafe output or a failed build · **M** = quality or credibility loss · **L** = editorial.
| ID | Sev | Defect in v4 | Fix in v5 |
|---|:-:|---|---|
| Y-1 | H | Mouth-activity feature uses a **0.4 s window at 6 fps ≈ 2–3 samples**; syllable-rate lip motion (≈ 4–7 Hz) is also aliased at 6 fps. The AV-correlation speaker model (10.4) would be mostly noise. | Landmark/mouth stage at **15 fps on tracked face crops** (cheap: 192–256 px crops), window **0.8 s (≥ 12 samples)**; detection stays 6 fps. Optional ASD-network slot, shipped only if it beats the baseline on T-11 (10.2–10.4). |
| Y-2 | H | FFmpeg `crop` offsets are **integers**; a slow pan (e.g., 0.3 px/frame) becomes 1-px steps every ~3 frames = visible face judder. Scale-then-crop also resamples twice. v4 left the renderer choice "to a benchmark". | Decided: any moving camera path uses the **sub-pixel renderer** (13.1b: one affine resample, OpenCV, pipe to FFmpeg). Pure-FFmpeg expression graph only for static segments. New test T-24. |
| Y-3 | M | The pipe/convert design (and v4's graph) never specifies **colour matrix/range**. RGB→YUV conversion defaults can silently shift to BT.601; chrome and skin tones drift. | Explicit BT.709 / limited-range tagging both directions; colour-bars patch test (13.1b-7, T-14 extension). |
| Y-4 | M | `r=FPS` and "source fps preserved" assume constant frame rate. **VFR sources** (phone, screen-record, many web downloads) drift or stutter; 60 fps doubles CPU render cost with little debate-content benefit. | Probe + normalise to CFR; `fps_cap` default 30 (13.1c); T-25. |
| Y-5 | M | Chroma-guard rationale ("4:2:0 chroma bleed on rows 1740–1741") is probably incomplete: rows 524 and 1740 are both even (chroma pairs don't straddle them) but **neither is a multiple of 16** (macroblock/transform/deblock/motion-compensation spread). The 4 px guard is still right; the explanation is `[assumed]`. | Keep guard. New `bleed_profile` bench: measure bleed vs row distance at CRF 18/20/23 on real footage; set the guard from data (13.3). |
| Y-6 | M | Stance opposition = "share ≥ 2 lemmas + polarity flip" and cue lexicons only. Paraphrased challenges ("that's simply not what the record shows") match nothing. No semantic model anywhere in the always-on path. | **Semantic Intelligence Stack** (Part 19): cascade L0 lexicon → L1 small local models (embeddings, NLI, QA-relevance, dialogue-act) → L2 optional LLM, each gated by measured gain. |
| Y-7 | M | Diarization default needs a **gated Hugging Face token**; the fallback is only heuristics. | Default to **sherpa-onnx offline diarization** (pyannote-segmentation ONNX + speaker-embedding ONNX; CPU; no PyTorch; no token) `[ext-verified 2026-10-04]`; pyannote optional; choose by DER (T-27). |
| Y-8 | H | **Caption name accuracy is unaddressed.** Political content is full of proper names; Whisper misspells them and hallucinates on silence/music. A wrong name burned into a political clip is a credibility and defamation risk. | ASR guard + glossary system (4.2, Part 20.5, T-26): VAD pre-segmentation, repetition/hallucination detector, hotword/prompt priming where supported, post-correction against `glossary.json` (phonetic + fuzzy, auto-seeded from title/description/chapters), one-click "fix everywhere" in Studio. |
| Y-9 | H | **Review Studio security absent.** A local FastAPI app that renders transcripts, video titles and comments (all attacker-controlled text) and can run FFmpeg/write files is an XSS/CSRF/path-traversal target. v4 covers prompt injection only. | Part 24: bind 127.0.0.1, token for LAN, Origin checks, `textContent`-only rendering, CSP, ID-based file access, OS keyring for secrets; T-23. |
| Y-10 | M | Compliance gaps: no per-source **rights classification** gating Auto/publish; no note on platform "reused/unoriginal content" policies; GPL implications of the "full" FFmpeg build; no provenance record; the cyan verified-style check defaulted **on**. | 15.4 default changed to `brand_check`; new 15.8–15.11 (rights_class, policy re-check at release, licence table, provenance sidecar); Part 22 publish rules. |
| Y-11 | M | Q&A pairing allows only a 2.0 s gap and skips only fillers; real debates have courtesies ("Thank you, Jake.") and applause between question and answer. | 7.4 step 2: 3.0 s tolerance, courtesy/address skip-list, reaction spans skipped. |
| Y-12 | M | Analytics loop fits "a transparent regression" on what is typically **tens of clips** → overfit, spurious "insights". Labeling protocol for precision@90 / recall@10 also unspecified (who rates, how many, what CI). | Part 23 (ridge + leave-one-out CV, N ≥ 60 gate, CIs); 17.5 labeling protocol with Wilson intervals and minimum sample sizes. |
| Y-13 | L | 0.4 says "only 3 inputs" but 18.1 lists 3 + several more; Part 18 milestones omit hardening/ops; no crash-recovery, sleep-prevention or disk guards for the "overnight batch" story. | 0.4/18.1 corrected; Part 25 (Reliability & Ops); 18.2 rewritten. |
| Y-14 | L | "Exact 16:9" for 1080×608 panels: 1080×607.5 is exact; 608 is within 0.08%. Harmless but the validator must not assert exactness. | Validator asserts `abs(w/h − 16/9) < 0.002`. |

## 1.5 Added in v5 (new capability)
Hybrid semantic stack with gates (Part 19) · **Receipts engine** (contradiction clips with visible "EARLIER" provenance) · evasion/deflection detector · crowd signals (YouTube most-replayed heatmap, timestamp mentions) and audience-reaction events (Part 20) · source hygiene (sponsor/intro/music filter) · **question chips** and **evidence cards** that fix missing context *without* lengthening the clip (Part 21) · verify-before-post claim gate · caption modes + opt-in emoji pops · NLE/OTIO/FCPXML/EDL export, publish pack, offline multilingual caption sidecars (Part 22) · learning loop from your own approvals (Part 23) · security (Part 24) · reliability/ops (Part 25) · **Monitor's Protocol** for the human supervising the builder agent (Part 26).

---

# PART 2 — COMPETITIVE POSITIONING (honest)

| Capability | Typical commercial clippers | This product (mechanism) | Status until measured |
|---|---|---|---|
| Debate-aware selection (Q→A, challenge→rebuttal, contradiction, concession) | generic "viral moments", loud/emotional peaks | Archetypes A1–A7 + debate graph + evidence quotes (Part 7) | claim only after bake-off |
| Clean in/out points | frequent mid-thought cuts | boundary rules with onset/decay + next-speaker guard (7.4) | measurable: T-08 |
| Active-speaker framing | face-centered, wrong face in cross-talk | AV-correlation + turn evidence + conservative WIDE (Part 10) | measurable: T-11 |
| Layout | single crop, basic split | PL-2: single / stacked 16:9 dual / wide-blur / manual, upscale budget | measurable: T-06/T-07 |
| Captions | template pop | reference-locked Hormozi + glow, slot solver vs faces, calibrated size, A/B-verified (Part 11) | measurable: T-13/T-16/T-17 |
| Branding | template overlay | pixel-deterministic chrome, bbox fidelity gate | measurable: T-01/T-02 |
| Integrity | none/opaque | integrity flags, fairness meter, headline fidelity, `edited` labels (7.9, 8, 15) | measurable: T-10 |
| Score transparency | single opaque number | component scores + evidence + calibration gate | measurable: T-09 |
| Cost/privacy | cloud, per-minute pricing | local-first, offline-capable | measurable |
| Prompt search ("find where X is challenged") | some | local BM25/embedding retrieval over debate graph (12.1) | to build |

## 2.2 Competitor snapshot — Opus Clip & Klap (checked 2026-10-04)
Sources: vendor pages and independent reviews found by web search (secondary; vendors change features often). **Re-verify every row before it is used in any claim**; "n/v" = not verified.
| Capability | Opus Clip | Klap | This product (v5) |
|---|---|---|---|
| Find moments by prompt / any content | "ClipAnything": multimodal (visual cues, audio sentiment, faces); prompt such as "every time we mention pricing" | AI topic detection | Prompt search v2 over the debate graph + embeddings (19.6); visual cues limited to face/mouth events + audience-reaction audio |
| Score | Virality 0–99 (reviews cite hook strength, emotional flow, perceived value, trend alignment); reviewers call it inconsistent | Virality score | Component score with evidence; **explicitly not a virality prediction** (7.8) |
| Reframe | "ReframeAnything" object/speaker tracking | "AI Reframe 2": multiple layouts incl. stacking split-screen interviews | PL-2 single / stacked / wide-blur / manual + AV-correlation (Part 10) |
| Captions | Animated templates; reviews cite 20+ languages | Reported 52 languages | Reference-locked Hormozi + glow; multilingual sidecars only after per-language measurement (22.3) |
| Dubbing | n/v | Reported 29 languages (Pro) | **Deliberately none** (21.7, 15.10) |
| B-roll | AI B-roll (a review calls it experimental) | B-roll integration | **No automatic B-roll** (misleading-imagery risk); manual user-supplied overlay only |
| Editing | Editor; filler/silence removal on paid tiers | Built-in editor; transcript editor | Review Studio transcript editing; silence-only tight-cut (12.4) |
| Publishing | Social scheduler | Reported 4-platform scheduling | Publish Pack; API publishers gated by platform audits (22.2) |
| Pro-NLE hand-off | XML export (Pro, per a review) | n/v | OTIO / FCPXML / EDL + SRT/VTT/ASS (22.1) |
| Teams | Seats on Pro (2 per a review) | n/v | Single-user local + LAN review (22.4) |
| Cost model | Subscription tiers by processing minutes (reviews: ≈ $15 Starter / $29 Pro per month) | Subscription (reviews: ≈ $14–$23+ per month on annual billing) | No per-minute fee; your hardware and time |
| Data location | Cloud | Cloud | Local-first |
| Reported weak spots | Slow on long videos; inconsistent score; B-roll unpolished | Manual selection still needed; support response complaints | — (ours are in 2.3) |

## 2.3 Where this product can win, where it will lose, and what v5 does about it
**Plausible wins (each still needs the bake-off to be claimed):** debate-specific selection (Q→A, challenge→rebuttal, contradiction) · receipts clips with provenance · context fixed by chips instead of padding · zero-surprise brand output (deterministic chrome) · integrity flags and fairness meter · name-accurate captions via glossary · cost and privacy · full manual override and inspectable reasons for every decision.
**Expected losses (do not market against these):** zero-setup ease · cloud speed · mobile apps · 50+ language captions and dubbing · turnkey scheduling · team collaboration · support.
**v5 closes what is closable without compromising principles:** NLE export, multilingual caption sidecars, publish pack, phone review (22.1–22.4). It *chooses not to match* dubbing, auto B-roll and virality prediction, and says why (21.7).

---

# PART 3 — PRODUCT DEFINITION

## 3.1 User stories
1. Paste a URL or drop a file → get 5–10 ranked debate clips with headlines → approve → get ready-to-post MP4s + metadata.
2. Drop a folder of long videos → unattended overnight batch → morning review queue.
3. Type "find where he dodges the question" → get candidates for that intent.
4. Open any clip, fix trim/headline/crop in a transcript-style editor, re-render in seconds.
5. Re-render all clips under a new brand preset.
6. Type "find the receipts" → get verbatim contradiction clips with an on-screen "EARLIER" provenance chip.
7. Review the overnight queue on a phone (swipe approve/reject), then export clips + NLE timelines + a publish plan.

## 3.2 Modes
| Mode | Behaviour |
|---|---|
| **Review-first** (default) | stop at *Awaiting review*; approve/trim/reject; render approved |
| **Auto** | auto-render only if `score ≥ auto_threshold (90)` **and** no integrity flag ≥ `review` **and** boundary/layout confidence ≥ thresholds |
| **Batch** | many sources queued; each follows its mode |
| **Watch-folder** | new file in `inbox/` → full pipeline |
| **Prompt** | candidate retrieval driven by a natural-language intent (12.1) |

## 3.3 Success metrics (all must be *measured*, results written to `reports/`)
precision@90 ≥ 0.70 · recall@10 (IoU≥0.5) ≥ 0.60 · 0 mid-word cuts · wrong-speaker ≤ 15% (easy) · face-in-safe-area ≥ 98% · ≤ 8 switches/min · chrome MAE ≤ 2.5 · caption center error ≤ 12 px · ≤ 3 manual steps per clip · peak RAM < 12 GB on a 60-min source · pan jitter ≤ 50% of the integer-crop baseline (T-24) · name-correction precision ≥ 0.98 (T-26) · each learned layer passes its gate or ships off (T-28) · 0 XSS/CSRF findings (T-23).

---

# PART 4 — ARCHITECTURE

## 4.1 Principles
One **shared core library**; CLI, watch-folder and Review Studio are thin shells over it (no second renderer). Pure-function stages with typed JSON artifacts, cached by content hash. Analysis (produces `framing.json`, `captions.ass`, `chrome.png`) is separate from rendering (consumes them).

## 4.2 Stack (pin versions in `requirements.lock`; verify wheels exist for the installed Python)
| Concern | Choice | Fallback |
|---|---|---|
| ASR + word timestamps | `faster-whisper` (int8 on CPU). Benchmark `large-v3-turbo`, `distil-large-v3` (English-only), `medium.en`, `small.en` for **real-time factor and word/name error on the labeled set**; choose by measurement. Guards: VAD pre-segmentation, repetition/hallucination detector, hotword/prompt priming from the glossary where supported | smaller model |
| Word alignment refinement | forced alignment (e.g., `whisperx` aligner or `ctc-forced-aligner`) if it improves onset error on the hand-verified sample | native Whisper word times |
| VAD | Silero VAD (bundled with faster-whisper) | WebRTC VAD |
| Diarization | **default: `sherpa-onnx` offline diarization** (pyannote-segmentation ONNX + speaker-embedding ONNX; CPU, no PyTorch, no token) `[ext-verified 2026-10-04]`; optional `pyannote.audio` 3.x (gated HF token). Choose by DER (T-27) | turn heuristics: gap ≥ 0.35 s + terminal + response cue; then AV mapping (Part 10) |
| Face detection / landmarks | MediaPipe Tasks (Face Detector, Face Landmarker w/ blendshapes), optional Pose Landmarker lite; models stored offline in `assets/models/` | OpenCV DNN face detector (mouth analysis then disabled → turn evidence only) |
| Text embeddings (diversity, prompt search) | TF-IDF + BM25 (always) ; optional small sentence-embedding model (offline) | BM25 only |
| Imaging / text | Pillow (2× supersample), NumPy, OpenCV | — |
| Render | FFmpeg (libx264, libass) | CPU encoder only until proven otherwise |
| Metadata/DB | SQLite (jobs, cache index, ledger), JSON artifacts on disk | — |
| API/UI | FastAPI + vanilla JS/HTML Review Studio (no build step) | CLI only |
| CLI | Typer (`py -m dc ...`) | argparse |
| Tests | pytest + golden files + synthetic video generator | — |
| Optional LLM | any provider via one adapter; strict JSON schema; word-index outputs; transcript = **untrusted data** | disabled |
| Downloader | `yt-dlp` (user supplies URL; see Part 15.1; pinned, explicit update — Part 24) | local files only |
| Semantic models (Part 19) | small ONNX/CTranslate2 embedding, NLI and QA-relevance models chosen by benchmark **and licence** | BM25 + lexicons (L0) |
| Audience-reaction events (20.3) | MediaPipe Audio Classifier (YAMNet-class) | skip the signal |
| Camera renderer (13.1b) | NumPy + OpenCV `warpAffine` → rawvideo pipe → FFmpeg | pure-FFmpeg crop for static segments |
| Interop (22.1) | `opentimelineio`, FCPXML + EDL writers | SRT/VTT/ASS only |
| Translation (22.3, optional) | CTranslate2 + permissively licensed MT model | off |
| Secrets (Part 24) | OS keyring (`keyring`) | env var outside the repo |

## 4.3 Repo layout
```
debate_clipper/
  assets/ fonts/ (Poppins-Regular/SemiBold/ExtraBold, Anton, NotoColorEmoji + licenses)  logo.png  wordmark.png  models/  sfx/ (CC0 only)
  config/ political_lens.json  lexicons/*.json  safe_zones.json  intents.json  glossary.json
  dc/ core/ (config, hashing, cache, ledger, jobs, errors)
      ingest/ transcribe/ audio/ signals/ graph/ semantic/ select/ hook/ layout/ framing/ captions/ polish/ render/ qa/ meta/ distribute/ security/ studio/ cli.py
  tests/ unit/ golden/ synth/
  work/<job_id>/     exports/<clip_id>/     reports/     inbox/
  DECISIONS.md  LEDGER.md  README.md
```

## 4.4 Windows rules
Argument lists only · UTF-8 everywhere (ASS written UTF-8) · long filter graphs via `-filter_complex_script file` · FFmpeg `cwd=work/<job>/` + relative paths · stable output names `<source_slug>_<clip_id>_<hash8>.mp4` · cancel kills the whole process tree (`taskkill /T` equivalent) and sets state `cancelled`.

## 4.5 `doctor` command (must pass before any job)
Checks: Python, FFmpeg libass/harfbuzz/x264, fonts load (no fallback), emoji glyph is not tofu, models present, write access, path-with-spaces test, free disk, config schema, safe-zone profile `verified_on` (warn if null), badge-mode warning, caption calibration cache, model licence table + hashes, yt-dlp pinned version/age, Studio bind address = 127.0.0.1, keyring available, VFR/60 fps probe sample, placeholder-asset banner.

---

# PART 5 — DATA CONTRACTS (schema_version on every file)

```
Word      {i, text, start, end, prob, speaker|null}
Sentence  {i, w0, w1, terminal: ".|?|!|none", speaker, complete: bool}
Turn      {i, speaker, start, end, s0, s1, wps, gap_before}
Edge      {type: answers|challenges|rebuts|interrupts|concedes|contradicts|clarifies, from, to, p, evidence:[{cue, w:[i..j]}]}
Candidate {id, source_id, start, end, duration, archetype, score, components{}, penalties[], structure[], boundary{}, integrity_flags[],
           hook{spoken, headline_options[]}, layout_hint, alt_boundaries[], edited: bool, provenance: local|llm}
Framing   {segments:[{t0,t1,mode,regions,confidence,reasons[],upscale_factor}], path:[{t,x,y,w,h}], debug{}}
RenderPlan{source, trim, framing_hash, chrome_hash, ass_hash, audio{}, output{}, config_hash, tool_versions}
Report    {status: passed|needs_review|failed, checks:[{name,value,threshold,evidence}], timings{}}
```
Every artifact stores its cache key. Re-rendering from a saved `RenderPlan` must reproduce identical layout and captions.

---

# PART 6 — PIPELINE (stage → artifact → cache key → gate → on failure)

| # | Stage | Artifact | Cache key | Gate | On failure |
|---|---|---|---|---|---|
| 1 | Ingest | `source.json` + file | source fingerprint (size+mtime+first/last MB hash) | streams present, duration>0 | stop; never overwrite |
| 2 | Audio extract | `audio_16k.wav` | source fp | duration ±0.05 s | retry once |
| 3 | Transcribe | `transcript.json` | fp+model+params+glossary | monotonic times; speech coverage ≥ 90% | smaller model |
| 4 | Shot + layout scan | `shots.json` | fp+params | ≥1 shot; per-shot layout label (single/split/side-by-side/graphic) with confidence | all `unknown` → conservative |
| 5 | Acoustics + diarization | `acoustics.json`, `turns.json` | fp+params | VAD coverage plausible | drop acoustic term |
| 6 | Debate graph + candidates | `candidates.json` | transcript key + scoring cfg | valid intervals, no dups | local path always works |
| 7 | Optional LLM rerank | `candidates_llm.json` | chunk hash+prompt ver | schema + index validity | discard, keep local |
| 8 | Review | `decisions.json` | candidate id + edits | persisted | — |
| 9 | Framing (approved only, +3 s margins) | `framing.json` | fp+interval+tracker ver | feasibility, upscale budget | WIDE + flag |
| 10 | Chrome/layout | `chrome.png`, `layout.json` | preset+text+asset hashes | validator invariants (9.1), fit | shorten/drop emoji |
| 11 | Captions | `captions.ass`, `captions_plan.json` | words+style+layout hash | geometry/timing (11.8) | shrink/slot/box; flag |
| 12 | Polish plan | `polish.json` (punch-ins, tightening, nameplates, audio chain) | cand+cfg | within upscale/integrity limits | skip polish item |
| 13 | Render | `clip.mp4` | RenderPlan hash | exit 0 + progress complete | CPU encoder; ≤1 retry |
| 14 | QA | `export_report.json` | output hash | Part 13.3 | `needs_review`/`failed` |
| 15 | Export + metadata | `exports/<clip_id>/…` | — | status `passed` | — |

A job is complete only when stage 14 = `passed` (or user explicitly accepts `needs_review`).
**Invalidation:** changing headline/palette/caption style re-runs 10–14 only; changing a boundary re-runs 9–14 for that clip only.
**v5 sub-stages:** 3b glossary + hallucination guard · 5b reaction events · 5c crowd signals + source hygiene (Part 20) · 6b semantic L1 behind its gate (Part 19) · 10b question chips / evidence cards (Part 21) · 13 renderer = sub-pixel camera (13.1b) · 15b export bundle + provenance (22.1, 15.11).

---

# PART 7 — DEBATE HOOK & EXCHANGE SELECTION ENGINE

## 7.1 Archetypes
| Code | Archetype | Core signals | Length | Hook form | Layout pref |
|---|---|---|---|---|---|
| A1 | Direct takedown (challenge→rebuttal) | challenge cue + stance opposition + rebuttal by other speaker | 30–55 s | Attribution/Question | Single→Dual on cross-talk |
| A2 | Gotcha / contradiction | "you said/earlier you said" + earlier claim in same source | 35–60 s | Question | Single (`edited` if multi-segment) |
| A3 | Clean answer (Q→A) | question + substantive answer, high clarity | 20–45 s | Question | Single |
| A4 | Concession/admission | "you're right/fair point/I was wrong" | 15–35 s | Attribution | Single |
| A5 | Escalation | ≥4 speaker switches/6 s, interruptions, rate spike | 30–60 s | Question/Stance | Dual |
| A6 | Evasion | "answer the question/that's not what I asked" + non-responsive reply | 25–50 s | Question | Dual or Single |
| A7 | Mic-drop statement | high-clarity standalone claim, strong ending | 15–35 s | Stance (verified) | Single |
Default target 25–55 s; longer only if each added second adds context or conflict (up to the project ceiling; beyond that use the **series splitter**, 12.10).

## 7.2 Transcript → debate graph
- Build `Word → Sentence → Turn → DebateGraph`. All labels **probabilistic with evidence**; never assert a role without evidence; never invent words.
- **Speaker attribution order:** diarization → transcript tags → turn-gap heuristic (gap ≥ 0.35 s + sentence terminal + lexical response cue). Uncertain ⇒ `speaker=unknown`, lower context/boundary confidence, never show names.
- **Sentence complete** = terminal punctuation or pause ≥ 0.45 s **and** last token not a dangling function word (`and, but, because, so, that, which, if, the, a, to, of, with`) **and** next word starts a new sentence/turn. Pause+dangling test is primary; ASR punctuation only supports.

## 7.3 Cue lexicons (`config/lexicons/*.json`, English seeds; each hit stores word indexes; extend per language only with measured precision/recall)
| Family | Seeds |
|---|---|
| Question | who/what/when/where/why/how/do you/did you/will you/can you/are you/would you (`?` supports, never decides) |
| Challenge | "that's not true", "that's false", "you're wrong", "with all due respect", "let me finish", "actually", "no, no", "hold on" |
| Evasion | "answer the question", "that's not what I asked", "you didn't answer", "yes or no" |
| Concession | "you're right", "fair point", "I'll give you that", "I agree", "I was wrong", "I'll concede" |
| Contradiction | "but you said", "earlier you said", "that contradicts", "which is it", "so you're saying" |
| Checkable claim | numbers, percentages, years, million/billion, "studies show", "the data", named statutes |
| Reframing/quoting (integrity) | "they say", "my opponent claims", "some people argue", "you're telling me", "let's say" |

## 7.4 Narrative-unit detection
1. **Anchors (over-generate):** question turn; challenge/evasion; concession; contradiction; speaker-switch burst (≥3 in 6 s); strong claim (checkable + clear); topic boundary; prompt-retrieval hit.
2. **Q&A pairing:** for question turn Q by S, answer onset = first non-filler sentence by another speaker within 3.0 s (skip fillers `well, look, so, yeah, um, I mean, okay`, courtesy/address openers such as `thank you, <name>` / `<name>,` / `Mr.|Madam <name>` / `great question`, and applause/laughter spans). Answer end = earliest of turn end / follow-up question / topic shift / rebuttal onset from S. No substantive answer within 8 s ⇒ `unanswered` (valid A6).
3. **Arc building** (smallest unit satisfying the archetype): A3 `[Q][A]` (+follow-up only if it raises conflict within cap); A1 `[claim][challenge][rebuttal]` (claim shortened to its last complete sentence if >12 s); A2 `[earlier claim ≤12 s]+[exchange]` ⇒ `edited=true`; A4/A7 single turn + minimum setup.
4. **Context sufficiency test** — pass requires ALL: (a) no unresolved leading anaphora (`that/this/it/he/she/they/those/as I said` in first 6 words) unless the antecedent noun phrase is earlier in the clip; (b) claim's topic entity appears within first 12 s; (c) if first turn is an answer, the question is inside the clip or restated in the answer's first sentence. Fail ⇒ extend back to question start (cap +20 s) or flag `needs_context`. **Never ship a context-poor clip silently.**
5. Refine boundaries (7.5) → re-score → hard rejects → cluster/select (7.9).

## 7.5 Boundary engine
**Start (ordered, stop at first that applies):**
1. Starts at the onset of the first word of the question/claim sentence the viewer needs.
2. Mid-sentence start → move back to sentence start unless that adds > 6 s unrelated content; else flag `mid_sentence_start` (penalty).
3. **Onset refinement:** search the audio onset (VAD/energy rising edge) in `[word_start−0.25, word_start+0.10]` → `start = onset − 0.08 s` (Whisper times can be off ≥100 ms).
4. **Lead-in trim:** first spoken word begins 0.08–0.20 s after clip start.
5. Never start inside a word; reject if previous word overlaps `start` by > 0.04 s (unless interruption).

**End:** (1) end of last word of last complete sentence; (2) tail = clamp(decay_time, 0.25, 0.60 s), decay_time = time for short-term loudness to fall 12 LU below word peak (fallback 0.35 s); (3) **guard:** `end ≤ next_word_start − 0.08` and `≤ next_speaker_onset − 0.05` — never include the next speaker's first syllable (unless intended interruption); (4) incomplete last sentence → extend up to +6 s else flag `truncated_ending`; (5) 30 ms audio fades (no fades that shorten audible speech).
**Fallback buffers** (only when rules can't decide): pre-roll 0.30 s, post-roll 0.40 s, bounded by guards. 2–5 s buffers are context-expansion tools only.
**Duration:** soft 20–60 s; hard min 8 s; hard max = project ceiling; penalize >15% dead air and >2.0 s continuous silence.

## 7.6 Acoustic rules (propose/refine/corroborate; never rank alone)
Signals: momentary loudness (400 ms), VAD, pauses, words/sec per turn, overlaps, switch rate. Per-speaker median+MAD baselines `z=(x−median)/(1.4826·MAD)`. Emphasis event: `z_loud ≥ 1.5` for ≥ 0.6 s **and** (`z_rate ≥ 0.5` or preceded by pause ≥ 0.4 s). Gate: ignore if VAD prob < 0.7 or ASR word prob < 0.5 (applause/music/crowd). Cap: ≤ 5% of score; acoustic-only candidates rejected. Laughter/applause = context markers only.

## 7.7 Semantic tension (each 0–1 with evidence)
Stance opposition (consecutive turns share ≥2 content lemmas and polarity flips) · challenge density per 10 s · interruption density (gaps <0.20 s/overlaps per 10 s) · escalation (rate z rise over 3 turns) · unresolved/evasion · stakes (entities, numbers, legal/policy terms) · reversal beat. **Beat rate:** a retention-oriented clip has a new beat every 8–12 s; `beat_rate < 0.4/10 s` ⇒ down-weight.

## 7.8 Scoring (absolute, explainable, calibratable)
| Dimension | Weight | Sub-features |
|---|---:|---|
| Narrative completeness | 18 | setup, payoff, archetype match, boundaries ok, sufficiency passed |
| Conflict / disagreement | 15 | stance opposition, challenge density, interruptions, escalation |
| Hook strength | 14 | first-3 s hook type, curiosity gap, immediacy (first word ≤ 0.2 s), no filler opener |
| Argument clarity | 13 | rate 2.0–3.5 w/s, filler ratio, mean ASR conf, sentence completeness |
| Rebuttal / response | 10 | response present, relevance, completeness |
| Ending quality | 9 | last sentence complete, terminal cue (conclusion/punchline/concession/open question), tail 0.25–0.6 s |
| Context independence | 9 | unresolved refs (inverse), entity introduced, question included **or shown via question chip (21.1, −2)** |
| Acoustic & audience reaction | 5 | gated emphasis events + reaction events (20.3) |
| Crowd signal | 7 | most-replayed heatmap / timestamp mentions (Part 20); dropped and weights renormalised when unavailable |
`score = (100 / Σ available w) · Σ w·s − penalties`, clip 0–100 (weights sum to 100 when every signal is available; initial priors, calibrate). **Penalties** (cap −40, each logged): missing context −12 · repeated vs higher-ranked −10 · mid-sentence start −8 · truncated ending −10 · dead air>15% −6 · low ASR conf (<0.6) −8 · integrity `review` −6 · hook mismatch −5.
**Hard rejects:** mid-word start/end · duration outside hard limits · mean ASR conf < 0.45 · integrity `block_auto_approve` unless manually reviewed · timestamps inconsistent.
**Meaning of "90+":** absolute scale; on the golden set ≥ 70% of candidates scoring ≥ 90 must be rated usable (as-is/trivial trim) by a human, else recalibrate and log. Tiers: 90–100 priority · 80–89 strong · 70–79 possible · <70 hidden. UI states once, plainly: *a score ranks clips; it does not predict virality.*

## 7.9 Diversity, integrity flags
- Cluster by time IoU > 0.3 or TF-IDF/embedding sim > 0.8; keep best, store others as `alt_boundaries` (keep a longer variant only if it adds a new beat or resolves a context warning). **MMR** `λ·score − (1−λ)·max_sim`, λ=0.7. ≤ 2 clips per 10 min of source per topic chapter unless raised.
- **Integrity flags** (severity info/review/block_auto_approve): I-1 quoted/reframed speech (speaker says "they claim…" — clip may attribute the claim to the wrong person); I-2 cut removes a rebuttal or qualifier; I-3 multi-segment edit (`edited`); I-4 unverified speaker identity in a headline; I-5 sarcasm/hypothetical markers ("let's say", "imagine") in the headline-bearing sentence; I-6 numbers/names in headline missing from transcript; **I-7** checkable claim in the clip not yet marked `claim_checked` (review; blocks Auto); **I-8** `rights_class` unknown (blocks Auto and publish); **I-9** overlap with a sponsor/intro/music span ≤ 10% (20.4); **I-10** election-related content (15.5).
- **Fairness / balance meter (new):** for two-sided exchanges compute each side's share of speaking time and whether the opposing position's response is included. If one side has < 15% share while the clip's headline attributes a claim to the other side's opponent, or a rebuttal that existed in the source within 15 s was cut, raise I-2 `review`.

## 7.10 Optional model layer
Use only for: stance confirmation, rebuttal-relevance ranking, headline options, top-N rerank (N ≤ 20). Return **word-index ranges**, not seconds. Transcript text is untrusted data (prompt-injection safe: model output validated against schema + index bounds; any instruction-like line in the transcript must not change output — test T-10). Cached, budgeted. The local path must produce the full candidate list with no model.

---

# PART 8 — HEADLINE ENGINE

- **Two layers:** *spoken hook* (actual first line, never edited) and *editorial headline* (card text, visually distinct from quotes, never presented as something a speaker said).
- **Forms & templates** (each ≤ 52 chars target, hard ≤ 78 with font shrink; ≤ 1 trailing emoji; no ALL-CAPS; no claims/numbers/names absent from the clip):
  - Stance: `Why We Need to <X>` — only if stance check confirms the dominant speaker advocates it **and** `stance_headlines: true` (else auto-fallback to Question).
  - Question: `Should <X> Be <Y>?` · `Is <X> Actually Working?`
  - Attribution-neutral: `The Case for <X>` · Attribution: `<Side> Answers: <Q>`
- **Fidelity check:** named entities and numbers in the headline must appear in the clip transcript (fuzzy ≥ 0.9); failing options dropped; if none pass → neutral topic question from the top noun phrase.
- Generate 3 options, auto-pick the highest passing, show all 3 in Review Studio. Scoring: immediate clarity, curiosity, relevance, concision, accuracy, context independence, **fit** (measured by the §9.4 fitter, not char count).
- **Cold open** (moving the punchline to the start): off by default; only when enabled, labeled `edited`, followed by the original sequence; disabled in Auto.
- **Emoji:** 1 relevant trailing emoji from a curated map (🎓 education, ⚖️ law, 💰 economy, 🏛️ government, 🗳️ elections, 🛂 immigration, 🔫 guns, 🩺 health) — default none for sensitive topics (war, deaths, abuse).

---

# PART 9 — VISUAL LAYOUT & BRANDING ENGINE (preset `PL-2`, measured from the user's reference)

## 9.1 Coordinates and validator invariants
Canvas 1080×1920, origin top-left, all widths/heights even, `setsar=1` on every layer. **Block the render if any fails:**
1. `feed.y + feed.h + bottom_white.h = 1920` (524 + 1216 + 180).
2. Header (y138–296) and hook zone (y320–505) don't intersect; hook zone ends before feed (505 < 524).
3. Every measured text box inside its band (hook: x 140–940, y ≥ 320).
4. Caption footprint (fill + stroke + glow halo) inside the feed layer and the selected safe-zone profile.
5. Uniform scale on every layer (`sx==sy` within 0.1%).
6. No read outside the source frame after clamping.

## 9.2 Composition
| Region | x | y | w | h | Content |
|---|---:|---:|---:|---:|---|
| Top reserved | 0 | 0 | 1080 | 138 | white |
| Header | 108 | 138 | ≈620 | 158 | logo + wordmark + handle + badge |
| Hook zone | 140 | 320 | 800 | 185 | bottom-anchored text, last baseline y=495 |
| Gap | 0 | 505 | 1080 | 19 | white |
| **Feed** | 0 | **524** | 1080 | **1216** | video + captions (burned in first) |
| Bottom white | 0 | 1740 | 1080 | 180 | white (optional credit/progress, 12.9) |
**Layer order (back→front):** white canvas → feed layer (captions already burned in) overlaid at (0,524) → chrome PNG 1080×524 overlaid at (0,0) → QA. Isolation by construction: no caption pixel can reach rows 0–523; chrome is last so nothing covers it.

## 9.3 Header (measured)
| Element | Spec | Reference |
|---|---|---|
| Logo | circle Ø158 at (108,138), 2× supersampled circular mask | x108–266, y138–296 |
| Wordmark | **image asset**, left x=276, cap-top y=170, cap-height 64, ink ≈390 px; "POLITICAL" `#3F3F3F`, "LENS" `#EC0000`; fallback live Anton two-colour fitted to the same box | x276–665, y170–234 |
| Handle | `@_political_lens`, Poppins Regular, `#7F7F7F`, ink-left x=303, ink-top y=247, ink width **278** | x303–581, y247–280 |
| Badge | circle Ø50 at (677,176), `#4DD0E2`; modes: **`brand_check` (v5 default)** = same circle/colour/position with a non-check brand glyph; `platform_style` = white check stroke 0.11·Ø (only if the account is truly verified, 15.4); `none` | x677–727, y176–226 |
Left-aligned group; handle indented 27 px under wordmark; badge 12 px right of wordmark, vertically centered on it; keep right 160 px free; if the badge hits the right limit drop it and log. Text is measured with the real font and fitted.

## 9.4 Hook text fitter
Poppins SemiBold `#0A0A0A`, centered x=540, **bottom-anchored** (last baseline y=495 for 1/2/3 lines). Size 50→40 px, line pitch 1.04×px, ≤3 lines, max width 800, greedy wrap with emoji width reserved on the last line only. Emoji: ≤1, trailing, color font `embedded_color=True` at the bitmap strike size (109) then resized to 1.05×px with 0.25×px gap; `tofu` check → drop emoji + log. Capacity: ≈26–28 chars/line at 50 px. Output the measured text box to the manifest.

## 9.5 Feed crop mathematics & upscale budget
`a = 1080/1216 = 0.8882`; `Hc_max = min(Hs, Ws/a)`; `Wc = a·Hc`; `s = 1216/Hc`; scale first then crop at integer offsets; clamp to source; never stretch.
| Source | Max single crop | `s` |
|---|---|---:|
| 3840×2160 | 1918×2160 | 0.563 |
| 1920×1080 | 959×1080 | 1.126 |
| 1280×720 | 639×720 | 1.689 |
| 854×480 | 426×480 | 2.533 |
**Policy:** `s ≤ 1.5` normal · `1.5 < s ≤ 2.0` allowed, log `soft_upscale` (Lanczos, no extra sharpening) · `s > 2.0` → prefer Stacked or Wide-blur; if single is forced manually, flag. **Punch-ins (12.3) count toward `s`.** Always store `upscale_factor`.

## 9.6 Layout modes
- **A Single:** crop above, solver §10.6.
- **B Stacked dual:** two panels **1080×608** (16:9 within 0.2%; validator asserts `abs(w/h − 16/9) < 0.002`). Top canvas y524–1131, bottom y1132–1739, 4 px divider centered y=1132 (white 60% or lime 70%). Per-panel `Hc_i = hf_i/φ_panel` (φ≈0.22–0.28); from 1080p a full-res 1080×608 crop gives s=1.0.
- **C Wide conservative:** C1 wider single crop; **C2 fit-width** = 1080×608 foreground centered over a blurred fill (304 px blur bands). Default when speaker/layout/tracking uncertain.
- **D Manual:** user rectangles in `framing.json`; never silently replaced.
- Side-by-side/split sources: detect seam first; crop each half to its panel.

## 9.7 Safe zones (data, not constants; `config/safe_zones.json`)
| Profile | Bottom | Right | Left | Top (info) | Use |
|---|---:|---:|---:|---:|---|
| `balanced` (default) | 440 | 140 | 60 | 150 | typical organic posting |
| `strict` | 576 | 192 | 60 | 288 | one export for all platforms |
| `ad_template` | 672 | 192 | 48 | 288 | ad figures |
Store `source_url`, `verified_on`, `notes`; `verified_on: null` until measured (post a test clip with a safe-zone grid on each platform; screenshot). PL-2 consequences: caption anchor y=1136 is compliant in all profiles; keep faces/hands above y≈1480; header starts at y=138 (12 px inside the balanced top band) ⇒ `top_zone_overlap` = **info**.

## 9.8 Exclusion regions
`E_face` = face box expanded 0.20·wf sides, 0.25·hf above, 0.15·hf below, +24 px. Upper-body prior (containment only, not caption blocking): face ±1.3·wf horizontally, −0.6·hf above, +2.8·hf below. `E_hand` only when pose landmarks exist, benchmark acceptably, wrist visibility ≥ 0.5: square 0.9·hf around wrists above hip line. Caption **stroke box = hard constraint** vs `E_face`; **glow halo (≈45 px beyond fill) = soft** (warn if it covers > 15% of the face box → reduce `outer_alpha` for that segment). Divider line always excluded. Reports must state which exclusion level was active.

## 9.9 Reference fidelity gate
Every header/hook element bbox within **10 px** of the reference (kit result: ≤3 px logo/wordmark/handle/badge, hook ≤9 px). Upgrade to SSIM ≥ 0.98 (text masked) once the user supplies one clean 1080×1920 export frame.

---

# PART 10 — SPEAKER TRACKING & REFRAMING

## 10.1 Principles
Face boxes say **where**, audio says **that** someone speaks, neither says **who** — you need both plus turn structure. Weak evidence ⇒ stable and wide (C2) or hold current framing. Analysis outputs `framing.json`; preview and render both consume it.

## 10.2 Proxy and cadence
Analyze **only approved/top-N intervals (+3 s)**; shot detection runs on the whole source (cheap FFmpeg scene filter). Decode once to proxy: width 640 (960 if faces small), **6 fps** (tunable 5–10); audio once to 16 kHz mono. Face detect every proxy frame (6 fps); **landmark/mouth stage at 15 fps on tracked face crops (192–256 px), boxes interpolated between detections (Y-1)**; full re-scan every 1.0 s to recover missed faces. Min face height at proxy scale **48 px** for mouth analysis, else `av_unreliable` ⇒ turn evidence only or conservative mode. Record RAM/CPU per stage.

## 10.3 Components
Face Detector (required) · Face Landmarker blendshapes for mouth activity (`jawOpen`, `mouthFunnel`, `mouthPucker`, lip gap; recommended if it benchmarks) · Pose Landmarker lite (optional) · Silero/WebRTC VAD (required). Use the maintained MediaPipe **Tasks API**; keep model files offline in `assets/models/`. **ASD model slot (optional):** a lightweight audio-visual active-speaker network (e.g., Light-ASD/TalkNet-class) may replace the correlation score only if its licence permits your use and it beats the baseline on T-11 at acceptable CPU cost; otherwise do not ship it.

## 10.4 Active-speaker evidence model
```
s(t)  speech presence: inside any word interval ±50 ms or VAD; 0 after pause > 250 ms
m_i(t) mouth energy: std of jawOpen (or lip gap/face height) over trailing **0.8 s (≥ 12 samples at 15 fps)** ÷ track's own 95th percentile
r_i   max over lag ∈[−200,+200] ms of Pearson(m_i, s) in a 3 s window
e_turn_i  1 if the diarized/transcript speaker now active is mapped to track i (only if mapping verified)
h_i   1 if i is current speaker;   q_i = det_conf × min(1, face_h/48)
score_i = 2.0·z(r_i) + 2.5·e_turn_i·[mapping_verified] + 0.6·h_i + 0.5·q_i
P_i = softmax(score_i) over tracks with valid landmarks;  margin = P_max − P_second
```
If Σs(t) in the window < 20% (silence) **hold**; if max r_i < 0.2 for all ⇒ `uncertain`. Speaker→track mapping per shot: highest AV correlation with margin ≥ 0.15 over runner-up and ≥ 3 s overlapping speech; re-verify after each cut. Names only from user labels (12.5).

## 10.5 Layout state machine
States: `SINGLE(i)` · `DUAL` · `WIDE` (C1/C2) · `MANUAL`. Shot cuts reset the tracker and enter `WIDE` until re-acquired.
| Transition | Condition |
|---|---|
| any→SINGLE(i) | margin ≥ 0.30 sustained ≥ 0.6 s **and** feasible |
| SINGLE(i)→SINGLE(j) | P_j − P_i ≥ 0.25 for ≥ 0.6 s **and** dwell ≥ 1.5 s |
| interruption bypass | P_j ≥ 0.80 for ≥ 0.4 s and i silent ≥ 0.3 s ⇒ dwell ≥ 0.8 s suffices |
| SINGLE→WIDE | margin < 0.15 for ≥ 1.2 s, or tracks lost > 1.0 s |
| WIDE→SINGLE | margin ≥ 0.30 for ≥ 1.0 s |
| SINGLE/WIDE→DUAL | crosstalk ≥ 0.60 for ≥ 1.0 s, both faces present, `s_dual ≤ 2.0` |
| DUAL→SINGLE/WIDE | crosstalk < 0.35 for ≥ 2.0 s |
| limits | DUAL min dwell 3 s; ≤ 1 mode change per 6 s |
`crosstalk = max(min(1, switches_in_6s/4), both_mouths_active_fraction_in_3s/0.40)`.
**Feasibility (PL-2):** `φ_single = hf·s/1216`; prefer SINGLE when `s_single ≤ 1.5` and `φ_single ≥ 0.10`; `φ_dual = hf·s_dual/608`; prefer DUAL when single fails and `s_dual ≤ 1.5`; else WIDE. Archetype hints bias, never override feasibility. A1/A5/A6 prefer DUAL when two faces present (each panel s≈1.0 from 1080p).

## 10.6 Single-speaker crop solver (caption-aware)
```
hf = face h;  φ_target = 0.20;  Hc_pref = hf/φ_target
Hc = clamp(Hc_pref, 1216/1.5 ≈ 811, Hc_max);  Wc = a·Hc;  s = 1216/Hc
x0 = face_cx − Wc/2 (+ look-room: shift 3% of Wc toward the open side)
y0 = face_cy − 0.33·Hc          (headroom ≥ 5% of Hc)
clamp to [0,Ws−Wc]×[0,Hs−Hc]; round only after scaling
```
Containment priority: head (hard) > face-exclusion margins > shoulders > wrists (soft). If clamping puts the head within 4% of a feed edge ⇒ WIDE or DUAL. **When Hc ≈ Hs (1080p), y0=0 and vertical face position is fixed by the source ⇒ captions adapt to the face (slot solver), not the crop to captions.** Caption-aware check: require `E_face.bottom ≤ caption_top − 16 px` for the preferred slot else pick another slot (11.5).

## 10.7 Smoothing, dead zone, transitions
`α = 1 − exp(−Δt/τ)`; `p_t = p_{t−1} + α(target − p_{t−1})`; `τ_follow = 0.35 s` (confident), `τ_slow = 0.80 s` (margin < 0.30); dead zone 0.04·Wc horizontal, 0.05·Hc vertical; velocity cap 0.25·Wc/s; freeze path during non-speech > 0.4 s; interpolate analysis path (6–10 Hz) to source fps at render. **Speaker change in same shot:** `d = |x_new−x_cur|/Wc`; `d ≤ 0.6` ⇒ eased pan of `clamp(0.25+0.5d, 0.25, 0.60) s`; `d > 0.6` or mode change ⇒ hard cut (or ≤2-frame dissolve). Source shot cut ⇒ cut, reset tracker.
**Dual details:** enter only via the transition; never switch for interjections < 1.0 s; stable assignment (left→top unless swapped); if one participant lost > 1.0 s hold last crop ≤ 1.5 s then WIDE; optional accent bar on the active panel. **Worked clearance (replaces v3's "≈400 px"):** with φ=0.28, faces centered at 33% of each panel, top-face exclusion bottom ≈ canvas y859, bottom-face exclusion top ≈ y1181 ⇒ ≈320 px clear band around the divider `[assumed; solver verifies at runtime]`.

## 10.8 Conservative behaviour, logging, evaluation
Fall back to WIDE (C2 preferred) when: no tracks, low margin, `av_unreliable` on all tracks, layout classifier unknown, upscale budget exceeded. `reason_code` per segment: `LOW_MARGIN, TRACK_LOST, NO_LANDMARKS, UPSCALE_BUDGET, SHOT_CUT, MANUAL_LOCK`, shown in Review Studio as "why this crop". `--debug-overlay` draws face boxes, track IDs, posterior bars, mode/reason, crop rect, caption band, exclusions, safe-zone. **Targets (to be measured on labeled 60 s samples):** face inside safe area ≥ 98%, ≤ 8 switches/min outside interruption bursts, wrong-speaker ≤ 15% on easy cases; report % time in WIDE, jitter, mean/max face-in-safe-area.

---

# PART 11 — KINETIC CAPTIONS (Hormozi "Viral Shorts" + glow, reference-locked)

## 11.1 Style identity & fonts (SIL OFL, bundled with licences; `doctor` confirms they load — no silent fallback)
ALL CAPS · heavy geometric sans · white base · one accent-colored active word · thick dark outline · drop shadow · center-screen · 1–3 words at a time · quick pop per new word · glow on active word.
| Role | Font | Size | Colour |
|---|---|---|---|
| Caption | Poppins ExtraBold, ALL CAPS | cap-height **44 px** | base `#FFFFFF`, active **`#B4F83D`** |
| Hook | Poppins SemiBold | 50→40 px | `#0A0A0A` |
| Handle | Poppins Regular | fit 278 px ink | `#7F7F7F` |
| Wordmark fallback | Anton | fit 390 px ink | `#3F3F3F`/`#EC0000` |
| Non-Latin fallback | Noto family | — | verify libass renders before claiming multilingual |
**Calibration [verified in kit]:** reference "RIGHT" = 172×44 px; Poppins ExtraBold natural width is wider ⇒ ASS `\fscx 92`. If the real CapCut font is supplied, set `font_family`, re-run `calibrate_caption()`.

## 11.2 Palettes
P1 (default, measured) `#B4F83D` lime · P2 `#FFE600` yellow · P3 emphasis only `#FF3B30` red (negations/numbers, ≤1 per group, never the active word). **ASS colours are BGR:** `#B4F83D→&H3DF8B4&`, `#FFE600→&H00E6FF&`; unit-test the converter. Dual mode may use P1/P2 per speaker **only when the speaker→track mapping is verified**.

## 11.3 Glow (3 layers per event; only the active word glows, other words transparent in glow layers so layout is identical)
| Layer | Content | Params (initial) |
|---|---|---|
| 0 outer halo | active word, accent colour | `\bord18 \blur16`, alpha `&H68&`, colour `#B4F83D` |
| 1 inner glow | same, tighter | `\bord9 \blur6`, alpha `&H30&` |
| 2 text | full group; active `#B4F83D`, others white | outline **5 px** black, shadow 2 px, no blur |
Measured halo reach ≈ **45 px** beyond the fill. Subtler: raise `outer_alpha` toward `&H90&`; stronger: toward `&H40&`. Benchmark render time before raising radii.

## 11.4 libass size calibration (required, cached by `hash(font file, style)`)
`\fs` ≠ pixel size. Render a test word on black, threshold pure white (stroke/shadow removed), solve `fs` for cap 44 px and `\fscx` for 172 px "RIGHT" width. **[verified]** Poppins ExtraBold: `\fs 110` + `\fscx 92` → 172×44. `\an5` centers the line box ⇒ cap-center lands ≈6.5 px high ⇒ **dy = +6.5 px** to hit canvas y=1136. Re-run on any font/size/style change.

## 11.5 ASS spec, grouping, timing, pop, position
- `PlayResX 1080 · PlayResY 1216` (feed-local: canvas y − 524), `ScaledBorderAndShadow: yes`, `WrapStyle: 2`, our own line breaks. Each event: `\an5\pos(540, 612+dy)` (612 = 1136−524). One `Dialogue` per word state × 3 layers.
- **Grouping:** 1–3 words, max 16 chars, tokens ≤ 3 chars merge with the next word, break on pauses > 0.6 s (hide captions during pauses > 0.6 s); ALL CAPS; punctuation stripped (fidelity check normalizes); never break article+noun, preposition+object, name parts, number+unit; keep contractions intact; keep entities/numbers together. **[assumed]** 1-word vs 3-word grouping needs 2–3 more reference frames.
- **Active interval:** start−0.03 s → next word start−0.03 s; last word released ≤ 0.12 s after end; overlap ≤ 80 ms; repair non-monotonic times by clamping + log.
- **Pop:** 82% → **108%** in 90 ms → 100% in 80 ms; applied to every event of a 1-word group, only the **first** event of multi-word groups (prevents neighbour jitter). If neighbours visibly shift, color-only.
- **Emphasis (optional):** numbers, negations (`no/not/never`), lexicon entities get P3 when not active; ≤1 per group.
- **Anchor:** default centre **(540,1136)** (feed centre + 4 px). **Slot ladder** on collision: `1136, 1096, 1176, 1056, 1216, 1016, 1256 …` (±40 px), within `[feed_top+120, bottom_max − 45 halo]`, hysteresis ≥ 1.5 s, ≤ 3 slots/clip, change only at group boundaries. No free slot → shrink in 2 px steps to a 36 px cap-height floor → 60% black rounded plate (r 14, pad 18; also when mean luma in band > 200 or the divider crosses the box) → flag `CAPTION_REVIEW`. Max width 800 px (x 140–940) measured with real font × `\fscx`. A hand briefly (<0.8 s) in the band: keep stable; ≥ 0.8 s: move at the next group boundary. Dual mode: `x_c = 540`, default slot at the divider (≈1132–1136) when ≥ the clearance from §10.7, else lower part of upper panel.

## 11.6 Fast-glow alternative (benchmark at M5; choose by measurement, log in DECISIONS.md)
Render captions-only (no glow) to a transparent/black layer → `split` → `gblur` copy colored accent → `screen`/`overlay` onto the feed before chrome. Pros: one blur per frame instead of per event. Accept only if the A/B halo reach stays 40–50 px and the colour error vs the ASS-glow render is small.

## 11.7 Word-timing accuracy
Prefer forced-aligned times. Hand-verify ≥ 100 words; require median onset error ≤ 100 ms, p95 ≤ 250 ms. If worse, enable a global caption lead of up to −80 ms (log) rather than shifting individual words.

## 11.8 Caption validation (deterministic)
Text fidelity (0 missing/0 invented words) · timing (above) · geometry (box inside slot limits; 0 overflow) · **A/B presence** on **lossless** renders (≥ 20 event midpoints; changed pixels only inside the predicted box; first changed row ≥ 524) · font actually loaded · active colour present (≥ 800 px within ΔRGB < 30 of the accent) · no group < 0.30 s · density ≤ 3.0 words/s · glow reach ≥ 30 px each side (add as an automated check) · outline/fill contrast ≥ 4.5:1.

---

# PART 12 — WORLD-CLASS FEATURE PACK (new in v4)

Each feature has a config switch, a QA hook, and is **off or conservative by default** where it could alter meaning or the reference look.

## 12.1 Prompt-based clip search ("find where he dodges the question") — upgraded in 19.6
BM25 + optional embedding retrieval over sentences/turns, constrained by debate-graph edges (e.g., intent "dodges" ⇒ boost `unanswered`/Evasion lexicon; "contradiction" ⇒ A2; "concedes" ⇒ A4). Output the normal `Candidate` objects (same scoring, boundaries, integrity checks). CLI: `py -m dc find --job <id> --q "<intent>" --top 5`. Show the matched evidence words in Review Studio.

## 12.2 Hook A/B variants at near-zero cost
Because chrome is overlaid last, render the **feed layer once** to a high-quality intermediate (`libx264 -crf 12 -preset veryfast` or FFV1) and composite N chrome variants (different headlines/forms) from it. Store as `variants/`. Flag the extra generation loss: final outputs must come from one composite encode of the intermediate, and QA still runs on each.

## 12.3 Beat-synced punch-ins (SINGLE mode only)
At tension beats (7.7) apply a slow 1.00→1.06 zoom over 0.6 s (ease-out), hold, return at the next speaker change/cut. Counts toward `s ≤ 1.5` (else disabled for that clip); never during DUAL/WIDE; max 1 per 6 s; the caption slot solver must re-check collisions at peak zoom (face grows).

## 12.4 Silence tightening ("tight cut")
Remove **silence only** (never words): pauses > 1.2 s inside a single speaker's turn compressed to 0.35 s; total compression ≤ 15% of duration; 30 ms audio crossfades; visual jump masked by a +4% alternating punch-in at the cut. Each cut stored in `edits[]`, clip marked `edited=true`, and I-2 check confirms no rebuttal/qualifier is removed. Default **on** only for pauses > 1.2 s; fully off in the "faithful" preset.

## 12.5 Speaker nameplates (user-labeled only)
One-time labeling: the user names a diarization cluster / face track in Review Studio; stored locally. Nameplate chip (Poppins SemiBold 30 px, white text on 65% black rounded plate) appears 1.2 s at top-left of the feed (canvas y≈552) when that speaker first speaks in the clip; never over a face exclusion; never shown for `unknown`. No face-recognition models are used; labeling is manual and local.

## 12.6 Fairness / balance meter
See 7.9. Surface it in Review Studio as two bars (speaking-time share) with a plain-language note; I-2 raised when the opposing response was cut.

## 12.7 Burned-in text avoidance
OCR/edge-density on proxy frames flags sources with hard-coded captions or lower-thirds (`source_has_captions`). Policy: prefer a crop that excludes the band; else move our caption slot off it; else suppress our captions only if the user enables `trust_source_captions`. Log as a QA note.

## 12.8 Cover-frame + metadata pack
- **Cover frame:** among frames in the first 3 s choose max(face sharpness (Laplacian var) × eyes-open × mouth-not-mid-syllable × ≥ φ face fraction); export `cover.jpg` (1080×1920) with the chrome.
- **Metadata pack** per clip and platform: 3 title options (≤ 60 chars YouTube Shorts; no clickbait claims absent from the clip), description with source link + start timestamp + speaker attribution, 5–8 hashtags (topic-derived, no banned/misleading tags), **pinned-comment engagement question** (neutral, two-sided: "Which side made the stronger case?"), chapter. Written to `metadata.json`.

## 12.9 Bottom-band extras (both **off by default** to keep the reference look)
- `source_credit`: one line, Poppins Regular 28 px `#7F7F7F`, centered y≈1790: "Source: <channel/event> · full video in bio".
- `progress_bar`: 6 px bar at y=1748–1754 in `#EC0000` over `#E6E8EB`, drawn in the chrome-over layer so it can't enter the feed. QA bottom-white check is masked over the bar rows.

## 12.10 Series splitter ("Part 1/2")
If a high-value exchange > 75 s: split at the strongest natural pause + beat so each part is self-contained (re-run sufficiency test per part), add `PART 1/2` as a small suffix on the headline's last line only if the fitter has room, else in metadata only. Cap at 3 parts.

## 12.11 Audio polish chain
`loudnorm` two-pass to −14 LUFS (true peak ≤ −1.0 dBTP) · optional conservative denoise (`afftdn` low strength; skip if speech-to-noise is already fine) · 30 ms fades · optional music bed **only from user-supplied licensed files**, sidechain-ducked, default off · bundled SFX (CC0 only) for nameplate/transition, default off. Never cut speech with a gate/compressor that changes perceived meaning.

## 12.12 Analytics feedback loop
Import platform stats CSV per clip (views, avg % watched, swipe-away@3 s, shares). Fit per Part 23.4 (ridge regression, leave-one-out CV, N ≥ 60 clips) of outcome vs the score components; show which components correlate; propose weight changes in `proposals/`; apply only after the user approves + a `DECISIONS.md` entry. UI wording: correlation on *your* channel, not a virality prediction.

## 12.13 Multi-brand presets
`config/presets/<brand>.json` can override chrome, palette, fonts, safe zone. PL-2 is the default preset; adding a second channel must need zero code changes.

## 12.14 Review Studio (local web app, FastAPI + vanilla JS)
Candidate list sorted by score with component bars and evidence quotes · **transcript editing** (click a word to move in/out; boundary guard warnings live) · 3 headline options with fit preview · palette/layout/crop overrides with "why this crop" reason codes · fairness bars · speaker labeling · proxy preview (540×960, fast preset, same RenderPlan) · approve/reject/alt-boundary · one-click render + export. All state persisted in `decisions.json`; overrides always beat automation.

---

# PART 13 — RENDER & QA

## 13.1 Render graph (single mode; run with cwd = `work/<job_id>/`, relative paths, long graphs via `-filter_complex_script`)
```
[0:v]trim=start=S:end=E,setpts=PTS-STARTPTS,
     scale=W1:H1:flags=lanczos,                         # W1=Ws*s, H1=1216 (s may include punch-in)
     crop=1080:1216:x='<path_x(t)>':y='<path_y(t)>',setsar=1,
     subtitles=captions.ass:fontsdir=../assets/fonts[feed];
color=c=white:s=1080x1920:r=FPS:d=DUR[bg];
[bg][feed]overlay=0:524[c];
[c][1:v]overlay=0:0:format=auto,format=yuv420p[v]       # -i chrome.png (looped)
# audio: atrim,asetpts,<polish chain>,loudnorm(2-pass),afade in/out 30 ms
```
Output: `-c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -movflags +faststart`, High profile, AAC 160–192 kbps, **source fps preserved up to `fps_cap` (default 30; VFR normalised — 13.1c)**. Dual mode: two cropped panels (1080×608) `vstack`/`overlay` with the divider drawn before captions. WIDE C2: blurred scaled-to-fill copy under a fit-width foreground. **v5 decision: any segment whose camera path moves uses the sub-pixel renderer (13.1b); the expression graph above is used only for constant-layout segments.** `-ss` before `-i` for long sources with re-encode for frame accuracy; verify first/last frames. Temp files only under `work/<job_id>/`.

### 13.1b Camera renderer — sub-pixel (v5 decision, replaces "decide by benchmark")
**Problem (Y-2):** `crop` offsets are integers; slow pans judder and scale-then-crop resamples twice. **Design:**
1. **Path → per-frame rects.** `framing.json` (6–10 Hz) is resampled to per-frame float rectangles `(x, y, w, h)` in *source* coordinates using the frame-rate-independent smoothing of 10.7. Punch-ins (12.3) are just a smaller `w,h`.
2. **Decode process.** FFmpeg decodes the trimmed segment to raw frames on stdout, pre-cropped (integer) to the path's bounding box + 16 px margin to limit pipe bandwidth.
3. **Warp.** NumPy/OpenCV `warpAffine` (Lanczos4; cubic if the benchmark shows no visible difference) maps each source rect directly to 1080×1216 — **one resample, sub-pixel exact**. DUAL: two warps to 1080×608 + 4 px divider. WIDE-C2: blurred fill + fit-width foreground. Assert no read outside the source (validator 9.1-6).
4. **Encode process.** A second FFmpeg reads the composed feed frames from stdin plus the original audio (trimmed), applies `subtitles` (captions burned on the feed layer), overlays at (0,524) over white, then the chrome PNG, loudnorm/fades, libx264.
5. **Plumbing.** Both pipes drained by dedicated threads (no deadlock); bounded queue (≤ `queue_frames`); timestamps come from frame index ÷ CFR fps, never wall-clock; cancel kills both process trees; stderr to logs.
6. **Static segments** (path variance < `static_threshold_px`) use the pure-FFmpeg expression graph of 13.1 (faster).
7. **Colour (Y-3).** Convert explicitly in both directions: decode with the source's own matrix/range; encode with `out_color_matrix=bt709`, limited range, and tag the output `-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv`. Test: a colour-bars source through the whole path keeps patch ΔE ≤ 3 (add to T-14).
8. **Measurement.** `bench` records frames/s for pure-FFmpeg vs sub-pixel on the same clip; T-24 proves the smoothness gain. If sub-pixel is slower than real time on the reference machine, reduce `queue_frames` overhead, use cubic, or process only moving segments this way — do not fall back to integer crops for moving paths.

### 13.1c Frame-rate and audio normalisation (Y-4)
Probe `r_frame_rate`, `avg_frame_rate` and packet-pts deltas for the clip window. If variable-frame-rate (pts-delta coefficient of variation > 1% or avg ≠ r): normalise to CFR with `fps=<target>` where target = nearest of {24, 25, 30, 50, 60} to the median rate, then apply `fps_cap` (default **30**; set 60 to keep 60 fps — roughly doubles CPU render time). Audio resampled to 48 kHz. Log the decision in `RenderPlan`. T-25.

## 13.2 Latency design
Analyze only what renders · decode once · cache by content · one heavy ML stage + one render at a time (cap FFmpeg threads while analysis runs; measure before raising) · proxy preview with the same RenderPlan · `libx264` baseline, hardware encoders only after trial encodes prove better speed at equal quality · never print a speed number that wasn't measured.

## 13.3 Automated QA suite (all deterministic where possible)
| Check | Rule |
|---|---|
| File | exists, size>0, probe ok, seek at 25/50/75% ok |
| Streams/Res/SAR/FPS/Codec | video+audio (if source had audio) · exactly 1080×1920, SAR 1:1 · fps = min(source, `fps_cap`) after VFR normalisation (13.1c) · H.264+AAC |
| Duration | within ±0.1 s (or ±2 frames) of plan |
| A/V sync | audio cross-correlation offset ≤ 40 ms vs source segment |
| Loudness | integrated within ±1.5 LU of target; true peak ≤ −1.0 dBTP |
| Clipping/silence | no ≥3 consecutive 0 dBFS samples; `silencedetect=n=-50dB:d=1.0` flag (compare with source); first word ≥ 0.08 s after start; last word ends ≥ 0.25 s before end unless interrupted |
| **Chrome integrity** | rows 0–523 equal `chrome.png`, MAE ≤ 2.5/255 at **≥ 12** frames (first, last, ~every 2 s, every mode change). Kit baseline 0.40 |
| **Bottom white** | rows **1744–1919** ≥ 250 (4 px guard mandatory (≥ measured bleed + 1 px): codec bleed on rows 1740–1741, cause `[assumed]` — see Y-5); masked over optional credit/progress rows |
| **Caption isolation (lossless A/B)** | same frame with and without `subtitles`, lossless; first changed row ≥ 524 (kit: 1067–1068) |
| Caption centre | footprint centre within 12 px (y) / 30 px (x, single) of (540,1136) unless the slot solver moved it (then equals the logged slot) |
| Active colour | ≥ 800 px within ΔRGB<30 of the accent (kit: 3,857) |
| Safe area | footprint x within [100,980]; bottom ≤ `bottom_max` |
| **Glow presence** | footprint exceeds fill ≥ 30 px each side (kit: 45) — **new automated check** |
| Face-edge | detector on ≥ 10 sampled output frames: no face box within 4 px of the feed edge or cut |
| Black/frozen | `blackdetect=d=0.1:pic_th=0.98`, `freezedetect=n=-60dB:d=1.0`, flagged unless in source at same time |
| Stutter | presented timestamps match cadence; drops/dups within tolerance |
| Narrative/integrity | boundary rules satisfied; integrity flags recorded; headline fidelity + stance check; `edited` label present on multi-segment/tightened clips |
| **Provenance** | `edits.json` lists every cut/insert; `provenance.json` has source hash, output decoded-frame hash, tool versions; `augmented`/`edited` flags consistent with edits |
| **Chip/card fidelity** | every character of a question chip / evidence card is a substring of the normalised transcript (clip or cited span); timing within ±120 ms of the word onset; no pixels over `E_face` |
| **Sub-pixel smoothness** | median rendered frame-to-frame displacement of the tracked face matches the planned path within 0.5 px (phase-correlation on output) |
| **Bleed profile** | measured chrome/feed boundary bleed (rows 0–523 and 1740+) vs distance at the chosen CRF; guard ≥ measured extent + 1 px |
**Why lossless A/B:** two lossy encodes flagged 1.15% pixels as "caption" from encoder noise alone.
**Outcome:** `passed` · `needs_review` (any warning) · `failed` (any hard check); each entry has check name, value, threshold, evidence pointer. No silent success; ≤ 1 retry with a changed parameter, logged.

## 13.4 Records & handoff
Per export keep: source fingerprint, candidate + edits, `RenderPlan`, `framing.json`, `captions.ass`, `chrome.png`, config hash, git commit, tool versions, stage runtimes, `export_report.json`, `metadata.json`, `cover.jpg`. Optional OpenTimelineIO export later.

---

# PART 14 — CLI & JOB SPEC

```
py -m dc doctor
py -m dc run   --source "<url|path>" --preset political_lens --top 8 --mode review
py -m dc run   --source "<path>" --preset political_lens --mode auto --auto-threshold 90
py -m dc find  --job <id> --q "<intent>" --top 5
py -m dc render --job <id> --candidate c_0012 [--variants 3]
py -m dc validate --output "<mp4>" --plan "<plan.json>"
py -m dc watch --inbox "<folder>" --mode review
py -m dc studio            # Review Studio
py -m dc bench             # records speeds/RAM
py -m dc bakeoff ...       # Part 17.4
```
Job spec (validated before run):
```json
{"job_id":"auto","source":{"path":"D:\\...\\debate.mp4","url":null},
 "candidate":{"id":"c_0012","start":1523.84,"end":1568.12,"edits":[]},
 "preset":"political_lens",
 "headline":{"text":"Should the Department of Education Be Abolished? 🎓","form":"question"},
 "layout":{"mode":"auto","manual_regions":null,"safe_zone_profile":"balanced"},
 "captions":{"style":"hormozi_glow","palette":"P1","uppercase":true,"pop":true,"speaker_colors":false},
 "polish":{"punch_in":false,"tight_cut":false,"nameplates":false,"progress_bar":false,"source_credit":false},
 "audio":{"loudnorm":true,"target_lufs":-14},
 "output":{"profile":"shorts_1080x1920","fps":"source_capped","crf":18,"preset":"medium"}}
```
Validation: times inside transcript/video; paths exist/writable; headline passes fit + fidelity; safe-zone known; no output collision.

---

# PART 15 — COMPLIANCE, INTEGRITY & PLATFORM RISK (build these in; do not skip)

1. **Source rights.** The tool processes sources the user chooses. Each export stores `source_url`, channel/event, timestamp. The default metadata pack includes source attribution and a link to the full video. README states plainly: clipping third-party video can infringe copyright or breach platform terms even with attribution; fair-use/fair-dealing depends on jurisdiction and facts; the user is responsible for permission or a defensible transformative use. The app never claims legal clearance. Add a per-source `rights_note` field the user can fill (license, permission, own content).
2. **Faithful editing.** No word removal, no reordering, no cold open unless `edited` is labeled; headline never attributes words to a speaker that they didn't say; I-1…I-6 flags and the fairness meter exist to catch misleading cuts.
3. **Platform labeling.** If any synthetic or heavily altered media is added (AI voice/dubbing/face edits — none are in scope by default), the export report flags `needs_platform_disclosure`. Tight-cut/punch-in clips set `edited=true` in metadata.
4. **Badge.** A cyan check next to a handle reads to viewers as a *platform-verified* mark. Unless the account actually is verified, that misleads the audience — and a political channel's whole asset is trust. v5 therefore defaults to `badge.mode: brand_check`: same circle, colour and position (so all geometry tests are unchanged) with a **non-check brand glyph** (e.g., a small lens/aperture mark). `platform_style` (the check) is available as one config line **only if the account is verified**; `none` removes the badge. `doctor` prints a banner whenever `platform_style` is active.
5. **Political-content caution.** Election-related content (voting procedure, dates, results claims) gets integrity flag `review` and is excluded from Auto; headlines for such clips must be Question form. No fabricated numbers/names (I-6). Respect each platform's current election/misinformation policies — re-check at release time.
6. **Privacy.** No face-recognition identification; speaker names only from manual user labels; all processing local by default; optional LLM layer sends **transcript text only** (never video), user-toggled, with the key stored outside the repo.
7. **Safety on bad input.** Never execute anything from transcript text; shell calls use argument lists; downloaded filenames sanitized.
8. **Rights classification.** Every source has `rights_class ∈ {own, permission, public_domain_verified, licensed, unknown}` plus `rights_note`. `unknown` ⇒ Auto disabled and publish blocked until the user sets a class (flag I-8). The app never asserts that something is public domain; `public_domain_verified` is a user attestation with a link.
9. **Platform policy re-check.** Platforms have policies on reused/unoriginal content, election and political content, synthetic media and branded content. The README lists them as *to re-read at release time* (not summarised from memory). Transformation features that add real context (chips, receipts, source credit, commentary) are encouraged; nothing here guarantees monetisation or reach.
10. **Synthetic media.** No AI dubbing, voice cloning, face/lip edits or generated imagery of real people (21.7). If a user-supplied overlay or music is added, the report notes it; `needs_platform_disclosure` applies per item 3.
11. **Provenance sidecar.** Each export writes `provenance.json`: source URL/hash, rights class, every cut (`edits.json`), tool versions, config hash, output decoded-frame hash, and the "watch the full exchange" link with start timestamp. Optional: embed a C2PA manifest only if a real signing certificate is configured (never ship test-cert signatures as if genuine).
12. **Licences.** Fonts (SIL OFL), models (see `MODELS.md`), and the FFmpeg build: a "full" GPL build is fine for personal use; **distributing** this tool or its binaries triggers GPL/LGPL obligations — README states this and links the licences.
13. **Security.** See Part 24 (binding, XSS/CSRF, secrets, dependency pinning).

---

# PART 16 — PERFORMANCE PLAN

`bench` records per stage: wall time, CPU%, peak RAM, with command, media ID, settings. Record: ASR real-time factor per model/compute type; candidate discovery s per source-hour; framing s per 45 s clip; proxy preview s per clip; final render RTF per profile; fast-glow vs 3-layer glow; peak RAM on a 60-min source (< 12 GB objective). Manual steps per clip in Review-first (objective ≤ 3). Tuning order: (1) cache hits, (2) ASR model/precision, (3) proxy fps/size, (4) glow method, (5) FFmpeg preset/threads, (6) optional hardware encoder trial. Never raise parallelism without a measurement.

---

# PART 17 — TESTS & ACCEPTANCE

## 17.1 Test data
Synthetic video generator (known faces as colored boxes + sine "speech" with scripted mouth signals) for geometry/state-machine tests; golden transcripts with hand labels; **a labeled real-footage set (user supplies ≥ 5 debate videos, ≥ 20 labeled 60 s framing samples, ≥ 100 hand-verified words)**.

## 17.2 Acceptance matrix
| ID | Test | Pass condition |
|---|---|---|
| T-01 | Layout validator PL-2 | 524+1216+180=1920; no overlaps |
| T-02 | Element bbox fidelity vs reference | each ≤ 10 px (kit: ≤3; hook ≤9) |
| T-03 | Headline fit, 30 headlines (short/long/emoji) | ≤3 lines, ≥40 px, 0 overflow |
| T-04 | ASS colour converter | `#B4F83D→&H3DF8B4&`, `#FFE600→&H00E6FF&` |
| T-05 | Caption slot solver, synthetic faces | 0 stroke-box intersections; inside safe profile |
| T-06 | Crop solver clamps, 1000 random faces | no read outside source; uniform scale |
| T-07 | Upscale policy | 720p single = `soft_upscale` (1.689); 480p rerouted; punch-in counted |
| T-08 | Boundary rules on golden transcripts | 0 mid-word; 0 truncated final word; next-speaker onset never included |
| T-09 | Candidate gate | recall@10 ≥ 0.6; 0 duplicates; precision@90 ≥ 0.70 |
| T-10 | Prompt-injection transcript line | output unchanged; schema holds |
| T-11 | Framing on labeled 60 s samples | Part 10.8 targets |
| T-12 | End-to-end on path with spaces | `passed`, chrome integrity OK |
| T-13 | A/B caption differencing | presence at ≥ 20 events; 0 outside-box diffs |
| T-14 | QA negative tests | shifted crop, caption in header, missing glow, wrong colour order, missing audio, overflow — each flagged; plus colour-bars patch ΔE ≤ 3 (13.1b-7) and bleed profile measured |
| T-15 | Cancel during render | no orphan FFmpeg; state `cancelled` |
| T-16 | Caption calibration | "RIGHT" 172×44 ± 3; centre (540,1136) ± 6 |
| T-17 | Glow | reach 40–50 px; 0 glow pixels outside feed |
| T-18 | Real-footage render (M3) | real trim + camera-path crop + real audio + loudnorm → `passed` |
| T-19 | Fairness meter | synthetic one-sided cut raises I-2 |
| T-20 | Tight-cut | silence-only removal; 0 words removed; ≤15% compression; I-2 clean |
| T-21 | Prompt search | known-intent set (including **paraphrased** queries, 19.6) returns the labeled clip in top 5 for ≥ 70% of queries |
| T-22 | Emoji | 🎓 renders non-tofu on Windows; fallback drops emoji + logs |
| T-23 | Security (Part 24) | XSS payloads in transcript/title/comment/filename inert; cross-origin and token-less POST → 403; not reachable off-host without `--lan`; traversal IDs → 400 |
| T-24 | Sub-pixel smoothness | synthetic high-contrast edge video, pan 0.3 px/frame: rendered jitter (std of frame-to-frame displacement via phase correlation) ≤ 50% of the integer-crop baseline and ≤ 0.15 px `[assumed]` |
| T-25 | VFR / 60 fps / 25 fps | output CFR = min(normalised source, `fps_cap`); A/V offset ≤ 40 ms at 60 s; frame count within ±2 of plan; no duplicate bursts |
| T-26 | Name fidelity | glossary correction on ≥ 100 labeled name occurrences: name-error rate drops; **replacement precision ≥ 0.98** (no wrong substitutions on non-names) |
| T-27 | Diarization bake | DER (0.25 s collar) on ≥ 10 labeled 5-min excerpts for sherpa-onnx vs pyannote; default = lower median DER at acceptable RAM/RTF; report both |
| T-28 | Semantic gate (19.3) | L1 vs L0 and L2 vs L1: bootstrap 95% CI of gain excludes 0, mid-thought cuts not higher, else disabled and logged |
| T-29 | Question chip | text is an exact substring; ≤ 90 chars; starts 0–2.5 s; zero overlap with `E_face`/caption band; A/B differencing shows chip pixels only inside the feed |
| T-30 | Evidence card | characters ⊂ transcript; timing ±120 ms; position collision-free |
| T-31 | Null-safe signals | with heatmap absent and comments off, ranking equals the renormalised-weight baseline; no author names/ids in any artifact (grep test) |
| T-32 | NLE export | OTIO parses with `opentimelineio`, durations equal plan ±1 frame; FCPXML validates; EDL timecodes correct at 25/30 fps |
| T-33 | Publish dry-run | refused when flag ≥ review, `claim_checked` missing or `rights_class` unknown; default privacy `private`; API stub receives private; no secrets in logs |
| T-34 | Multilingual captions | non-Latin and RTL samples render without tofu (pixel check vs `.notdef`), correct order; `machine_translated` label present |
| T-35 | Receipts | planted same-speaker contradiction found; planted qualifier within 30 s blocks or forces inclusion; cross-speaker pair rejected; clip carries chip, `edited=true`, never Auto |
| T-36 | Crash recovery | kill the process mid-render and mid-ASR: resume completes, no partial file in `exports/`, deterministic artifacts hash-identical |

## 17.3 Regression protocol
Golden frames for chrome + caption footprint; any change to fonts/config re-runs calibration and T-01/02/16/17.

## 17.4 Bake-off (the only source of "better than" claims)
10 diverse debate sources (2-person, panel, street Q&A, hearing; 720p/1080p/4K; clean/noisy). Run this tool, Opus Clip and Klap on each with comparable settings (user supplies exports from the commercial tools). Blind-rate (≥ 3 raters, randomized order) per clip: clean start/end, context sufficiency, correct speaker framing, caption legibility/collision, brand consistency, "would post as-is". Report mean ± spread per criterion, counts of mid-thought cuts, wrong-speaker seconds, caption-on-face seconds, minutes of human fix time per clip. Publish `reports/bakeoff.md`. Claims are limited to criteria where this tool wins with the sample size stated.

## 17.5 Labeling protocol (makes T-09, T-11, T-28 measurable)
- **Golden set:** ≥ 5 diverse sources; ≥ 100 rated candidates. **Two raters** (the user plus one other person) rate each on 3 levels: usable as-is / usable with trivial trim / not usable. Report Cohen's κ; if κ < 0.4 the rubric is unclear — fix the rubric before trusting any number.
- **Recall:** before seeing system output, each rater marks the clips they would post from each source (Studio Label mode, 23.5). Recall@10 uses IoU ≥ 0.5 against those marks.
- **Precision@90:** report the point estimate with a **Wilson 95% CI**. If fewer than 40 candidates score ≥ 90 across the set, the estimate is "insufficient" — report precision@top-k per source instead and do not claim the gate.
- **Framing samples:** ≥ 20 labeled 60 s windows with per-second "who is speaking" and "is the face inside the safe area".
- **Words:** ≥ 100 hand-timed words for the onset-error check (11.7) and ≥ 100 name occurrences for T-26.
- **Bake-off statistics:** paired comparisons per source with bootstrap 95% CIs; criteria and sample sizes are fixed before the run (`reports/bakeoff_plan.md`).

---

# PART 18 — BUILD ORDER (milestones with Definition of Done)

## 18.1 Inputs to request from the user — 3 required, plus optional extras (build with placeholders meanwhile)
1. Clean **logo PNG** and **wordmark PNG/SVG** (transparent). Kit's `assets/logo.png` is a crop of an annotated reference — placeholder quality only.
2. **2–3 more caption frames** with multi-word moments (confirms 1-word vs 3-word grouping and the true font).
3. **Badge decision** (`brand_check` default · `platform_style` only if the account is verified · `none`). Also request: one clean un-annotated 1080×1920 export frame (enables SSIM gate) and the ≥ 5 labeled debate videos (17.1) with a `rights_class` per video, a starter `glossary.json` of recurring names, and a second rater for 17.5.

## 18.2 Milestones (v5)
| M | Deliverable | DoD (evidence required) |
|---|---|---|
| M0 | Repo, config loader + schema, extended `doctor`, ledger, `MODELS.md` licence table, security baseline (127.0.0.1 bind, escaping helper, subprocess wrapper, keyring), unit-test CI | `doctor` green on a path with spaces; T-23 skeleton runs |
| M1 | Chrome builder + layout validator + bbox fidelity gate | T-01/02/03/22 pass (V1–V2) |
| M2 | Caption engine: grouping, 3-layer glow, calibration, slot solver (synthetic faces), colour converter | T-04/05/16/17 pass |
| M3 | **Real render pipeline** (trim, camera path, captions, chrome, audio chain) + QA suite + **sub-pixel renderer + colour pipeline + VFR/fps cap** | T-12/13/14/18/24/25 pass on real footage (V3) |
| M4 | Ingest + ASR (VAD, hallucination guard, glossary) + diarization (sherpa-onnx default, pyannote optional) + alignment + audio features + reaction events + source hygiene | word-onset check (≥ 100 words); T-26/27 |
| M5 | Debate graph + L0 candidates + boundaries + scoring + diversity + integrity flags; crowd signals; **L1 semantic stack behind its gate**; fast-glow benchmark | T-08/09/10/19/28/31 (golden); glow decision logged |
| M6 | Headline engine (fidelity/stance), hook variants, question chips, evidence cards | T-03/29/30 |
| M7 | Framing: shots/layout scan → conservative WIDE → tracking (15 fps mouth stage) → AV association → state machine → camera director → dual panels | T-06/07/11 |
| M8 | Polish pack (punch-in, tight-cut, nameplates, burned-in-text avoidance, cover, metadata, series splitter, bottom-band extras) + receipts + caption modes + NLE export + multilingual sidecars | T-20/32/34/35 + unit tests |
| M9 | Review Studio (transcript editing, Label mode, swipe/LAN review, verify-before-post) + Auto/Batch/Watch + prompt search v2 + Publish Pack (dry-run) | T-21/33; ≤ 3 manual steps/clip measured |
| M10 | `bench`, learning loop, multi-brand, ops hardening (Part 25), README, bake-off | T-36; `reports/bench.md`, `reports/bakeoff.md`; LEDGER shows V3+ for every shipped feature |
**Order rationale:** deterministic, high-visibility pieces first (M1–M3) so the brand look is locked and provable; heavy ML (M4–M7) after the render path is proven; polish and studio last. v5: the sub-pixel renderer and colour pipeline sit in M3 because every later feature inherits them; the semantic stack (M5) is gated so it cannot degrade the proven L0 path.

---

> Parts 19–26 are v5 additions. They are binding and are referenced by the milestones in 18.2.

# PART 19 — SEMANTIC INTELLIGENCE STACK (v5)

## 19.1 Why
v4's local selection is cue lexicons plus shared-lemma stance. It misses paraphrase ("that's simply not what the record shows" contains no seed cue) and cannot judge whether an answer actually addresses its question. Commercial clippers lean on learned models. This product's rule is *no claim without measurement*, so each learned layer must **earn** its place on the golden set.

## 19.2 Cascade
| Layer | Role | Runs on | Budget |
|---|---|---|---|
| **L0** | Lexicons + debate graph + acoustic/reaction anchors → **over-generate** candidates (high recall) | whole transcript | seconds |
| **L1** | Small local models re-score semantic features: (a) sentence embeddings; (b) NLI cross-encoder → entailment / contradiction between claim and rebuttal (stance opposition); (c) question↔answer relevance cross-encoder → answered / deflected / unanswered; (d) dialogue-act head (question, challenge, concession, evasion, claim, backchannel) = logistic regression on embeddings, seeded from lexicons, retrained from Studio labels (Part 23) | L0 windows only (≈ top 60 candidates per source-hour) | ≤ minutes per source-hour on CPU |
| **L2** | Optional LLM (local llama.cpp/Ollama or cloud via one adapter): rerank top-N ≤ 20, headline options, claim extraction. Strict JSON, **word-index outputs**, transcript = untrusted data (T-10) | top-N | token-budgeted, cached |
| **L3** | Human, Review Studio | — | — |
Use CPU-friendly small models (ONNX or CTranslate2). Pick specific models by benchmark and **licence**; record name, version, licence, hash, size, RTF in `assets/models/MODELS.md`. Prefer Apache-2.0/MIT/BSD; do not bundle non-commercial weights for a monetised channel.

## 19.3 Gate rule (non-negotiable)
L1 is enabled by default only if, on the golden set, it improves recall@10 **or** precision@90 over L0-only with the 95% bootstrap CI of the difference excluding 0, **and** does not increase mid-thought cuts or wrong-context clips. Same test for L2 over L1. Otherwise it ships **disabled**, and the result is logged in `DECISIONS.md`. Never lower a threshold to pass the gate.

## 19.4 Evasion / deflection detector
Features: low similarity between the question and the first substantive answer sentence (τ calibrated) · deflection markers ("the real issue is", "what people don't ask", "let me turn that around") · asker repeats the question or says "yes or no" · answer topic drift (embedding distance to the question rises) within 8 s. Output `answered | deflected | unanswered` with evidence word indices. Thresholds are `[assumed]` until measured.

## 19.5 Receipts engine (upgrade of archetype A2)
1. Index assertion-type sentences per speaker over the **whole source** (not only the current window).
2. Candidate pair (earlier claim C1, later claim C2): same speaker (diarization-verified, or user-labeled), embedding similarity ≥ τ_s, NLI contradiction ≥ τ_c, time gap ≥ 60 s (closer than that it is the same exchange, handled by A1/A6).
3. Clip structure: `[C1 ≤ 12 s, ending on a complete sentence] → visible chip "EARLIER · mm:ss" for 1.5 s → [the exchange or C2]`. Everything shown is verbatim and in source order; the only removed material is the gap, which the chip discloses. `edited=true`, flag I-3, `receipt.json` stores both source spans, their hashes and the gap length so Studio can open both in context.
4. Hard blocks: pair spans different speakers (unless identity verified by the user); either claim carries I-1 (quoted/reframed speech) or I-5 (hypothetical); the speaker qualifies/retracts C1 within 30 s ("what I meant was…") → include the qualifier or drop the pair (I-2). Receipts **never run in Auto**.

## 19.6 Prompt search v2 (extends 12.1)
`config/intents.json` maps intent names to predicates over graph / L1 / audio / crowd: `dodges` → deflected|unanswered; `gotcha`/`contradiction` → receipts; `concedes` → A4; `numbers` → checkable-claim density; `heated` → escalation + interruptions; `crowd_reacts` → reaction events; `funny` → laughter events. Free text → (1) nearest-intent classification by embedding against exemplar phrases; (2) BM25 + embedding retrieval for topical words ("student loans"). Results are ordinary Candidates (same boundaries, scoring, integrity). T-21 now includes paraphrased queries.

---

# PART 20 — CROWD, REACTION & SOURCE-HYGIENE SIGNALS (v5)

All signals are **optional, capped, and null-safe**: if a signal is unavailable its weight is dropped and the remaining weights are renormalised (`scale = 100 / Σ available weights`), so the pipeline works identically offline (T-31).

## 20.1 Most-replayed heatmap
`yt-dlp` exposes a `heatmap` list (segments with `start_time`, `end_time`, `value` 0–1) for YouTube videos that have enough viewing data; it is absent for new or low-traffic videos `[ext-verified 2026-10-04]`. Feature `crowd_replay` = mean heat inside the candidate, expressed as a percentile of the source's own distribution; weight 7. Heat percentile ≥ 90 also acts as an **anchor** for L0 over-generation. It never creates or promotes a candidate by itself. Benefit is `[assumed]` until measured on the golden set.

## 20.2 Timestamp mentions (off by default)
With explicit opt-in (`--comments N`), fetch up to N comments, extract `mm:ss`/`h:mm:ss` strings, histogram in 15 s bins → `crowd_mentions` (feeds the same weight as 20.1, averaged). **Store only bin counts**; discard comment text and author identifiers. Respect platform terms and rate limits; any failure → null.

## 20.3 Audience-reaction events
An audio-event classifier (MediaPipe Audio Classifier with a YAMNet-class model, or an ONNX equivalent; verify the label map and skip classes it lacks) over ~1 Hz windows yields applause / laughter / cheering / jeering events with confidence ≥ 0.5 (calibrate). `reaction_after` = event onset within 0–2.0 s after a sentence end → boosts A7/A1/A4 features (inside the 5-point acoustic/reaction weight). **Ending policy:** by default end before the reaction swell; `keep_reaction_s` (0–1.5) lets the reaction be part of the payoff (e.g., laughter after a punchline). Reactions never decide boundaries inside speech.

## 20.4 Source hygiene
Detect sponsor reads, intro/outro bumpers, music-only spans, ad breaks and long dead air (chapters, "sponsored by"-type lexicon, music class, speech-density) → `non_content` spans. Candidates overlapping > 10% are rejected; overlap ≤ 10% raises I-9.

## 20.5 Source metadata ingestion
Title, description, chapters, upload date, channel, licence field (if present) → `source.json.meta`. Uses: (1) seed `glossary.json` with names/places (ASR priming and post-correction, 4.2); (2) `event` string for the source credit; (3) rights hint for `rights_class` (15.8); (4) speaker-name **suggestions** shown in Studio — never auto-applied (I-4).

---

# PART 21 — SHORTS-CRAFT PACK v2 (v5)

Each item has a config switch, a QA hook, and a conservative default.

## 21.1 Question chip — context without padding
When the sufficiency test (7.4-4c) fails because the clip starts on an answer, v4 extends back up to 20 s. v5 first tries a **chip**: the question text, verbatim, shown for 2.5 s from t=0 on the plate style of the nameplate (Poppins SemiBold 30 px, white on 65% black rounded plate), top-left of the feed, label "QUESTION". Rules: ≤ 90 characters, shortened only by dropping **whole leading clauses** (never rewording); text must be an exact substring of the normalised transcript (T-29); placed by the same slot solver as captions (never over `E_face`, never in the caption band); only when the question was spoken by an identifiable other speaker. Scoring: context counts as passed with a −2 penalty (prefer natural context when it is cheap). Metadata `augmented=true` (nothing removed, so not `edited`).

## 21.2 Evidence cards
For a checkable claim (number, percentage, currency, year) **in the speaker's own words**: a card with exactly that figure ("$1.2 TRILLION") for 1.8 s starting at the word onset, Poppins ExtraBold on a dark plate with an accent underline, positioned by the slot solver away from faces and captions. Every character must exist in the clip's transcript (T-30); the card never adds external facts, sources or verdicts. If the claim is not user-checked (I-7) a small "CLAIMED BY SPEAKER" tag is drawn. Off by default.

## 21.3 Caption modes
`hormozi_glow` (the measured reference, default) · `gravitas` (sentence-level, no pop, no emoji, for serious subjects) · `karaoke_lite` (accent word, no glow; fastest render). **Emoji pops** (competitor-parity, opt-in): curated map of Part 8, ≤ 1 per 8 s, placed above the caption slot, never over a face exclusion, never for sensitive topics (war, deaths, abuse, elections); failure → drop.

## 21.4 Verify-before-post gate (I-7)
Studio lists every checkable claim in the clip (figure, words, timestamp). The user ticks `claim_checked` and may paste a source URL. Unchecked claims disable Auto for that clip; checked claims with sources are written to the metadata pack ("Claims in this clip") and an optional pinned-comment sources line. The product never fact-checks and never labels a claim true or false.

## 21.5 Pacing advisor (advisory only)
Studio draws a "visual-change timeline" (cuts, punch-ins, mode changes, chips, cards) and highlights stretches > 6 s with none, suggesting punch-ins. No automatic action; effect on retention is `[assumed]` and testable through Part 23.

## 21.6 Reaction-aware endings
See 20.3 `keep_reaction_s`; QA still enforces the tail rules of 7.5.

## 21.7 Deliberate non-goals (and why)
- **AI dubbing / voice cloning / lip-sync of real people:** synthetic speech of real political figures is an impersonation and election-integrity risk (15.10). Translated captions only.
- **Automatic AI B-roll or generated imagery:** can misrepresent events or people. A user-supplied manual overlay is allowed, labelled `illustrative`, never over a speaker's quoted words.
- **"Virality prediction":** no such claim (7.8). Part 23 reports correlations on your own channel only.

---

# PART 22 — DISTRIBUTION & INTEROP (v5)

## 22.1 Export bundle and NLE hand-off
Per clip: `clip.mp4`, `captions.srt`, `captions.vtt`, `captions.ass`, `cover.jpg`, `metadata.json`, `edits.json`, `provenance.json` (15.11), and a **timeline** referencing the *source file* with trims and the caption track: `timeline.otio` (OpenTimelineIO), FCPXML, and CMX3600 EDL for simple cuts — so a human can finish in Resolve/Premiere/CapCut Desktop. T-32 round-trips them.

## 22.2 Publish Pack (manual-first, API optional)
- Always produced: `publish_plan.csv` (platform, title, description, hashtags, pinned comment, `scheduled_at`, `privacy` default `private`) and copy-ready text blocks per platform.
- Optional API publishers live in `dc/distribute/*` as separate plug-ins, **disabled by default**:
  - **YouTube Data API `videos.insert`** — resumable upload. Per public developer summaries, uploads from projects created after 2020-07-28 that have not passed YouTube's API compliance audit are forced private; the upload scope is restricted `[ext-verified via third-party summaries 2026-10-04 — confirm in Google's current docs]`.
  - **TikTok Content Posting API** — Direct Post and Upload-to-inbox modes; unaudited clients are restricted to private viewing; requires express user consent and disclosure controls; creator caps apply `[ext-verified: TikTok developer docs, 2026-10-04]`.
  - **Instagram/Facebook Graph API** — requirements `[verify at build]`.
- Rules: default privacy `private`/inbox · never publish a clip with an integrity flag ≥ `review`, `claim_checked` missing, or `rights_class` unknown · every publish needs an explicit click in Studio and writes `publish_log.jsonl` · tokens live in the OS keyring (Part 24).
- Honesty: scheduler parity with commercial tools depends on passing those platforms' audits. Until then the pack's value is zero-typing manual posting; do not describe it as "auto-posting".

## 22.3 Multilingual caption sidecars (measured before claimed)
Offline translation (CTranslate2 or equivalent) with a **permissively licensed** MT model — check licences; some popular multilingual MT weights are reported as non-commercial `[verify]`. Output `captions.<lang>.ass` with script-appropriate Noto fonts, no ALL-CAPS for uncased scripts, `\fscx` recalibration per font (11.4), RTL/shaping via libass + HarfBuzz, no-tofu pixel check (T-34). Metadata labels the track `machine_translated`. Translations are **additional exports**, never silent replacements. Non-English *sources*: ASR language-confidence gate; L0 English lexicons are disabled; L1 multilingual embeddings only; clips default to `needs_review`. Claim a language only after a per-language word-error and caption-fit measurement.

## 22.4 Phone review (swipe queue)
`dc studio --lan` serves the review queue to a phone on the same network (token + QR, read-only by default; Part 24). Vertical 540×960 proxy feed: swipe right = approve, left = reject, tap = trim/headline pick. Designed for the overnight batch → morning review story; manual steps per clip are measured (≤ 3).

---

# PART 23 — LEARNING LOOP v2 (v5)

Everything here is **proposal-only**: nothing changes weights, thresholds or lexicons without the user's approval and a `DECISIONS.md` entry.

## 23.1 Decision log → "taste" ranker
Every Studio action (approve, reject, trim delta, headline pick, crop override) is stored with the candidate's feature vector in `labels.sqlite`. After **≥ 150 labeled decisions**, fit a regularised logistic model (approve vs reject) on the component scores; use it only if leave-one-out/k-fold **AUC ≥ 0.70**. It may be blended into ranking with weight ≤ 0.30 and always displayed as a separate "your taste" bar next to the default score.

## 23.2 Boundary-bias learner
Log the signed difference between proposed and user-final start/end. If the median bias over ≥ 30 edits is ≥ 80 ms in one direction, propose a change to `pre_roll`/`post_roll` or onset offsets (7.5). Never auto-apply.

## 23.3 Negative memory
Rejected candidates' embeddings are added to a "rejected" set; MMR (7.9) penalises similarity to it (so the same bad pattern stops resurfacing).

## 23.4 Analytics import (replaces 12.12's unspecified regression)
Import platform stats CSV per clip (views, average % watched, swipe-away@3 s, shares, `variant_id`). Fit **ridge regression with leave-one-out CV**, only when **N ≥ 60 clips**; report coefficients with bootstrap CIs and CV error; if CV error is not better than predicting the mean, say so. Language in the UI: *correlation on your channel, not a virality prediction*. Hook-variant outcomes (12.2) are compared per `variant_id` with the same caution (small N).

## 23.5 Label mode
Studio "Label mode" supports the protocol in 17.5 (blind annotation of clips the user would post, rating of candidates) so evaluation data is collected as a by-product of normal use.

---

# PART 24 — SECURITY & HARDENING (v5)

Threat model: the **text and media are attacker-controlled** (video titles, descriptions, comments, transcripts, filenames, metadata); the local web UI can start FFmpeg and write files; the user may open the UI from a phone.

1. **Binding:** server binds `127.0.0.1` only. `--lan` enables LAN mode with a random per-session token (≥ 24 bytes, URL-safe) shown as a QR; LAN mode is read-only + approve/reject unless `lan.read_only_default=false`.
2. **Request checks:** every state-changing request needs the session token header; verify `Host` and `Origin` (reject cross-origin); same-site cookies if cookies are used; no CORS wildcard.
3. **Output encoding:** all untrusted text is rendered with `textContent`/escaped templates; **no `innerHTML`, `eval`, `document.write`, inline event handlers**; CSP `default-src 'self'` (no inline scripts); video served only via ID-based routes.
4. **File access by ID only:** the client never supplies a path; IDs map to files under `work/<job>/` and `exports/`; reject `..`, drive letters, UNC paths and reserved Windows names; sanitise downloaded filenames; never follow symlinks out of the job folder.
5. **Subprocess hygiene:** one wrapper for all subprocess calls — argument lists only, `shell=False`, timeouts, output-size caps, process-tree kill on cancel; stderr logged, never executed.
6. **Dependencies and models:** pin versions with hashes (`requirements.lock`); record model SHA-256 in `MODELS.md` and verify at `doctor`; `yt-dlp` version pinned and updated only by an explicit `dc update-ytdlp` (it changes often); no auto-update on run.
7. **Secrets:** API keys and OAuth tokens only in the OS credential store (`keyring`); never in config, repo, logs or `RenderPlan`; logs redact tokens and URLs' query strings.
8. **Data minimisation:** comments (20.2) reduced to bin counts; the optional LLM layer sends transcript **text only**; a `--no-network` switch makes any network call raise.
9. **Tests (T-23):** XSS payloads in transcript/title/comment/filename render inert; cross-origin and token-less POSTs are rejected; server not reachable from another host without `--lan`; traversal IDs return 400; `grep` gates in Part 26 pass.

---

# PART 25 — RELIABILITY & OPERATIONS (v5)

1. **Job state machine** persisted in SQLite: `queued → running(stage) → awaiting_review → rendering → passed | needs_review | failed | cancelled`, with heartbeat timestamps. A crashed app resumes at the last artifact whose hash verifies; stages are idempotent.
2. **Atomic outputs:** write `clip.mp4.part` and `export_report.json.part`, rename only after QA; `exports/` never contains partial files (T-36).
3. **Disk guard:** before a job require free space ≥ `min_free_disk_x_source` × source size (default 3×); never delete outside `work/<job_id>/`; `work/` retention default 14 days; `exports/` never auto-deleted.
4. **Overnight-batch comfort (Windows):** run analysis/render children at `BELOW_NORMAL_PRIORITY_CLASS`; keep the machine awake during a batch with `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` and release it when the queue is empty; pause the batch on battery < 20% (configurable); expose CPU/RAM in Studio.
5. **Logging:** JSONL structured logs with job/stage/correlation IDs; `dc diag` zips redacted logs + config hash + tool versions for bug reports.
6. **Determinism:** same `RenderPlan` + same tool versions ⇒ byte-identical `chrome.png`, `captions.ass`, `framing.json`; the `.mp4` is compared by decoded-frame hash, not file bytes (encoder threading can vary).
7. **Graceful degradation ladder** (documented in the report when used): GPU/ML model missing → CPU/baseline; L1 off → L0; tracker unreliable → WIDE; glow too slow → fast-glow; ASR model too slow → smaller model.

---

# PART 26 — MONITOR'S PROTOCOL (for the human supervising the builder agent)

This part is for the person reviewing the agent's work. The agent must also follow it (it is how the agent proves it did the job).

## 26.1 Evidence to demand at every milestone
`reports/M<n>_report.md` containing: commands run (copy-pasteable), raw outputs, test IDs passed with counts, verification level per feature (V0–V4) with evidence paths, deviations from this spec with `DECISIONS.md` references, known gaps. A milestone without this file is not done.

## 26.2 Red flags (stop and question the agent)
- A V3/V4 claim without a media ID and recorded command.
- Speed/accuracy numbers not produced by `bench` or the test suite.
- A threshold changed in `config/` or tests with no `DECISIONS.md` entry in the same commit.
- Tests that mock FFmpeg or the render path and are counted as render evidence.
- Pixel literals (524, 1216, 1136, 1740, 1080, 1920) outside the config loader, validators and tests.
- Features "implemented" with no off-switch, no QA hook or no test ID.
- "Better than Opus Clip/Klap" anywhere outside `reports/bakeoff.md`.
- Placeholder assets (logo, wordmark) shipped as final without a banner in `doctor`.
- Weakening a gate (precision@90, L1 gate, chrome MAE) to make it pass.

## 26.3 Spot checks the monitor can run without reading code
```
py -m dc doctor
py -m pytest -q
py -m dc bench                      # compare against numbers in LEDGER.md
git log --stat -- config tests      # threshold edits must pair with DECISIONS.md
grep -rn "shell=True" dc/           # must print nothing
grep -rnE "innerHTML|eval\(|document\.write" dc/studio/   # must print nothing
grep -rnE "\b(524|1216|1136|1740)\b" dc/ | grep -v -E "config|validator|tests"   # must print nothing
```
Also open three random exports and look at them: chrome identical across clips, captions off faces, cuts not mid-word, first/last 0.5 s clean.

## 26.4 Stop-ship criteria
Any of: a mid-word cut in an exported clip · a headline/chip/card containing a word not in the transcript · caption or chrome A/B failures on real footage · XSS/CSRF test failure · unknown `rights_class` clip published · secrets found in repo/logs · `passed` status on a clip whose QA report has an unexplained warning.

---

# APPENDIX A — `config/political_lens.json` (reference-tested values; v5 changes applied here, new sections in A.2)
```json
{
  "schema_version": 5,
  "preset": "PL-2 (reference-locked)",
  "canvas": {"w": 1080, "h": 1920, "bg": "#FFFFFF"},
  "regions": {
    "top_reserved": {"y": 0, "h": 138},
    "header": {"y": 138, "h": 158},
    "hook": {"top_limit": 320, "bottom": 505, "last_baseline": 495},
    "feed": {"x": 0, "y": 524, "w": 1080, "h": 1216},
    "bottom_white": {"y": 1740, "h": 180}
  },
  "header": {
    "logo": {"d": 158, "x": 108, "y": 138, "file": "assets/logo.png"},
    "wordmark": {"x": 276, "cap_top": 170, "cap_h": 64, "ink_w": 390, "file": "assets/wordmark.png",
                 "live_font": "assets/fonts/Anton-Regular.ttf", "color_a": "#3F3F3F", "color_b": "#EC0000"},
    "handle": {"text": "@_political_lens", "x": 303, "ink_top": 247, "ink_w": 278,
               "font": "assets/fonts/Poppins-Regular.ttf", "color": "#7F7F7F"},
    "badge": {"mode": "brand_check", "d": 50, "x": 677, "y": 176, "color": "#4DD0E2"}
  },
  "hook": {"font": "assets/fonts/Poppins-SemiBold.ttf", "color": "#0A0A0A", "px_range": [50, 40],
           "line_pitch": 1.04, "max_lines": 3, "max_w": 800, "center_x": 540,
           "emoji_font": "assets/fonts/NotoColorEmoji.ttf", "emoji_strike_px": 109,
           "target_chars": 52, "hard_chars": 78, "stance_headlines": false},
  "captions": {
    "style": "hormozi_glow", "font_file": "assets/fonts/Poppins-ExtraBold.ttf", "font_family": "Poppins ExtraBold",
    "target_cap_px": 44, "target_word_w_RIGHT": 172, "spacing": 0,
    "base": "#FFFFFF", "active": "#B4F83D", "alt_active": "#FFE600", "emphasis": "#FF3B30",
    "stroke": "#000000", "stroke_px": 5, "shadow_px": 2,
    "glow": {"method": "ass_layers", "color": "#B4F83D", "outer_bord": 18, "outer_blur": 16, "outer_alpha": 104,
             "inner_bord": 9, "inner_blur": 6, "inner_alpha": 48},
    "center_x": 540, "center_y_canvas": 1136, "slot_ladder": [1136,1096,1176,1056,1216,1016,1256],
    "uppercase": true, "strip_punct": true, "group_words": [1, 3], "merge_short_chars": 3, "max_chars": 16,
    "pause_hide_s": 0.6, "min_group_s": 0.30, "max_words_per_s": 3.0, "max_w": 800,
    "pop": {"from": 0.82, "peak": 1.08, "up_ms": 90, "settle_ms": 80},
    "x_limits": [140, 940], "bottom_max": 1480, "plate_fallback": {"alpha": 0.6, "radius": 14, "pad": 18}
  },
  "safe_zone": {"profile": "balanced"},
  "framing": {"analysis_fps": 6, "landmark_fps": 15, "mouth_window_s": 0.8, "proxy_width": 640, "min_face_px": 48, "phi_target": 0.20, "phi_panel": 0.25,
              "s_max": 1.5, "head_y_frac": 0.33, "tau_follow": 0.35, "tau_slow": 0.80,
              "deadzone_x": 0.04, "deadzone_y": 0.05, "vmax_wc_per_s": 0.25,
              "switch_margin": 0.25, "switch_hold_s": 0.6, "min_dwell_s": 1.5,
              "crosstalk_on": 0.60, "crosstalk_off": 0.35, "dual_min_dwell_s": 3.0, "divider_px": 4},
  "selection": {"weights": {"narrative": 18, "conflict": 15, "hook": 14, "clarity": 13,
                "rebuttal": 10, "ending": 9, "context": 9, "acoustic": 5, "crowd": 7},
                "auto_threshold": 90, "target_s": [25, 55], "hard_min_s": 8, "mmr_lambda": 0.7},
  "polish": {"punch_in": {"enabled": false, "max_zoom": 1.06, "ramp_s": 0.6},
             "tight_cut": {"enabled": false, "min_pause_s": 1.2, "to_s": 0.35, "max_fraction": 0.15},
             "nameplates": {"enabled": false, "show_s": 1.2},
             "progress_bar": {"enabled": false, "y": 1748, "h": 6},
             "source_credit": {"enabled": false, "y": 1790, "px": 28},
             "cover_frame": true, "metadata_pack": true},
  "audio": {"loudnorm": true, "target_lufs": -14, "true_peak_db": -1.0, "fade_ms": 30, "denoise": false},
  "output": {"crf": 18, "preset": "medium", "pix_fmt": "yuv420p", "audio_kbps": 160, "fps_cap": 30, "audio_hz": 48000}
}
```

## A.2 — v5 sections (merge these keys into the same `config/political_lens.json`; values marked null are filled by benchmark/decision, never guessed)
```json
{
  "signals": {
    "crowd_replay": {"enabled": true, "weight": 7, "anchor_percentile": 90},
    "crowd_mentions": {"enabled": false, "max_comments": 500, "bin_s": 15, "store_text": false},
    "reaction_events": {"enabled": true, "min_conf": 0.5, "window_after_s": 2.0, "keep_reaction_s": 0.0},
    "source_hygiene": {"enabled": true, "max_overlap": 0.10}
  },
  "asr": {
    "model": null,
    "vad_filter": true,
    "condition_on_previous_text": false,
    "glossary_file": "config/glossary.json",
    "auto_glossary_from_metadata": true,
    "correction_min_score": 0.92
  },
  "diarization": {"engine": "auto", "candidates": ["sherpa_onnx", "pyannote"]},
  "semantic": {
    "l1_enabled": false,
    "gate": {"metrics": ["recall@10", "precision@90"], "ci": 0.95, "min_n": 100},
    "models": {"embedding": null, "nli": null, "qa_relevance": null},
    "evasion": {"sim_tau": null, "drift_s": 8},
    "receipts": {"enabled": true, "min_gap_s": 60, "sim_tau": null, "contradiction_tau": null,
                 "c1_max_s": 12, "qualifier_window_s": 30, "auto_allowed": false},
    "llm": {"enabled": false, "provider": null, "top_n": 20, "send": "transcript_text_only"}
  },
  "craft": {
    "question_chip": {"enabled": true, "max_chars": 90, "show_s": 2.5, "px": 30, "plate_alpha": 0.65},
    "evidence_cards": {"enabled": false, "show_s": 1.8, "px": 40},
    "caption_mode": "hormozi_glow",
    "emoji_pops": {"enabled": false, "min_gap_s": 8},
    "claim_gate": true
  },
  "renderer": {
    "camera": "subpixel",
    "interp": "lanczos4",
    "static_threshold_px": 0.25,
    "queue_frames": 8,
    "color": {"matrix": "bt709", "range": "tv"}
  },
  "distribution": {
    "export_bundle": ["srt", "vtt", "ass", "otio", "fcpxml", "edl"],
    "publish": {"enabled": false, "default_privacy": "private", "require_click": true,
                "block_flags": ["review", "block_auto_approve"], "block_rights": ["unknown"]}
  },
  "translation": {"enabled": false, "targets": [], "model": null, "label": "machine_translated"},
  "learning": {
    "label_log": true,
    "taste_ranker": {"enabled": false, "min_labels": 150, "min_cv_auc": 0.70, "max_blend": 0.30},
    "analytics": {"min_clips": 60, "model": "ridge", "cv": "loo"}
  },
  "security": {
    "bind": "127.0.0.1",
    "lan": {"enabled": false, "token_bytes": 24, "read_only_default": true},
    "csp": "default-src 'self'",
    "secrets": "os_keyring"
  },
  "ops": {"low_priority": true, "prevent_sleep": true, "work_retention_days": 14, "min_free_disk_x_source": 3}
}
```

# APPENDIX B — Tunables to calibrate first
`glow.outer_alpha/outer_blur` and method · caption `dy` and `fscx` (recalibrate on font change) · `group_words` (needs more reference frames) · slot ladder step · `phi_target`/`s_max` · hook `px_range`/`line_pitch` · safe-zone profile · switch margin/dwell/crosstalk · `auto_threshold` (precision@90) · pop scale · seed lexicons · tight-cut thresholds · punch-in zoom · crowd weight · reaction `min_conf` · L1 thresholds (evasion τ, receipts τ_s/τ_c) · chip/card timing · `static_threshold_px` · interpolation (lanczos4 vs cubic) · `fps_cap` · `landmark_fps`/`mouth_window_s` · glossary `correction_min_score` · taste-ranker blend · chroma/bleed guard rows.

# APPENDIX C — Reference measurements to defend (kit-verified on the user's two reference images)
Feed 1080×1216 at y=524 (ends 1740); bottom white 180; header logo Ø158 at (108,138); wordmark x276–665, y170–234; handle x303–581, y247–280; badge Ø50 at (677,176) `#4DD0E2`; hook 2 lines at 50 px, ink x≈182–885, last baseline 495; caption "RIGHT" fill ≈ x455–625, y1114–1156, centre (540,1136), active `#B4F83D` (180,248,61), cap height 44, width 172; stroke 5 px; glow halo ≈45 px (kit footprint x409–670, y1068–1202). **Reviewer note (v5): the kit results below were not re-run during the v5 review; treat them as V2 (still-source) claims until reproduced at M1–M3.** Kit results to reproduce: chrome MAE 0.40/255; 14/14 QA pass on the still-source demo; bbox deltas ≤ 3 px (hook ≤ 9 px); 4 px chroma guard.

# APPENDIX D — Change log
v2→v3 (friend): measured reference geometry, glow spec, calibration, lossless A/B, Windows-safe paths.
v3→v4 (this file): self-contained (algorithms inlined); defects X-1…X-12 fixed; new Part 12 feature pack (prompt search, hook variants, punch-ins, tight-cut, nameplates, fairness meter, burned-in-text avoidance, cover + metadata pack, series splitter, audio chain, analytics loop, multi-brand, Review Studio); compliance Part 15; performance plan; 22 acceptance tests; milestone DoDs; bake-off protocol; honest status of what is measured vs assumed.

v4→v5 (reviewer): second audit Y-1…Y-14 (mouth-sampling statistics, sub-pixel camera, colour matrix, VFR/fps cap, bleed rationale, semantic gap, diarization token, ASR name accuracy, Studio security, rights/policy/licence gaps, Q&A courtesies, statistics of the learning loop, editorial fixes); competitor snapshot (2.2/2.3); badge default → `brand_check`; scoring weights re-balanced with a crowd term and renormalisation; new Parts 19–26; tests T-23…T-36; labeling protocol 17.5; milestones rewritten; config A.2. Every external fact is tagged `[ext-verified date]`; everything else numeric remains `[assumed]` until measured.

**Agent: start at M0. Commit after each green milestone, update `LEDGER.md`, and report the verification level you actually reached.**