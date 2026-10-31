# HOW TO SET UP THE PROJECT — step by step

This is the plain walkthrough for setting up the Debate Clipper project on a
Windows PC, from nothing to a working system. Follow the steps in order.
Do not skip a step because it "looks fine" — each step has a check, and the
check is the point.

## Before you start

You need:
- A Windows PC with plenty of free disk (source videos, models and renders
  are large — keep at least 30 GB free).
- Your own Muse signed in as you.
- The project code: accept the owner's invite to the PRIVATE GitHub repo
  (or receive the code zip from the owner). Never put this code in a public
  repo.

## Step 1 — Put the machine tools on

Install these first; the project setup expects them:

- **Python 3.14** — check: open PowerShell and run `python --version`.
  (The production machine runs 3.14; the project refuses anything under 3.11.)
- **FFmpeg, a FULL build** (with libass, harfbuzz, libx264) on your PATH —
  check: `ffmpeg -version`. A minimal build fails the caption/render checks.
- **Node.js 24 or newer** — check: `node --version`.
- **Git** — check: `git --version`.

## Step 2 — Get the code

Clone the private repo into a normal working folder, for example:

```
git clone <the private repo address> D:\debate_clipper
```

(Or unzip the code zip into that folder.) From here on, "the project folder"
means that folder. Open PowerShell inside it for every command below.

## Step 3 — Run the project setup

In the project folder:

```
.\setup.ps1
```

What it does, in order:
1. Creates the project's own Python environment (`.venv_dc`).
2. Installs THREE pinned package sets, each verified by fingerprint
   (hash-checked): `requirements.lock` (core),
   `requirements-asr-windows.lock` (speech — without it every job dies at
   transcription), `requirements-vision-windows.lock` (vision — without it
   framing cannot be measured and renders fall back to a blurred wide
   strip, which the house rules treat as a failed export).
3. Writes the project's local tools config inside the folder.
4. Runs the health check (next step) and stops if it finds a hard failure.

Expect roughly 15–30 minutes, depending on the connection. If setup stops
with an error, read the last lines of the output: they name the set or the
check that failed. Fix that; do not work around it.

## Step 4 — Pass the health check

Setup already ran it once. Run it again any time with:

```
.\.venv_dc\Scripts\python.exe -m dc doctor
```

The bar: **no hard failures.** Warnings are expected and do not block work —
in particular, warnings about optional models that are disabled by default
(the offline Whisper base model is not shipped; the speech model downloads
from Hugging Face on first use). If a model fingerprint (SHA-256) fails,
your copy of the files changed on the way in — clone the repo fresh and do
not edit anything under `assets\models`.

## Step 5 — Put YOUR brand in

The project ships a neutral starter brand so nothing starts broken:
`config\starter.json` + `config\presets\starter.json`, placeholder artwork
at `assets\starter_logo.png` and `assets\starter_wordmark.png`.

1. Replace the two placeholder artwork files with your owner's logo and
   wordmark (keep the same file names, or update the names in the config).
2. Set your channel name and handle in the config.
3. Simplest route: copy your finished config over
   `config\political_lens.json`. Then the default path, the health check,
   and the test suite all use your brand. (Or keep your config as its own
   preset and pass `--preset <yours>` on every job.)
4. The `political_lens` and `open_debate` configs are the ORIGINAL owner's
   accounts. Never post with them.

One test checks exactly this step: it fails until your own supplied logo
artwork is the one being used. That failure means "brand not in place yet",
not "the project is broken".

## Step 6 — Prove it works

Run the project's test suite:

```
.\.venv_dc\Scripts\python.exe -m pytest -q
```

The bar: **zero failures** (160 tests at the time of writing; the count can
grow — what matters is that none fail).

Then one practice job with a short debate video file saved on the PC:

```
.\.venv_dc\Scripts\python.exe -m dc run --source <video file> --job practice --mode review --top 5 --rights-class unknown
.\.venv_dc\Scripts\python.exe -m dc render --job practice --candidate <the top candidate id from the run output>
```

Check the export: it must be 1080x1920, pixel format yuv420p, and — per the
house rules — the picture must FILL the frame in the speaking shots. If the
framing report says "Not measured", the vision set did not install; re-run
Step 3.

## Step 7 — Start Studio (the review app)

```
.\run.ps1
```

Then open `http://127.0.0.1:8765` in a browser. In Studio you add a video,
let it transcribe and rank candidates, review them, and export.

## Step 8 — Only now, the first real clip

Read `FRIEND_CLIPPER_RULES.md` fully and write the rules back in your own
words for your owner (the read-back). Then build ONE test clip under the
full rules, with a separate checker, for the owner's verdict — see
`GIVE_TO_FRIENDS_MUSE.md` and `SUPERVISION_LOOP.md`. Regular production
starts only after the owner passes that test clip.

## If something breaks — the short list

- **A job dies at transcription** → the speech set is missing. Re-run Step 3.
- **Framing "Not measured", exports are a wide strip in blur** → the vision
  set is missing. Re-run Step 3.
- **Health check fingerprint (SHA-256) failure on a model file** → the copy
  changed the file's bytes (line endings). Clone fresh; never edit files
  under `assets\models`.
- **The one brand test fails** → your brand is not in place. Redo Step 5.
- **An export plays green/broken on a phone** → wrong pixel format. The
  renderer exports yuv420p; do not override the output settings.
