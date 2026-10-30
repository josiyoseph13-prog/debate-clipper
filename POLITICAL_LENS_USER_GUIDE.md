# Political Lens — User Guide

Political Lens is a local-first tool for turning a long debate, interview, or
discussion into vertical short clips for TikTok, YouTube Shorts, and Instagram
Reels.

It finds possible debate moments, shows you why each moment was selected, lets
you review and edit the boundaries, and renders an export with the Political
Lens layout, captions, audio treatment, metadata, and editing sidecars.

The normal workflow is **process the source with the command line, then review
and export it in the browser Studio**.

> **Important current behavior:** the browser Studio's “Paste a YouTube link or
> drop a video here” box is currently a visual entry point. It does not yet
> start a download or create a processing job by itself. Use the `dc run`
> command in this guide to create the job, then open the Studio to review it.

---

## 1. What you need

You need:

- Windows PowerShell or Command Prompt.
- The project folder:

  ```text
  D:\charlie youtube long videos\clipping automation\debate_clipper
  ```

- The verified Python environment:

  ```text
  work\native_windows\venv\Scripts\python.exe
  ```

- FFmpeg and FFprobe configured in the project. The verified copy is under:

  ```text
  work\native_windows\tools\ffmpeg-9.0.2-essentials_build\bin
  ```

Run all commands from the project folder. In PowerShell, for example:

```powershell
Set-Location "D:\charlie youtube long videos\clipping automation\debate_clipper"
```

The examples below use the verified Python executable. If you created another
environment, replace its path in the commands.

---

## 2. Start the Studio

Open a terminal in the project folder and run:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Then open this address in your browser:

```text
http://127.0.0.1:8765/
```

Keep the terminal running while you use the Studio. Press **Ctrl+C** in that
terminal to stop it.

The previous interface is still available here:

```text
http://127.0.0.1:8765/classic
```

Use `/classic` when you need the older dense review interface, word buttons,
manual crop input, or controls that are easier to inspect all at once.

### Local-only behavior

The default Studio listens only on `127.0.0.1`, which means it is intended for
the same computer. It does not expose the review interface to the network by
default.

---

## 3. The complete clipping workflow

### Step 1 — Check the installation

Before processing a source, run:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc doctor
```

`doctor` checks the Python/FFmpeg setup, fonts, write access, disk space, local
Studio binding, and other required parts of the pipeline.

### Step 2 — Process a local video

For a local video, run:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run `
  --source "input\debate.mp4" `
  --rights-class permission `
  --rights-note "Written permission from the source owner" `
  --mode review `
  --top 8
```

PowerShell uses the backtick character `` ` `` for a continued command. You
can also put the command on one line:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run --source "input\debate.mp4" --rights-class permission --rights-note "Written permission from the source owner" --mode review --top 8
```

Replace `input\debate.mp4` with your real file. Supported source formats
depend on the installed FFmpeg build, but common formats include MP4, MOV,
MKV, and WebM.

### Step 3 — Process a URL

The CLI can download a URL through the configured downloader:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run --source "https://www.youtube.com/watch?v=VIDEO_ID" --rights-class unknown --rights-note "Source rights not verified" --mode review --top 8
```

The URL workflow requires network access and a working `yt-dlp` installation.
The downloaded media is stored under the project input area and then processed
like a local source.

Only use media you are allowed to download and edit. A source URL or
attribution is not automatically permission to republish the content.

### Step 4 — Choose the rights classification

The `--rights-class` value records what you know about the source:

| Value | Use when |
|---|---|
| `own` | You own the source and have the right to use it. |
| `permission` | You have permission from the rights holder. |
| `public_domain_verified` | You verified that the source is public domain. |
| `licensed` | You have a licence covering this use. |
| `unknown` | You have not verified the rights yet. |

If you omit the option, the default is `unknown`.

Unknown rights do not necessarily stop local analysis or review, but they do
block the publish gate. The export can contain a `publish_dry_run.json` file
that explains why publishing is blocked.

