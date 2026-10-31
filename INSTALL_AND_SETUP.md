# INSTALL AND SETUP

Two halves: (A) the Debate Clipper project, (B) your own Muse tools.
The skills in this pack are instructions, not tools — a skill file does not
install FFmpeg for you. Both halves must pass their proof tests before the
first real clip.

## A. Debate Clipper project

For the plain step-by-step walkthrough, follow
`HOW_TO_SET_UP_THE_PROJECT.md`. This section is the reference behind it.

You receive the project code separately (see WHAT_YOU_STILL_NEED.md). Once you
have it:

1. Keep it in a normal working folder with plenty of free disk space — source
   videos and renders are large.
2. Known-good environment (from the production machine where this ran):
   - Python 3.14 (a dedicated virtual environment for the project)
   - FFmpeg — a FULL build (with libass, harfbuzz, libx264). A minimal build
     will fail caption/render checks.
   - Node.js (24+) for the Studio tooling/tests
   - yt-dlp for downloads
   - Project Python packages — run the project's `setup.ps1`. It installs
     THREE pinned, hash-locked sets, and all three are required:
     `requirements.lock` (core), `requirements-asr-windows.lock` (speech —
     faster-whisper; without it every job dies at transcription),
     `requirements-vision-windows.lock` (vision — mediapipe face tracking;
     without it framing cannot be measured and renders fall back to a
     blurred wide strip, which the house rules treat as a failed export).
3. Run the project's own health check (`dc doctor` from the project folder)
   and fix every hard failure before going further. Warnings about optional
   models that are disabled by default (for example the offline Whisper base
   model, which is not shipped) are expected and do not block work.
4. BRANDING — make it yours before the first real job. The repo ships a
   neutral starter brand: `config/starter.json` +
   `config/presets/starter.json`, with placeholder artwork at
   `assets/starter_logo.png` and `assets/starter_wordmark.png`. Copy the
   starter preset under your own name, replace the placeholders with your
   logo and wordmark, and set your channel name and handle. Run jobs with
   `--preset <yours>`. The `political_lens` and `open_debate` configs are
   the ORIGINAL owner's accounts — never post with them. In your own clone
   you may also copy your finished config over `config/political_lens.json`
   so the default path, the health check, and the test suite all use your
   brand; one test (`test_real_logo_artwork_is_used_without_redrawing`)
   checks exactly that your supplied logo artwork is used, and it fails
   until your own brand is in place.
5. Start Studio (the project's start script; Studio served locally, port 8765
   in the original setup) and open it in a browser.

Honest notes about the project as it stands:

- It is NOT a one-click install. Expect manual setup. Paths from the original
  machine may need adjusting to yours.
- Speaker diarization is built but switched OFF in the shipped config —
  transcripts come back with speakers "unknown". Plan for manual speaker
  assignment, or treat switching it on as your own tested change.
- The Studio caption preview is a static overlay, not the true word-by-word
  captions of the final render. Judge captions from rendered files, not the
  preview.
- Downloads from YouTube may hit bot gates. The working recipe on the original
  setup was: the owner's OWN browser cookies (exported by the owner himself —
  never share or accept anyone else's), yt-dlp with browser impersonation, and
  parallel fragment downloads. Your owner exports his own cookies on his own
  machine.

## B. Your Muse tools

Install ALL the folders in `skills/` unchanged into your custom skills
location — the same full set the original operation's agents run. The
clipping core:

- framework-clipper — the clip-selection and build framework
- local-ffmpeg-video — verifying and working media files with FFmpeg/ffprobe
- local-computer-vision — frame inspection
- local-speaker-tracking — speaker framing support
- local-research-tools — polite public web research (robots.txt obeyed)
- local-reel-catalog — cataloguing shared reels/videos

Plus the supporting set (documents/PDF, webapp testing, skill creation,
frontend/canvas/theme design, algorithmic art, Slack GIFs, foundation
checks, recovered notes) — install them all; they are part of the standard
kit even if clipping uses only some of them daily.

Models and music in the project: the speaker (ASD), diarization, and
face-landmarker models are in `assets/models/`, and the standing music bed
is in `assets/music/`. The Whisper base model is NOT in the repo (145 MB,
over GitHub's file limit) — faster-whisper downloads it from Hugging Face
on first run.

## Proof tests (both required, report results as files/numbers)

TEST 1 — Project: run `dc doctor`, then run the project's test suite
(pytest). Then add one short public debate video in Studio, let it
transcribe and rank candidates, and export one candidate. Report: doctor
output, test count, export file size + MD5 + pixel format (must be
yuv420p).

TEST 2 — Tools: with ffprobe, report the streams, duration, and loudness of
the Test 1 export, and extract a 20-frame contact sheet at full size from
it. Report the numbers and the sheet file. This proves your FFmpeg side
works independently of the project. The contact sheet is also a framing
gate: the picture must FILL the frame (speaker framing). Blurred bands
above/below a wide strip of video mean the framing was never measured —
that is a FAIL, not a style. Fix the vision setup (step 2) and render
again; never accept a blur-filled export.
Honest limit, measured on the fixed pack: with the vision stack installed
the framing IS measured and the speaking shots fill the frame — but a
moment whose source is genuinely wide (a stage or crowd shot, or a
two-shot with no single trackable speaker) can still come out as a smaller
picture inside blur, and the render report flags it (framing needs
review). Per the house rules that export is not deliverable either: in the
supervised build, cover or re-cut those moments — a filled duo crop, a
reaction shot, or a different moment — and render again.

Only after both tests pass do you build the owner's ONE test clip under the
full rules in FRIEND_CLIPPER_RULES.md, with the separate checker, for the
owner's verdict.
