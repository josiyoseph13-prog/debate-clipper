# POLITICAL LENS

Local-first, review-first debate-shorts factory for TikTok, YouTube Shorts,
and Instagram Reels. It produces deterministic 1080×1920 H.264/AAC exports
with PL-2 chrome, feed-local ASS captions, conservative reframing, explainable
debate candidates, integrity flags, provenance, metadata, and NLE sidecars.

## Quick start

For the complete non-engineer workflow, see
[`POLITICAL_LENS_USER_GUIDE.md`](POLITICAL_LENS_USER_GUIDE.md). It explains
how to process a source, review candidates in the Studio, edit boundaries,
export a clip, and understand the rights/publishing gates.

The project path may contain spaces. All application subprocesses use argument
lists and the render job folder as their working directory.

Native Windows setup keeps the core separate from the old Streamlit environment:

```powershell
.\setup.ps1 -PythonPath ".venv\Scripts\python.exe" -FFmpegDirectory "C:\tools\ffmpeg\bin"
.\run.ps1
```

Supply your actual Python3.11+ and FFmpeg locations. The core defaults to
`.venv_dc`; `-VenvPath` can select another core environment. Setup records
portable tool/Python paths in `config/local_tools.json`, and run.ps1 uses them.
The verified isolated environment here is `work\native_windows\venv`, with
tools in `work\native_windows\tools\ffmpeg-9.0.2-essentials_build\bin`.

```powershell
py -m pip install --require-hashes -r requirements.lock
py -m dc doctor
py -m dc run --source "input\debate.mp4" --rights-class permission --rights-note "written permission" --mode review --top 8
py -m dc find --job job_<id> --q "find where he dodges the question" --top 5
py -m dc render --job job_<id> --candidate c_<id>
py -m dc studio
```

For a pre-existing hand-verified transcript, avoid downloading an ASR model:

```powershell
py -m dc run --source "input\debate.mp4" --transcript "input\debate.json"
```

`doctor` checks Python, FFmpeg/ffprobe, libass/HarfBuzz/x264 reporting,
optional modules, placeholder assets, safe-zone verification, badge mode,
free disk, the path-with-spaces condition, and the local Studio bind address.

## Product workflow

1. **Ingest** fingerprints the source, probes streams, stores metadata and
   requires an explicit `rights_class` before Auto or Publish can pass.
2. **Transcribe** uses faster-whisper CPU int8 with VAD when installed. The
   glossary and repetition guard protect proper names and silence artifacts.
3. **Select** builds words → sentences → turns → debate graph, then generates
   conservative L0 candidates with boundaries, evidence, fairness, claims, component
   scores, context warnings, and integrity flags. BM25-style prompt search is
   offline; semantic L1/L2 layers are gated and disabled until measured.
4. **Review** is the default. The Studio is bound to `127.0.0.1`; untrusted
    text is inserted with `textContent`; every mutation requires a session token
    and an exact Host/Origin match, including the port. File routes use IDs.
5. **Render** creates the same `RenderPlan` for preview and final export. PL-2
   uses the config-defined header/feed/bottom bands, feed-local 3-layer ASS
   glow, conservative WIDE framing when evidence is weak, BT.709 tags, CFR
   cap, fades, and loudness normalization.
6. **Export** writes MP4, SRT, VTT, ASS, cover when available, metadata,
   edits, provenance, OTIO/FCPXML/EDL, and a private-by-default publish plan.
   The complete bundle is hash-checked in work before directory promotion;
   interrupted promotion recovers without exposing partly written sidecars.
   Previous bundles are retained. Hard QA failures cannot be accepted as warnings.
   Any unresolved rights, integrity-review, or claim-check flag blocks publish.

## Existing Streamlit shell

The earlier interactive workflow remains available for compatibility:

```powershell
streamlit run app.py
```

The v5 CLI and Studio share `dc`; the preserved Streamlit workflow uses its
historical root modules. Install that optional profile with `requirements.txt`
or `setup.ps1 -Legacy` in an appropriate environment.