### Step 5 — Optional: supply an existing transcript

If you already have a hand-checked transcript with word timestamps, provide
it instead of asking the ASR stage to create one:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run `
  --source "input\debate.mp4" `
  --transcript "input\debate.json" `
  --rights-class own `
  --mode review `
  --top 8
```

Without a supplied transcript, the project uses the configured local ASR
profile if it is installed. ASR produces timestamped words used for candidate
boundaries and captions. If no usable ASR model is installed, use a transcript
file or install the appropriate optional ASR environment before running a
source.

### Step 6 — Wait for the job to finish

The command prints a result similar to:

```json
{
  "job_id": "job_example",
  "state": "awaiting_review",
  "candidate_count": 8,
  "work_dir": "...\\work\\job_example"
}
```

Copy the `job_id` if you want to use the command-line search or render
commands. The important state for browser review is:

```text
awaiting_review
```

The job artifacts are stored in:

```text
work\<job_id>\
```

The original source is not overwritten.

### Step 7 — Open or refresh the Studio

With the Studio running, open or refresh:

```text
http://127.0.0.1:8765/
```

The Home screen loads the jobs already stored in the project. Your processed
job should appear under **Recent jobs** with a plain status such as:

- **Working** — processing is still running.
- **Ready to review** — candidates are available.
- **Done** — an export completed.
- **Problem** — the job needs attention.

---

## 4. How the software finds clips

Political Lens does not simply cut every loud section. Its selection pipeline
works roughly like this:

1. **Ingest** fingerprints the source, probes its dimensions, frame rate,
   duration, audio, and metadata, and records the rights class.
2. **Transcribe** creates words, timestamps, and speech segments. Word timing
   is important because the renderer avoids cutting through a spoken word.
3. **Build the conversation structure** by grouping words into sentences and
   speaker turns and by identifying question/answer and debate relationships
   when the available evidence supports them.
4. **Generate candidates** that may contain a setup, disagreement, response,
   concession, contradiction, or another complete moment.
5. **Score and rank candidates** using signals such as narrative completeness,
   disagreement, opening strength, clarity, response coverage, ending quality,
   context, voice energy, and available audience signals.
6. **Check integrity and fairness** for missing context, possible cut-off
   responses, uncertain speakers, claim checks, and other review risks.
7. **Return the highest-ranked candidates** while keeping the evidence and
   warnings attached to each candidate.

The score is a ranking aid. It is not a guarantee of views, virality, truth,
or political correctness.

The default target is a short mini-story: usually around 25–55 seconds, with
the actual candidate limits controlled by the selected configuration. A
candidate can be shorter or longer when the conversation requires it.

---

## 5. Using the guided Studio

The main screen has four steps across the top:

1. **Add video**
2. **Find clips**
3. **Review**
4. **Export**

The source-processing command described above must be run before the Studio
can show real candidates.

### Add video

This page shows:

- The Political Lens welcome message.
- The current recent jobs.
- A plain-language status and progress bar for each job.
- A help message when a job needs attention.

At the moment, use the terminal `dc run` command to add/process the source.
After the job is ready, continue to **Find clips** or **Review**.

### Find clips

The search page is called **Find a moment**. Type a plain-language request,
for example:

- `where does he dodge the question?`
- `find the strongest disagreement`
- `where does someone change their mind?`

You can click one of the example searches or enter your own question. The
browser search works against candidates already generated in the project; it
does not transcribe a new source or create a new job. The command-line search
below lets you target one specific job.

