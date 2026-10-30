# Political Lens — current build report

## UI Fix — 2026-10-07

The guided Studio at `/` was updated to match `OMNIRUSH_UI_FIX.md`. The old
interface remains available at `/classic`.

- The home screen now starts with the plain instruction **“Paste a YouTube link
  or drop a video here.”** It supports file choosing and drag-and-drop, shows
  recent jobs with plain statuses and accessible progress bars, and keeps the
  next action clear.
- Review cards show the video preview, source time, length, plain title, word
  rating, small measured score or **Not measured**, a plain reason, warnings,
  and big **Approve**, **Reject**, **Edit start/end**, and **Export** buttons.
- Score details, framing, captions, speaker names, retry/cancel, word fixes,
  and Blind Label mode are behind **Advanced**. Blind Label mode explains:
  “For testers. Hides the system's score so you can rate clips fairly.”
- Search is labeled **Find a moment** with three clickable example searches.
  System/model details, CPU/RAM, graphics, logs, and local activity are behind
  **Advanced settings**; values that are not measured say so.
- The browser acceptance run passed on native Windows with no JavaScript errors.
  The optional XSS text fixture was not in the current queue, so it is recorded
  as unavailable rather than passed. API security tests still cover XSS,
  traversal, origin, token, and localhost rules.
- The native Studio launcher check passed: the page loaded, CSP was present, the
  listener stayed on localhost, tokenless and cross-origin mutations returned
  403, and the launcher process tree stopped cleanly.
- Real screenshots are in `reports/ui_fix/before/` and `reports/ui_fix/after/`:
  `classic.png`, `home.png`, `find.png`, `review.png`, `export.png`, and
  `my-exports.png`.
- Native Windows full suite: **99 passed**, 1 existing Starlette warning.
  Security audit: **15,547 paths checked, zero findings**. Linux pytest is
  unavailable in this environment.

Details: `reports/ui_fix/screenshot_status.md`,
`reports/ui_fix/browser_acceptance.json`, and
`reports/ui_fix/security_audit.txt`.

## Task 3 — Duo style checkpoint — 2026-10-07

**Built and working as an optional Speaker Frame layout; real voice switching is
Not measured.** Open `reports/duo_style/WATCH_TASK_3.html` for the four real
exports, style-only comparison sheet, different-clip review, and study files.
Full details: `reports/checkpoints/CHECKPOINT_3.md`.

- Studied 9 supplied files, representing **8 distinct edits** after one duplicate
  hash. Frames were sampled every 0.5 seconds. The approximate study measured
  19 Duo runs averaging 9.31 seconds, 5 Full A runs averaging 2.20 seconds,
  and 18 Full B runs averaging 4.82 seconds.
- Added Duo beside the other Speaker Frame layouts. It is OFF by default and has
  Always Duo, Always Full, Smart, full/return delays, blend controls, side swap,
  and direction controls. Unknown audio stays Duo and warns; no identity was
  guessed.
- Three real-source Duo exports pass technical QA with 24/24 sampled faces in
  the panel inset and outside the soft join. The different raw clip completed
  with safe Wide fallback after camera changes; its face safety is **Not measured**.
- Native Edge browser test passed, including Duo controls and no JavaScript errors.
  Native full suite: **99 passed**, one existing warning. Security audit:
  **15,528 paths checked, zero findings**. Linux pytest is unavailable.
- The reference comparison is style-only because the supplied references are
  finished edits without matching raw-source cut maps. Exact synchronized
  recreation, real voice accuracy, full temporal flicker, hairline headroom,
  and platform safe zones remain **Not measured**.

## Task 2 — Speaker Frame checkpoint — 2026-10-07

**Built and working; real automatic voice switching is PARTIAL.**
Open `reports/speaker_frame/WATCH_TASK_2.html` for four real test exports and
comparisons. Full details: `reports/checkpoints/CHECKPOINT_2.md`.

- Guided clip card → More options → Speaker Frame. OFF by default; lazy editor
  starts from Auto Reframe with suggestions. Draw/move/resize/delete two boxes,
  typed labels, frame picker, saved edits, and Back to Auto Reframe work.
- One speaker, Stacked, Blended (two directions, width, position, swap), Auto,
  voice links, timeline corrections, camera-change confirmation, and explicit
  off-screen fallback are implemented. No automatic tracker is enabled.
- All four real export examples pass technical QA. One speaker: 12/12 sampled
  face checks. Stacked, Blended, Auto fallback: 24/24. Blended faces are outside
  the join. Stacked/Auto headroom is honestly marked too much at some moments.