The core hash lock has run on Linux Python **3.14.4** and native Windows
Python **3.14.7** with actual wheel installations and tests.
Python syntax supports 3.11+, but wheel availability and compatible dependency
pins must be checked for the chosen Python/Windows installation. The core lock
uses OpenCV headless 5; it provides warping while legacy Haar face detection is
unavailable, so automatic reframing remains WIDE. The legacy profile uses
OpenCV contrib 4.x. Optional ML stacks and OpenTimelineIO have separate wheel
requirements; run `doctor` after installation.

## Configuration and assets

- `config/political_lens.json` is the PL-2 source of truth; no production
  geometry belongs in Python literals.
- `config/safe_zones.json` is deliberately unverified until platform
  screenshots are supplied.
- Montserrat, Poppins, Anton, Bebas Neue, and Noto Color Emoji include OFL licences;
  hashes and sources are in `MODELS.md`. Montserrat ExtraBold is the closest
  tested caption fallback; the exact CapCut Viral font is unknown. Actual
  libass/HarfBuzz RIGHT calibration retains the V5 172×44px target/tolerance.
- The supplied genuine200px JPG emblem is used directly, with no redrawing.
  Five screenshots and six reference videos have been inspected and measured.
  The adjoining Anton wordmark is a fallback; a separate production wordmark
  and clean full-size reference frame are still needed for exact fidelity.
- Seven golden videos were inventoried. `reports/supplied_media/golden_requirements.md`
  lists the genuine labels, raw-source mapping, rights and raters still needed.
- `brand_check` is the default badge. `platform_style` is available only when
  the account is genuinely verified and makes `doctor` warn.

## Integrity and legal posture

The tool processes sources selected by the user. Attribution does not itself
create permission: third-party clipping can infringe copyright or platform
terms, and fair use/fair dealing depends on jurisdiction and facts. The user
is responsible for permission or a defensible transformative use. Re-read
each platform's current reused-content, political/election, synthetic-media,
and branded-content policies at release time. The application does not fact
check claims, predict virality, dub voices, clone voices, recognize faces, or
generate political B-roll.

Full FFmpeg builds can carry GPL/LGPL obligations. Review the selected build,
fonts, models, and all downloaded weights before redistributing the tool.

## Verification

```powershell
py -m pytest -q
py -m dc doctor
py -m dc bench
```

The verification ledger distinguishes V0 code from V1 tests, V2 synthetic
media, V3 real footage, and V4 human-reviewed evidence. `PLAN_ACK.md`,
`DECISIONS.md`, `LEDGER.md`, `MODELS.md`, and `reports/M*_report.md` retain
the audit trail required by the build plan.

Reproducible checks with durable raw output:

```powershell
py tools/verify_v5.py
py tools/measure_subpixel.py
py tools/measure_colour.py
py tools/measure_bleed.py
py tools/measure_recovery.py
py tools/measure_cancel.py
```

Historical65-test/Poppins evidence lives in `reports/verification_v5/`.
Current frozen-tree Linux checks are in `reports/current_checks_final/`;
their start/end hashes include application/tests/tools/config/fonts/locks.
Full acceptance and subsection status is in `reports/requirements_traceability.md`.
Supplied-asset/current-font evidence is in `reports/supplied_media/`; native
setup, real render, Studio HTTP, cancellation, ASR recovery and export recovery
are in `reports/native_windows/`. Historical Poppins exports remain historical.
Actual OTIO verification uses a supported optional Python profile:
`py -3.12 tools/measure_nle.py` after installing `opentimelineio==0.18.1` there.
FCPXML1.10 has passed actual system-libxml2 validation against Apple's complete
DTD (`reports/current_checks/fcpxml.json`), including a required-reference
negative case. This confirms format structure, not application import. The
acceptance tool's schema retrieval is explicit (`--fetch-schema`); the Apple
schema is kept under owned work for local validation.
Browser fixture: install the pinned Node lock with `npm ci`, provision Chromium
with `npx playwright install chromium --only-shell`, then run
`py tools/studio_browser.py`. Temporary browser tooling is separate from the
Python core lock.
Current public-source/vendor/policy rechecks and unavailable pages are recorded
in `reports/release_policy_recheck.md`; no account audit or bake-off is inferred.
`reports/M13_report.md` and `OMNIRUSH_FINAL_REPORT.md` summarize the current
scoped passes and remaining work. The actual six encoded QA faults and
real/high-contrast top/bottom bleed profiles are in `reports/current_checks/`.
New RenderPlans declare physical4px white feed-edge guards; older plans keep
their original behavior. No chrome/white acceptance threshold was relaxed.