The command-line equivalent is:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc find --job job_example --q "where does he dodge the question" --top 5
```

Replace `job_example` with the actual job ID.

### Review

The Review page is where you decide what to keep. Each clip card contains:

- A video player connected to the source video.
- A plain title such as “Clip starting at 12:40”.
- The source time range, such as `12:40 to 13:25`.
- The approximate clip length.
- A word rating: **Great**, **Good**, **Okay**, or **Weak**.
- The numeric score in smaller text.
- A short reason such as “Strong opening, clear point, ends cleanly.”
- Warnings when the system needs human attention.
- A headline field.
- **Approve**.
- **Reject**.
- **Edit start/end**.
- **Export**.

#### Approve

Click **Approve** when you want to keep the candidate. This saves your
decision for the job. Approval does not automatically publish the clip.

#### Reject

Click **Reject** when the moment is not useful, is missing context, has a bad
cut, or is otherwise not suitable. Rejected examples can also be used by the
selection system as negative feedback in later processing.

#### Edit start/end

Click **Edit start/end** to show the numeric start and end fields. Times are in
seconds and can use decimals, for example:

```text
Start: 762.40
End:   805.20
```

Choose boundaries at natural word boundaries. The renderer rejects a boundary
that cuts through the middle of a word. If you see a boundary error, move the
start or end slightly earlier or later until it is between spoken words.

The classic interface also shows word buttons. In `/classic`, click one word
to choose a start boundary and another word to choose an end boundary.

#### Headline

The headline is shown in the top hook area of the vertical export. It must fit
the configured hook area and must remain faithful to the words in the clip.
The renderer refuses a headline that introduces unsupported words or claims.

#### Export

Click **Export** after approving a clip. The Studio saves the approval, creates
a render plan, renders the vertical MP4, runs technical QA, and creates the
export bundle if QA passes.

Export can take time because it may perform framing analysis, caption
generation, audio processing, FFmpeg rendering, cover-frame selection, and
post-render checks.

### Warnings you may see

Warnings are deliberately visible. They are review prompts, not automatic
verdicts:

- **Speaker: not identified yet** — speaker diarization or labels are not
  reliable enough yet. Check the video and optionally use Advanced speaker
  labels.
- **Rights unknown, publishing blocked** — the source rights class is still
  `unknown`. You may review locally, but the publish plan stays blocked.
- **Caption may be wrong** — inspect the words before exporting or posting.
- **Another response may be outside this clip** — a possible response from
  another speaker occurs shortly after the selected range. Review the full
  exchange before treating the clip as complete.

### Why this score?

Open **Why this score?** on a card to see the available score details. The
labels are written in plain language:

| Screen label | What it means |
|---|---|
| Complete story | The moment has a setup and a meaningful ending. |
| Disagreement | The speakers show a meaningful difference of opinion. |
| Strong opening | The first line gives the viewer a reason to keep listening. |
| Easy to follow | The words and point are clear. |
| Response included | An answer, challenge, or reply is present. |
| Clean ending | The clip ends after a complete thought. |
| Enough context | The clip can be understood without guessing too much. |
| Voice energy | A measured voice or sound signal was available. |
| Audience signal | A replay or audience signal was available. |

If a signal was not available, the Studio says **Not measured**. A numeric
value is a clue used for ranking; it is not a factual rating of the speaker.

---

## 6. Advanced controls

Open the **Advanced** section on a clip only when you need more control. Normal
review does not require these settings.

### Caption mode

The available modes are:

- `hormozi_glow` — the default Political Lens highlighted-word style.
- `gravitas` — a calmer caption presentation.
- `karaoke_lite` — a lighter word-progress style.

The selected mode is saved with the decision and applied during rendering.

### Layout

The layout choices are:

- `auto` — let framing analysis choose the safest layout.
- `dual` — use a stacked two-panel treatment when the evidence supports it.
- `manual` — use a manually supplied crop in the classic interface.

When face or speaker evidence is weak, the renderer can choose a conservative
wide treatment instead of confidently following the wrong person.

### Caption colour

The colour control changes the active caption colour. Use a six-digit hex
colour such as `#B4F83D`.

### Speaker labels

Speaker labels are user-provided names. Enter the supported JSON mapping when
you know the labels, for example:

```json
{"speaker_0":"Host","speaker_1":"Guest"}
```