- Current test-job voice IDs are unknown: Auto shows both and warns. Known-ID
  switching/overlap/minimum dwell is tested with timing fixtures, not claimed as
  measured real diarization accuracy.
- Native suite: **99 passed**, one existing warning. Real Windows Edge editor
  test passed, including actual visible source pixels and persistence. JavaScript
  syntax and security audit pass; the current audit checked **15,528 paths** and
  found zero findings. Linux pytest is unavailable.
- Feature-OFF export is **byte-identical** to the Task 1 MP4; evidence in
  `reports/speaker_frame/no_feature_regression.json`.
- A constructed real-imagery cut was measured at 2.0s and triggered the correct
  warning/wide fallback. Off-screen selection also uses Wide.
- Snapshot: `backups/after_task_2/`, with verified hashes. Full temporal blend
  quality, hairline headroom, platform safe zones, and real voice accuracy remain
  unmeasured; watch the full videos.
- Task 3 can proceed: the nine provided Duo videos are in
  `reference videos/duo style/`, with a space. The initial missing-underscore-path
  finding is superseded by this actual supplied folder.

## Task 1 — framing checkpoint — 2026-10-06

**The three requested framing fixes are built, rendered, and checkpointed.**
Full details and the exact three export paths are in
`reports/checkpoints/CHECKPOINT_1.md`. Open `reports/fix3/WATCH_TASK_1.html`
for links to the final videos and reference/before/after sheets.

- The main speaker is now a large single shot. The Christian-love clip now
  shows the questioner at the microphone clearly. The source split-screen seam
  is removed from the main view.
- Hash-checked local face/mouth tracking, calm holds, source-cut resets, and
  bounded camera paths are implemented. Unclear evidence falls back to wide.
- Header includes the genuine emblem, POLITICALLENS fallback wordmark, blue
  tick, and handle. The video window begins at the measured reference row 509.
  Captions use the reference row when face avoidance allows it.
- Each of the three final clips passes technical QA and has its selected face
  found inside the video-window inset in **12/12 sampled frames**. This does
  not certify every frame, every speaker turn, hairline headroom, or platform UI
  safe zones. Active-speaker accuracy remains **Not measured**.
- Native suite: **99 passed**, 1 existing warning. JavaScript syntax passed.
  Security audit: **15,528 paths checked, zero findings**. Linux pytest could
  not run because the system has no pytest; a separate system-Python unittest
  probe had 1 failure and 13 missing-dependency errors and is not counted as a
  pass.
- A saved preset without the new feature re-exported to a **byte-for-byte
  identical MP4**, including identical decoded video and audio hashes.
- Another supplied reference video was tested: camera checks pass; face inset
  measured **11/12**, with one ambiguous fallback sample. Its strict all-frame
  face check is not passed; this was a framing-only finished-reference test.
- Six final frames per clip and comparison sheets are saved under
  `reports/fix3/`. No filename/debug text is visible in those frames; all sampled
  footer dark-pixel counts are zero. The supplied filename appears to be a player
  overlay.
- `reports/fix3/WATCH_TASK_1.html` now links to the canonical `clip.mp4` in each
  export bundle. A local check resolved all **9/9** page links to existing
  files. Browser behavior was not measured.
- Remaining limits: missing production wordmark, fallback font/artwork
  differences, lower caption slots when needed, and unverified general speaker
  accuracy. These are documented in the checkpoint.
- Working code and assets are backed up to `backups/after_task_1/` with a hash
  manifest. Task 2 and Task 3 are not started at this checkpoint.

Studio restart from the project folder:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Open `http://127.0.0.1:8765/`.

## Fix Round 2 — final closeout — 2026-10-06

### Problem 1 — export names and finding finished videos: **PASSED**

- New exports use safe human-readable folders such as:
  `exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_01_okay-so-what-if-you-make-fun-of-a-white-person_7m55s-8m23s_c_a9ef26901548_f6f886c6/`.
- The video in that folder is named
  `01_okay-so-what-if-you-make-fun-of-a-white-person.mp4`.
- Each new bundle has `ABOUT_THIS_CLIP.txt` with source, time range, headline,
  rating, rights status, and publishing status.
- `exports/_LATEST/` contains the newest readable MP4 files.
- `exports/INDEX.html` lists old and new exports without deleting old folders.
  New bundle manifests keep the stable candidate ID.
- The Studio has **My exports** with thumbnail, title, time range, date, size,
  Play, Copy file path, and Open folder. Open folder is POST-protected and is
  refused in LAN mode; it is available only from the localhost Studio.

### Problem 2 — framing and zoom: **PARTIAL / HONEST**