## Additional workflows

```powershell
py -m dc render --job job_<id> --candidate c_<id> --variants 3
py -m dc preview --job job_<id> --candidate c_<id>
py -m dc receipts --job job_<id>
py -m dc batch --sources "inbox" --preset faithful
py -m dc worker
py -m dc watch --inbox "inbox" --mode review --interval 2
py -m dc cancel --job job_<id>
py -m dc resume --job job_<id> --candidate c_<id>
py -m dc studio --lan
py -m dc learn
py -m dc analytics --csv "channel_stats.csv"
```

LAN startup prints a token URL and QR. Opening it bootstraps an HttpOnly
same-site cookie; LAN defaults permit approve/reject while editing, rendering,
canceling, and publishing require the host session. Batch work is sequential;
OS-owned execution locks and identity-checked orphan recovery protect retries.
Learning commands create proposals with sample/CV gates and require human approval.
Receipts are disclosed source-ordered manual-review proposals and never Auto.

Analysis/selection checkpoints verify every recorded file hash before reuse.
Changing caption palette/mode or encoding settings reuses discovery; changing
words, rights, metadata, learned gates or rejected examples invalidates it.
Complete ASR/model-parameter invalidation and all render-stage contracts are
still tracked as engineering work.

Verification-only offline ASR is available with the registered MIT
`whisper_base` model and `verification_asr` preset. The native optional profile
is `requirements-asr-windows.lock`; install it only in a separate compatible
core environment. Inference/crash recovery has run on a real120s source
excerpt; word/name/onset accuracy and production model selection need labels.

The supplied verification footage has `rights_class: unknown`. Its latest
export passes technical QA, while publishing remains blocked by rights and
integrity review. The app has made no live platform upload. Full project
acceptance additionally requires the remaining engineering and the real labels,
raters, asset fidelity, human Windows/phone use and platform measurements in the
build plan. Automated native Windows acceptance does not stand for human review.


---

## Handover — for a friend's Muse agent

This repo is shared (private) with a friend who runs the same clipping system
with his own Muse agent, his own accounts, and his own branding.

If you are that Muse agent, work in this exact order:

1. Read `GIVE_TO_FRIENDS_MUSE.md` — your first-message instructions.
2. Read `FRIEND_CLIPPER_RULES.md` — the binding house clipping rules.
3. Read `INSTALL_AND_SETUP.md` — setup for the project and your tools, with
   the two proof tests you must pass before building anything.
4. Read `WHAT_YOU_STILL_NEED.md` — what is not in this repo (your owner's own
   cookies, accounts, logos) and where each piece comes from.
5. Install the skills in `skills/` unchanged.
6. Write the rules back in your own words for your owner, then wait for his
   first task: ONE test clip, judged by him.

The checker rule never breaks: the builder never checks its own work — a
separate checker re-measures every finished clip and writes a report file
with real numbers. No report = not done.

Also in this repo for the handover: `WORD_TIMINGS.md` (how caption word
timings are made from the audio), `SUPERVISION_LOOP.md` (the supervisor /
builder / checker loop), `JOB_LETTER_TEMPLATE.md` (one letter per job),
`assets/models/` (speaker, diarization and face models — the 145 MB Whisper
base model is not in git; faster-whisper downloads it on first use), and
`assets/music/` (the standing bed "Crypto" by Kevin MacLeod, CC BY 4.0 —
keep the credit line from `assets/music/MUSIC_CREDIT.md` in descriptions).