Do not use `unknown` as a speaker label. Labels are stored with the transcript
and can be used for nameplates when that feature is enabled in the preset.

### Retry / resume

Use **Retry / resume** when a job was interrupted or needs to continue from
its saved artifacts. The command-line equivalent is:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc resume --job job_example
```

### Cancel job

Use **Cancel job** to request cancellation. The process tree is stopped and the
job is marked cancelled when the cancellation is handled.

### Fix a word everywhere

Enter the incorrect word and the corrected word, then click **Apply
correction**. The correction is recorded in the transcript, the previous
candidate file is retained, and candidates are selected again from the
corrected transcript.

This is useful for names, places, organizations, and other political terms
that ASR may have written incorrectly.

### Blind Label mode

Blind Label mode is for testers and human evaluation. It hides the normal
system score so a person can rate the clip without being influenced by the
ranking.

The classic interface also provides ratings such as:

- `would_post`
- `as_is`
- `trivial_trim`
- `not_usable`

These labels are evaluation data. They do not automatically publish anything.

---

## 7. What rendering does to the clip

When you export an approved candidate, Political Lens builds one RenderPlan
and uses it for the preview and final output. The renderer can:

- Create a 1080×1920 vertical output.
- Preserve the selected source time range.
- Reframe the speaker or use a conservative layout.
- Use the Political Lens header, logo, wordmark, hook area, feed, and bottom
  reserved area.
- Burn in word-timed captions using the configured caption style.
- Avoid detected faces or source text when caption placement would collide.
- Keep the output frame rate within the configured cap, normally 30 fps.
- Normalize audio toward the configured loudness target.
- Add configured craft elements such as question chips when available.
- Choose a cover frame when the required video tools are available.
- Run technical QA before making the bundle complete.

The application does **not** automatically fact-check political claims. It
does not generate political B-roll, clone voices, dub voices, or predict
virality.

---

## 8. Where exported files are stored

For candidate `c_example`, the completed bundle is normally here:

```text
exports\c_example\
```

Typical files include:

| File | Purpose |
|---|---|
| `clip.mp4` | The rendered vertical clip. |
| Stable `.mp4` filename | A source/candidate/hash-based copy for handoff. |
| `cover.jpg` | A selected cover frame when available. |
| `captions.srt` | Standard subtitle sidecar. |
| `captions.vtt` | WebVTT subtitle sidecar. |
| `captions.ass` | ASS subtitle/caption artifact when included. |
| `timeline.otio` | OpenTimelineIO handoff timeline. |
| `timeline.fcpxml` | Final Cut Pro XML handoff. |
| `timeline.edl` | EDL handoff. |
| `metadata.json` | Titles, description, hashtags, chapter data, claims, and rights class. |
| `publish_plan.csv` | Private-by-default platform publishing plan. |
| `publish_dry_run.json` | Whether the publish gate allows publishing and why. |
| `provenance.json` | Source hash, output hash, edit information, and tool/config evidence. |
| `edits.json` | Saved edit and augmentation information. |
| `export_report.json` | Technical QA result. |
| `render_plan.json` | The plan used to make the output. |
| `candidate.json` | The selected candidate and its evidence. |
| `framing.json` | The selected framing segments. |
| `bundle_manifest.json` | Hash-checked list of bundle files. |

The `work\<job_id>\` folder contains the intermediate transcript, candidate
list, debate graph, render plan, logs, and recovery artifacts.

---

## 9. Command-line alternatives

The browser is the easiest place to review, but the core also has direct
commands.

### Search a job

```powershell
work\native_windows\venv\Scripts\python.exe -m dc find --job job_example --q "find the strongest disagreement" --top 5
```

### Render a candidate directly

```powershell
work\native_windows\venv\Scripts\python.exe -m dc render --job job_example --candidate c_example
```

The normal review-first workflow is safer: review and approve in the Studio,
then render.

### Render title variants

```powershell
work\native_windows\venv\Scripts\python.exe -m dc render --job job_example --candidate c_example --variants 3
```

### Make a preview

```powershell
work\native_windows\venv\Scripts\python.exe -m dc preview --job job_example --candidate c_example
```

### Cancel or resume

```powershell
work\native_windows\venv\Scripts\python.exe -m dc cancel --job job_example
work\native_windows\venv\Scripts\python.exe -m dc resume --job job_example
```

### Process a folder

For a folder of sources:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc batch --sources "inbox" --mode review --preset political_lens
```