- Added More options controls: Zoom in, Zoom out, Move left, Move right, Move
  up, Move down, Layout (Auto, Two people, Wide), and Reset framing.
- Added a live browser preview of the selected controls. The final renderer
  uses the saved framing controls.
- Added `framing_quality` to `export_report.json`: face evidence status, face
  safe-area status, camera movement speed, and zoom-change speed.
- The three final test exports pass the smooth-path checks and use safe wide or
  manual controlled framing. No non-uniform scaling is allowed.
- The face checks say **Not measured** where the active-speaker evidence is not
  verified. The system does not claim that an unmeasured face is safe. Human
  viewing is still needed for final face/headroom approval.
- Before/after frames are in `reports/fix2/framing/before/` and
  `reports/fix2/framing/after/`. Triptychs are in
  `reports/fix2/framing/comparisons/`.

### Problem 3 — captions: **PARTIAL / HONEST**

- Added More options controls: Bigger, Smaller, Higher, Lower, Highlight
  color, Style (Hormozi, Calm, Light), and Reset captions.
- Saved caption controls affect the render plan and final export.
- The three final exports pass caption timing, text fidelity, safe-slot,
  lossless caption A/B, active-color, caption-presence, and glow checks in
  their reports.
- Caption before/after frames are in `reports/fix2/captions/before/` and
  `reports/fix2/captions/after/`. Triptychs are in
  `reports/fix2/captions/comparisons/`.
- Reference-video frames are recorded under
  `reports/fix2/{framing,captions}/reference/`.
- The closest available local font is Montserrat ExtraBold. Exact font and
  pixel-level visual equality with the supplied references is **not claimed**.
  The clean full-size reference frame, platform screenshots, and independent
  human rating needed for that claim are still missing.

### Problem 4 — simpler UI and working Add video: **PASSED**

- The guided UI has the four labeled steps: Add video, Find clips, Review,
  Export.
- Add video now accepts a YouTube URL or selected file, asks for a plain rights
  choice, starts the same `dc run` pipeline, and shows Starting, Downloading,
  Listening, Finding clips, and Ready progress words.
- Recent jobs show source titles and hide test jobs unless **Show test jobs** is
  enabled.
- Normal clip cards show only the video, title, time, rating, warnings, and the
  three main actions. Less common features are inside **More options**.
- Empty states explain the next action. Rights and integrity warnings explain
  what the user should check.
- The local Add video endpoint was exercised with a mocked process launch and
  returned `200 started`; the real reviewed job pipeline was also rendered and
  verified below.

### Problem 5 — click feedback: **PASSED**

- Buttons immediately change to Saving…, Starting…, Searching…, Exporting…,
  or another plain busy word and are disabled during the action.
- Persistent green, yellow, and red messages stay visible until closed.
- Export progress shows Checking, Framing, Captions, Rendering video,
  Checking quality, Done, and elapsed time.
- Cards show Not reviewed, Approved, Rejected, Exporting, Exported, or Problem.
- Approve feedback was exercised in a real browser; the evidence screenshot is
  `reports/fix2/ui/after/approve-feedback.png`.
- The Activity area keeps the last 20 actions in browser storage.
- A red connection bar says: “The Studio stopped. Restart it in PowerShell.”
- The Studio prints a plain completion/error line in its PowerShell window for
  jobs started from Add video.

### Final three real exports

All three final test-job renders passed technical QA after the audio-normalize
and AAC true-peak headroom fix. They are:

1. `exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_01_okay-so-what-if-you-make-fun-of-a-white-person_7m55s-8m23s_c_a9ef26901548_f6f886c6/01_okay-so-what-if-you-make-fun-of-a-white-person.mp4`
2. `exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_02_but-my-question-is-how-can-christian-teaching-on-love_3m10s-3m38s_c_3b29c90cfa17_a17ccb77/02_but-my-question-is-how-can-christian-teaching-on-love.mp4`
3. `exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_03_all-that-matters-to-god-is-not-black-or-white-or-republi_5m21s-5m53s_c_9ecc907d1157_c86ca937/03_all-that-matters-to-god-is-not-black-or-white-or-republi.mp4`

The render evidence is in `reports/fix2/framing/after/render_*_final.txt` and
`render_c_a9ef26901548_controls.txt`. Each report says `status: passed`.

### UI evidence and verification

- Before screens: `reports/fix2/ui/before/`.
- After screens: `reports/fix2/ui/after/` including `classic.png`, `home.png`,
  `find.png`, `review.png`, `export.png`, `my-exports.png`, and
  `approve-feedback.png`.
- The older screenshot attempt was blocked by a missing Playwright browser
  executable. The current 2026-10-07 UI entry above supersedes that result with
  fresh native-Windows browser evidence.
