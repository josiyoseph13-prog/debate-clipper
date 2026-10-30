# OMNIRUSH UI FIX V2 — "Debate Clipper" Studio

Read this whole file first. Do the 8 fixes in order.

## THE DESIGN TO FOLLOW (very important)
The user designed a clickable prototype with Claude. It is saved as **`design/debate_clipper_ui_prototype.html`** (the user copies it into the project folder; open it in a browser and click through every screen, including Edit > Speaker Frame > Duo style).
- Build the real Studio to look and work **like this prototype, but BETTER**: more polished, smoother, faster, more beautiful, and more complete. The prototype is the minimum, not the ceiling.
- Keep its layout, its plain-English words, its 4 steps, its colors and its feel. Where it is rough or faked (pretend clips, pretend progress, pretend timeline), build the REAL version using real data.
- Where you can improve the design (spacing, animation that answers a click, icons, empty states, error states, keyboard use, dark mode, small screens), improve it, as long as it stays simple for a beginner.

## USE ANY MEANS NEEDED (permission granted)
You may install any tool, library or plugin that helps make the UI better, faster or more beautiful. Examples: UI component libraries, icon sets, a CSS framework, a video-player library, a drag-and-resize library for the boxes, a charting or timeline library, a test browser tool (Playwright) for screenshots. Rules:
1. Check the license of every package. Flag AGPL, GPL or unclear licenses as "Careful" and do not use them without asking the user.
2. Pin versions. Install only inside the project (the UI's own environment or `node_modules`), never change system-wide settings.
3. The Studio must still work fully offline on the user's PC. Bundle everything locally. No online CDN, no cloud calls, no sending the user's videos or data anywhere.
4. Installing UI packages must NOT change exported video output (the byte-for-byte check in the Ground rules still applies).
5. Write every package you added (name, version, license, why) in `reports/ui_fix2/dependencies.md`.

Do the 8 fixes in order. Do not stop or restart the project. Keep solving gaps you can solve alone.

## Ground rules (same as always)
- Never fake results. If something is not measured or not proven, write "Not measured" or "Cannot be proven yet".
- Never mark a fix "done" without a test ID, a QA hook, and an off-switch where it makes sense.
- This task changes the Studio screen only. It must NOT change exported video output. After finishing, prove it: export the same clip as before and confirm the MP4 is byte-for-byte identical to the previous export.
- Keep the old screens available at `/classic`. Do not delete anything.
- Do not run the full pipeline again just to test the UI. Use existing jobs (for example `job_863e97df620d`) and the existing exports.
- Before you start, make a code backup at `backups/before_ui_fix_v2/`.

---

## FIX 1 — Only one video plays at a time
Problem: When the user opens or plays a second video, the first video keeps playing. Both play together.

Do:
1. Find every video player in Studio (clip cards, review page, My exports, Speaker Frame preview, Duo timeline preview).
2. Add ONE shared rule: when any video starts playing, every other video is paused immediately.
3. When the user leaves a page, closes a clip panel, or opens another clip, pause and unload the old video.
4. Also pause videos that are scrolled out of view.
5. Test it in a real browser (Edge on Windows): start video A, start video B, confirm A is paused. Save the test as a named test (example `UI-V2-01`) and put a screenshot or log in `reports/ui_fix2/`.

---

## FIX 2 — COMPLETE UI REDESIGN: simple, easy, beginner-friendly (style base: Descript)
Problem: The screen is messy and hard to understand. The user wants the UI changed COMPLETELY, not tidied up.

IMPORTANT: Do NOT patch or rearrange the current screen. Throw away the current layout and BUILD NEW SCREENS FROM SCRATCH. Keep all the working features and backend, but the screens, layout, labels and buttons are all new. The old UI stays only at `/classic`.

Style base: **Descript** (descript.com): calm, lots of white space, very few things on screen, one clear action at a time. Layout idea for the clip list: **Riverside.fm**.
- Copy the STRUCTURE and CALM FEEL only. Do NOT copy logos, icons, brand colors, text or protected assets.

Design rules (apply to every screen):
1. The user is a complete beginner. Anyone should understand the screen in 5 seconds without reading a manual.
2. ONE big main button per screen, always the obvious next step (example: "Find clips", "Review clips", "Export"). It is the biggest and most colorful thing on the screen.
3. Maximum 5 things visible at once on any screen (not counting the clip list). Everything else is hidden behind "More options".
4. Plain words only. No codes, IDs, scores, or technical terms on the main view. Examples: say "Great clip", not "0.87"; say "Make the video" not "render"; say "Your video file" not "source".
5. One font, big text (at least 16px), 2 colors plus neutral, big click targets, lots of space. No tiny text, no crowded panels.
6. Always show "Step X of 4" at the top and a "What do I do next?" sentence in plain words.
7. Every button gives instant feedback (spinner, then a clear message).
8. A "Help" button on every screen opens a short plain explanation (5 lines max).

The 4 new screens:

**Screen 1: Add video**
- One big box: "Paste a YouTube link or drop a video file here".
- One big button: "Find clips".
- "More options" (closed): rights choice, number of clips. Rights default stays "unknown".

**Screen 2: Finding clips**
- Big progress bar with a real percent number and a plain sentence ("Downloading… 42%", "Listening to the debate… 65%").
- No other buttons except "Cancel".

**Screen 3: Review clips**
- Left: simple list of clips. Each row = small picture, short title, length, one word (Great / Good / Okay / Weak).
- Center: ONE big video player for the selected clip (only one video plays at a time).
- Right: 4 big buttons only: **Approve**, **Reject**, **Edit**, **Export**.
- "Edit" opens a clean side panel with 3 tabs only: **Framing**, **Captions**, **Speaker Frame**. Each tab shows 3-4 options at most, with a small preview picture and one plain sentence under each option. Advanced stuff is under "Advanced" (closed).
- "Why this score?" is a small link, never shown by default.

**Screen 4: Export done**
- Big green message: "Your clip is ready".
- Three big buttons: **Play**, **Open folder**, **Copy file path**. Show the readable file name.
- Link: "Back to my clips".

Also:
- "My exports" page: same calm style, simple list with Play / Open folder.
- Hide test jobs and technical jobs from the normal view.
- First-time hint on each screen (one sentence, can be closed, never shown again after closing).
- Fast: show the screen first, load pictures and videos after (see Fix 3).

Evidence:
- Before/after screenshots of every screen in `reports/ui_fix2/`.
- Write `reports/ui_fix2/UI_SIMPLICITY_CHECK.md` with, per screen: number of visible controls, the main button, the number of clicks needed to go from pasting a link to an exported clip, and any technical word still visible. Target: 5 or fewer visible controls per screen; 10 or fewer clicks for the whole path.
- You cannot test with real people. Write "Not tested with real beginners" in the report. The user will judge by eye.

---

## FIX 3 — Make it faster
Problem: The app feels slow.

Do:
1. Measure first. Record how long these take today: opening Studio, opening a job, opening the Review page, opening a clip, clicking Approve, starting Export. Save as `reports/ui_fix2/speed_before.md`.
2. Fix the biggest slowdowns you can find (examples: load clip list first and thumbnails later, lazy-load videos only when clicked, cache thumbnails, avoid reloading the whole page after a click, avoid heavy work on the main thread).
3. Do NOT lower exported video quality to gain speed. UI speed only. Preview videos may use a lighter proxy, but exports must use the original quality path.
4. Measure again after. Save `reports/ui_fix2/speed_after.md` with real before/after numbers. If something did not get faster, say so.
5. The user said "not fast enough" and may also mean the WAITING time for Find clips and Export, not only the screen. So also measure how long each processing stage takes (download, transcribe, find clips, render/export) on one existing job and save it in `speed_before.md`. Then:
   - Apply only safe speedups that keep the exported MP4 byte-for-byte identical (example: reuse results already computed, skip repeated work, run independent steps in parallel).
   - For any bigger speedup that WOULD change the output (lower quality, different encoder settings, skipping checks), do NOT apply it. List it in the report as an option for the user to approve.
   - Show the user which stage is the slowest, in plain words.

---

## FIX 4 — Speaker Frame: same features, much easier to understand
Problem: The user liked Speaker Frame but could not understand the options.

Do:
1. Keep every feature (manual boxes, layouts One speaker / Both stacked / Both blended / Auto, Blend layout controls, Duo style, timeline editor). Remove nothing.
2. Add a simple **step-by-step guide inside the tool** (3 steps max):
   - Step 1: "Pick how you want it to look" (show small picture previews of each layout, not just words).
   - Step 2: "Check the boxes around each person" (one sentence on what a box is).
   - Step 3: "Preview and save".
3. Rename confusing options into plain words. Show a one-line explanation under each option. Examples: "Blend width" → "How soft the join between the two people is". "Min shot length" → "Shortest time before switching person".
4. Put advanced options (timeline editor, Duo sliders, blend position, swap sides) behind a button called "Advanced". Closed by default.
5. Add a "Reset to Auto" button and a "?" help icon next to each option.
6. Show a live preview that updates while the user changes an option, so they can see what each option does.
7. Add a "Beginner mode" (default ON) that shows only Step 1–3. Turning it off shows Advanced.

---

## FIX 5 — Real progress number (0 to 100)
Problem: It only says "reload" or similar. The user wants a number from 0 to 100 that reaches 100 when finished.

Do:
1. Every long job (download, Find clips, Export) shows a progress bar with a **percent number**: 0% → 100%.
2. Show the current step name next to it in plain words (example: "Downloading video… 42%", "Finding clips… 65%", "Exporting… 90%").
3. The number must be REAL: based on actual work done (bytes, frames, steps finished). Never a fake timer.
4. If the real percent cannot be known for a step, show "Working…" with an animated indicator and say so honestly. Do not invent a number.
5. Only show **100%** when the job is truly finished and the result file exists. Then show a clear green "Done" message.
6. If the job fails, show the percent where it stopped and a red plain-English message.
7. Keep the number updating without the user pressing reload. If the connection drops, show a clear "Connection lost, reconnecting" banner.
8. Add tests for 0%, middle, 100%, and failure. Save to `reports/ui_fix2/`.

---

## FIX 6 — Name in the interface: "Debate Clipper"
Problem: The Studio shows "Political Lens". That is only one of the user's TikTok channels.

Do:
1. Everywhere in the Studio interface (title, browser tab, header, footer, page titles, messages, INDEX.html, My exports page) use **Debate Clipper**.
2. Do NOT remove Political Lens from the exported videos. The header, emblem, wordmark, and handle inside the exported clips stay exactly as they are.
3. Search the whole project for the text "Political Lens" in UI files and templates, and list each place you changed in `reports/ui_fix2/name_changes.md`. List the ones you left alone on purpose (export branding) and why.
4. Optional: add a setting "Channel branding for exports" so the user can later choose another channel brand. Keep it simple and off the main screen.

---

## FIX 7 — Edit panel must sit NEXT TO the video (edit while watching)
Problem: When the user presses **Edit**, the edit options appear BELOW the video, so the user cannot see the video while editing. It must be possible to edit and watch the video at the same time.

Do:
1. Pressing **Edit** opens the edit panel on the **right side, next to the video**. The video stays visible and stays in place (sticky) the whole time. Do not push the video up or make the user scroll to see it.
2. While editing, hide the clip list and the Approve / Reject / Export buttons, and show a clear **Done** button at the top of the edit panel. Done closes the panel and brings the normal layout back.
3. Every change shows **instantly in the video preview** (caption size, caption color, framing, layout, box moves, Duo timeline moves). No need to press Save to see it.
4. On a small screen, keep the video pinned at the top and put the edit panel under it, scrolling by itself. The video must never scroll out of view while editing.
5. The edit panel scrolls on its own if it is long. The page itself does not jump.
6. Test it in the real browser at a normal laptop size and a small size. Save screenshots `reports/ui_fix2/edit_side_by_side_*.png`. Test ID `UI-V2-07`.

---

## FIX 8 — Speaker Frame and Duo style features shown in the prototype
Build all of these for real (not just the picture). See the prototype's Speaker Frame tab.
1. Four layouts with small picture icons: **One person, Both blended, Both stacked, Duo style**.
2. **Editable boxes for BOTH people**: show boxes on the video, drag a box to move it, drag its corner to resize it, or use the buttons (left, right, up, down, Smaller, Bigger, Reset boxes). Choose Person A or Person B. A **Swap people** button. The video follows the boxes live.
3. **Duo style settings** in plain words: "When does it jump to one person?" and "Shortest time on one shot".
4. **Go full screen on one person in the middle of the video**: the user picks a moment, who (Person A, Person B or Back to both) and how long (2 sec, 4 sec, 8 sec, until the end). The user's manual choice always wins over the automatic guess.
5. **Timeline blocks** (Both / Person A / Person B). Click a block to see that moment in the preview, click again to change it. The automatic version comes from the real audio guess; label it "This is a guess from the audio. Check it by eye." Never fake it.
6. **Beginner mode** as the default: only Step 1 (pick look), Step 2 (check boxes), Step 3 (preview and save). Advanced stays closed.
7. Test IDs `UI-V2-08` to `UI-V2-12`. Speaker Frame OFF must still export a byte-identical video to before.

---

## FINISH
1. Run all tests (Windows native). The test count must not go down. Report the number.
2. Run the Edge browser test, including the new screens. No JavaScript errors allowed.
3. Run the security audit again. Report the result.
4. Prove exported video is unchanged (byte-for-byte check on one clip).
5. Backup to `backups/after_ui_fix_v2/` with a manifest.
6. Write the final report at `reports/ui_fix2/UI_FIX_V2_REPORT.md` with:
   - A table: Fix 1–8, status (Passed / Partial / Not done), test ID, evidence file.
   - Real before/after speed numbers.
   - What still needs the user to check by eye.
   - Anything you could not prove, in plain words.
7. Tell the user, in short plain language, how to restart Studio:
   `work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765`
   and open `http://127.0.0.1:8765/`.

If your context or memory runs low, stop safely and write `reports/ui_fix2/RESUME_HERE.md` with exact instructions on where to continue.