For a watch folder that processes new media:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc watch --inbox "inbox" --mode review --interval 2
```

---

## 10. Auto mode and batch mode

The safe default is review-first mode:

```text
--mode review
```

Auto mode can render an eligible high-scoring candidate, but it is deliberately
conservative. It does not auto-approve a candidate with unresolved review or
integrity problems, and unknown rights remain a publish block.

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run --source "input\debate.mp4" --rights-class own --mode auto --auto-threshold 90 --top 8
```

Use auto mode only after you understand and have reviewed the output behavior.
Review-first mode is recommended for political material and unfamiliar
sources.

---

## 11. Rights, integrity, and publishing rules

Political Lens is designed to expose risk instead of hiding it.

- Rights default to `unknown` unless you provide a classification.
- Unknown rights block publishing.
- Integrity warnings can require review before export or publishing.
- A candidate that may cut off a response is shown with a warning.
- A headline must remain faithful to the clip.
- Claim evidence can be checked and saved with source URLs.
- Export files include provenance and the source hash when available.
- Publishing is private-by-default and requires a deliberate user action.
- The app does not perform a live platform upload in the current build.

You are responsible for permission, copyright, fair-use/fair-dealing analysis,
platform rules, political-content rules, and the accuracy of the claims in the
final post.

---

## 12. Troubleshooting

### The Studio says there are no videos

1. Confirm that `dc run` completed and printed `awaiting_review`.
2. Confirm you ran the command from the project folder.
3. Confirm the Studio is also running from the same project folder.
4. Refresh `http://127.0.0.1:8765/`.

### The Home screen does not process my pasted URL

That is expected in the current build. Run the URL through the terminal first:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run --source "https://example.com/video" --rights-class unknown --mode review
```

Then refresh the Studio.

### ASR or transcript errors

Use a verified transcript:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc run --source "input\debate.mp4" --transcript "input\debate.json" --rights-class own --mode review
```

Otherwise install/configure the local ASR profile and run `dc doctor` again.

### Export says the edit cuts through a word

Move the start or end to a natural pause or word boundary. The classic route
provides word buttons that make this easier:

```text
http://127.0.0.1:8765/classic
```

### Export is blocked by rights

The source was processed with `rights_class: unknown`. Start or reprocess the
source with the correct verified classification and an explanatory note. Do
not select a stronger classification unless it is true.

### Export is marked “needs review”

Read `work\<job_id>\export_report.json`. Inspect the clip, the warning, the
captions, and the framing. Resolve the issue or explicitly accept the review
state only when the result is genuinely acceptable.

### The browser cannot connect

Make sure the Studio terminal is still running and that you opened the exact
address:

```text
http://127.0.0.1:8765/
```

If you started it with another port, use that port in the browser address.

---

## 13. Short version: how to make one clip

```powershell
# 1. From the project folder, process a source.
work\native_windows\venv\Scripts\python.exe -m dc run --source "input\debate.mp4" --rights-class own --mode review --top 8

# 2. Start the browser Studio in another terminal.
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

Then:

1. Open **Find clips**.
2. Search for a moment in plain words.
3. Open **Review**.
4. Watch the candidate.
5. Adjust the headline or start/end if needed.
6. Read every warning.
7. Click **Approve**.
8. Click **Export**.
9. Find the result in `exports\<candidate_id>\clip.mp4`.
10. Check `publish_dry_run.json` before posting anywhere.