- Native Windows full suite: **83 passed, 1 Starlette deprecation warning**.
- Security audit: **11,956 paths checked, zero findings** in
  `reports/current_checks/security_audit.json`.
- JavaScript syntax checks pass for the guided UI, classic UI, screenshot tool,
  browser fixture, and Fix Round 2 evidence tools.

### Exact Studio commands

```powershell
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Open:

`http://127.0.0.1:8765/`

Classic view:

`http://127.0.0.1:8765/classic`

The three final videos are local files. Rights for the reviewed source remain
`unknown`, so publishing remains blocked until rights are honestly verified.

## UI fix update — 2026-10-06 (historical; superseded by the 2026-10-07 entry above)

- **PASSED:** The Studio home page now has four clear steps: Add video, Find
  clips, Review, and Export.
- **PASSED:** The new home page has a clear add-video box, recent-job status
  rows, progress bars, plain status words, and simple help text.
- **PASSED:** Review cards now show a video player, plain title, source time,
  length, word rating, small score, plain reason, warnings, and big Approve,
  Reject, Edit start/end, and Export buttons.
- **PASSED:** Detailed score bars are behind “Why this score?” and Advanced.
  Unmeasured values say “Not measured.” Technical names are hidden from the
  normal card. Speaker text now says “Speaker: not identified yet” when needed.
- **PASSED:** Search is named “Find a moment” and has three example searches.
- **PASSED:** Blind Label mode is in Advanced with the plain explanation:
  “For testers. Hides the system's score so you can rate clips fairly.”
- **PASSED:** Less common controls are behind Advanced. The original UI is
  preserved at `/classic`.
- **PASSED:** Existing localhost, token, Origin, CSP, XSS, path, rights, and
  publishing rules remain in the server/API.
- **PASSED:** Native Windows test suite: **83 passed, 1 existing deprecation
  warning**. The required earlier 76 tests are included in this count.
  JavaScript syntax checks also pass for the new UI, classic UI, and screenshot
  and browser acceptance tools.
- **PASSED:** `tools/security_audit.py` checked 11,956 paths and found no
  symlink escapes, unsafe IDs, traversal acceptance, shell execution flags, or
  hard-coded source secrets.
- **PASSED:** `tools/studio_browser.cjs` now exercises both the preserved
  `/classic` review actions and the new guided `/` flow, including plain review
  text, approve, export navigation, and the text-node XSS fixture.
- **SUPERSEDED:** The first UI pass could not capture screenshots because its
  browser download timed out. Round 2 captured the before and after screens;
  the current evidence is in `reports/fix2/ui/`.

### Open the Studio

Run from the project folder:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Open this address:

`http://127.0.0.1:8765/`

The preserved old interface is at:

`http://127.0.0.1:8765/classic`

## Tier 1 instruction update

- **Item 1 — BLOCKED:** `reference image/clean_full_export.png` exists, but it
  is only 549×917 RGBA, not 1080×1920. It shows Political Lens-style header,
  headline, footage and footer, but it contains a visible source video overlay
  and is not a clean full-size frame for the SSIM gate. Please provide a clean
  1080×1920 frame.
- **Item 2 — BLOCKED (waiting for you):** no `assets/wordmark.png` or
  `assets/wordmark.svg` exists. No wordmark was made.
- **Item 3 — BLOCKED (waiting for you):** `reports/platform/` and the three
  safe-zone screenshots were not found. Safe zones remain conservative and
  unverified.
- **Item 4 — PASSED for file creation only:** all seven
  `reports/supplied_media/<media_id>/rights_attestation.json` files exist and
  validate. Each says `unknown`, user name `TODO`, evidence link `TODO`, and
  “Downloaded from YouTube. Rights not verified.” Unknown rights still block
  Auto and publishing.
- **Item 5 — BLOCKED:** `golden_links.txt` has six links, not seven. yt-dlp
  identified all six titles, but the first HLS download produced only a partial
  file and no usable full source. No speech/picture match was guessed. The
  evidence map is `reports/supplied_media/golden_source_map.json`; all seven
  shorts are currently marked `no match` pending full sources.

The exact Tier 1 file was requested as `OMNIRUSH_TIEER!.md`, which does not
exist. I followed the project-root `OMNIRUSH_TIER1.md` copy instead.

The Tier 1 rule “do not delete or change any file I did not name” prevents
further Group A code changes in this pass, because the remaining Group A work
would require editing files that Tier 1 did not name. Existing Group A
evidence remains unchanged below.

**Full V5 acceptance is still incomplete.** Engineering work remains in
Group A; it has not been moved into user-input or quality gates.
Detailed evidence: `reports/M13_report.md` and
`reports/requirements_traceability.md`.

## 1. Done — measured passes

- **Brand/reference:** the genuine supplied JPG is used directly. All five
  images and six reference videos were inspected. Original-artwork identity,
  twelve-frame chrome and all five header/hook position checks pass (**T-02**;
  `reports/supplied_media/`). The seven golden shorts are inventoried.
- **Captions:** licensed Montserrat ExtraBold is the closest tested fallback.
  The actual rendered RIGHT size/centre/glow pass **T-16/T-17**. Every protected token
  still has its own highlight; decimal/currency text is preserved.
- **QA:** all six actual encoded faults are flagged (**T-14**). Wrong-colour
  captions can no longer pass because of green footage. Physical 4 px feed-edge
  guards pass 12 real/pattern bleed cases at CRF 18/20/23 with the original
  chrome/white thresholds. The earlier failed case is kept in the reports.
- **Fairness/emoji:** an omitted identifiable opponent raises I-2 and blocks
  Auto (**T-19**). Missing fonts/glyphs drop the emoji and save a reason
  (**T-22**).
- **Native Windows:** 76 pytest tests pass. Actual setup, PowerShell Studio
  localhost/security checks, real moving render/QA, cancellation with no
  owned survivors, below-normal priority and awake release pass their recorded
  automated scope (**T-12/T-15/T-18**; `reports/native_windows/`).
- **Linux:** 76 pytest tests and the same 76 unittest cases pass. Current real
  guarded static render and final standalone QA pass. Compile/dependency/lock/
  JavaScript/scoped security checks pass; inputs stayed unchanged. Raw evidence
  is in `reports/current_checks_final/`.
- **Recovery/interop:** fresh real-model ASR kill/resume matches uninterrupted
  transcript/graph/candidates; real export-worker recovery preserves complete
  bundle hashes (**T-36**). Hash-verified checkpoints and strict hard-QA export
  refusal are tested. Official FCPXML DTD/25/30 fps/OTIO checks pass their format
  scope (**T-32**), not actual NLE application imports.

**Engineering still open (A):** full ASR/render stage contracts and retry/
telemetry, optional-model integration, narrative/AV/director/caption-slot work,
exact crossfade polish, full 60 s/VFR/craft/RTL/preview/security/performance checks
and publisher-session work. See `reports/open_gaps_ABC.md` for every item.

## 2. What you must give — checklist

- [ ] Separate production wordmark and one clean 1080×1920 reference frame.
  A transparent/higher-resolution original emblem is useful; your genuine
  supplied emblem is already used.
- [ ] Full raw-source relationships/cut maps and rights attestations for the
  golden material; finished shorts alone cannot show what was left out.
- [ ] Genuine word/name/framing/DER/query/candidate/blind-span labels and
  independent raters. Exact counts/rubrics are in
  `reports/supplied_media/golden_requirements.md`.
- [ ] Platform safe-zone screenshots and actual account/audit status when
  publisher testing is needed.
- [ ] Comparable Opus/Klap exports for the 10-source/3-rater bake-off; real
  channel decisions/analytics for learning. A recurring-name glossary is optional.

## 3. What cannot be proven yet

Selection recall/precision, word/name timing accuracy, speaker/safe-face/DER
targets, semantic gains, language quality, SSIM/exact style and competitor
superiority need genuine labels, clean references or independent reviews.
Whisper's measured speech coverage is not word accuracy. Green core tests do
not prove these quality gates. Learned layers remain gated.

## 4. Differences from the references

- The original emblem is a small opaque 200 px JPG, used without redrawing.
- The adjoining grey/red Anton wordmark is a fallback, not the missing asset.
- Montserrat is the closest tested font, not an identified CapCut Viral font.
  V5's calibrated 44 px target is kept; newer references sometimes look larger
  and use variable wrapping. Full dynamic wrapping/slot behavior remains A.
- `brand_check` deliberately differs from the reference's verified-style tick.
- Thin 4 px white guards occupy the feed edges; the feed/canvas coordinates and
  uniform footage scale remain unchanged. Human look approval is still needed.

## 5. Human acceptance gates still open

Use native Windows Studio and the phone queue; measure real manual steps.
Watch three exports, checking captions/faces/branding and the first/last 0.5 s.
Try actual overnight/low-battery use. Import timelines into the target NLE.
Complete real editorial/rights/claim review and independent ratings.

The supplied real source still has **unknown rights**. Publishing is blocked.
No live upload, human-acceptance pass or full-project completion is claimed.
