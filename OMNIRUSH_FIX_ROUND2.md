# FIX ROUND 2: NAMING, FRAMING, CAPTIONS, SIMPLE UI, CLICK FEEDBACK

I used the Studio and exported a real clip. Here is what is wrong. Fix all 5 problems.
Use simple words in the screen text and in your reports.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`
Test job: `job_863e97df620d` (8 clips, already reviewed by me)

## RULES

- Keep every V5 feature. Hide advanced things instead of deleting them.
- Keep all security rules (localhost only, XSS and path-traversal protection, rights and integrity blocks).
- Do not break the tests. Run all tests at the end and show the result.
- Do not fake results. Prove every fix with before and after pictures or videos.
- The Political Lens reference images and reference videos are the visual authority for look and quality. Do not copy one video exactly. Match the quality and design language.
- Do not stop the build over one problem. If one is blocked, note it and move on.

---

## PROBLEM 1: I CAN'T TELL WHICH EXPORTED FILE IS WHICH

Right now the exports folder is hard to read. I can't tell which clip is which.

Fix:
1. Give every export a clear, human name, for example:
   `exports/2026-10-06_<short-video-name>/clip_01_<clip-title>_12m40s-13m25s/clip.mp4`
   Use only safe characters. Keep the stable ID inside the folder (in `bundle_manifest.json`) so nothing breaks.
2. Make the exported video file itself have a readable name, for example `01_<clip-title>.mp4`, not only `clip.mp4`.
3. Add a simple `README.txt` or `ABOUT_THIS_CLIP.txt` in each export folder in plain words: source video, time range, headline, rating, rights status, and whether publishing is allowed.
4. Make one easy folder, `exports/_LATEST/`, that holds the newest finished videos with the readable names, so I can find them at once.
5. Make an `exports/INDEX.html` (or `INDEX.md`) that lists every export: thumbnail, title, time range, date, status, and a link to open the video.
6. In the Studio, add a page called **My exports**. For every export show: thumbnail, title, time range, date, size, a play button, a **Copy file path** button, and an **Open folder** button. Make Open folder work safely on localhost only.
7. Old exports: keep them, and give them readable names in INDEX without breaking hashes. Do not delete anything.

---

## PROBLEM 2: FRAMING AND ZOOM NEED WORK

Some exported clips have wrong framing or wrong zoom. I want the speaker framed like in my reference videos.

1. Open the exported clips from `job_863e97df620d` and my reference videos. Take frames at the start, middle and end of each clip. Save them in `reports/fix2/framing/before/`.
2. Find what is wrong. Check: face too small or too large, face cut off at the edge, too little or too much headroom, speaker not centered, wrong person followed, camera jumping or shaking, zoom changing too fast, zoom too tight on a wide shot, black bars, stretched picture.
3. Fix the framing logic using the reference videos for guidance:
   - Keep the active speaker's face fully inside the safe area, with natural headroom.
   - Use smooth, slow camera moves. No sudden jumps. Limit how fast the zoom and the pan can change.
   - Choose a sensible zoom level for each shot, tight enough to read the face but not so tight that it looks cropped.
   - Follow the real speaker. If speaker or face evidence is weak, use a safe wide or two-panel layout instead of guessing.
   - Never stretch or squash the picture.
4. Add framing controls in the Studio under **Advanced**, in simple words: Zoom in, Zoom out, Move left, Move right, Move up, Move down, Layout (Auto, Two people, Wide), and a **Reset** button. Show a live preview before export.
5. Add a framing quality check: face visible, face in safe area, no jump over a set limit, zoom change within a set limit. Show the results in plain words in `export_report.json` and on the card.
6. Re-export the same clips. Save frames in `reports/fix2/framing/after/` and make side-by-side images (reference vs before vs after).

---

## PROBLEM 3: CAPTION QUALITY IS NOT AT THE LEVEL I EXPECT

The caption style is right (Hormozi style) but the quality is not as good as my reference videos.

1. Compare my caption frames with the reference videos at the same moments. Save them in `reports/fix2/captions/before/`.
2. Find what is different. Check: text size, thickness of the black outline, glow, exact position, line breaks, space between lines, word highlight timing (highlight must land exactly when the word is spoken), colors, letter spacing, font weight, capital letters, text jitter, text overlapping faces or the logo, captions hidden behind the platform buttons, and spelling mistakes.
3. Fix the rendering until it matches the reference quality:
   - Sharp, clean edges. No blur or shimmer.
   - Smooth word-by-word highlight with no flicker, and no more than a tiny delay from the spoken word.
   - Smart line breaks: 2 short lines at most, break at natural phrases, never leave one lonely word where it can be avoided.
   - Keep captions inside the safe zones for YouTube, TikTok and Instagram.
   - Move captions away from faces and from the logo.
   - Fix spelling of names. Use `config/glossary.json` if it exists.
4. If the closest local font still looks different from the reference, say so. Show the difference. Do not claim it matches.
5. Add simple caption controls under **Advanced**: Bigger, Smaller, Higher, Lower, Highlight color, Style (Hormozi, Calm, Light), and a **Reset** button. Show a live preview.
6. Re-export. Save frames in `reports/fix2/captions/after/` and make side-by-side images (reference vs before vs after).

---

## PROBLEM 4: THE UI MUST BE SIMPLER

1. Show only what a first-time user needs. Everything else goes behind **Advanced**.
2. Use the 4 steps with clear WORDS on the buttons, not only numbers: **1 Add video, 2 Find clips, 3 Review, 4 Export**. Always show the current step, and one big button for the next step.
3. The Add video step: make the paste box and **Find clips** button WORK. When I paste a YouTube link or choose a file, start the same job that `dc run` starts. Ask for the rights word with a simple dropdown (default: "Not sure"), explain each choice in one line, and show progress with plain words: Downloading, Listening, Finding clips, Ready. If the app cannot do it, say why in plain words. Keep security rules.
4. Recent jobs: show the video title, not `job863e97df620d`. Hide old test jobs ("native_windows_cancel_acceptance" and similar) behind a **Show test jobs** switch.
5. Clip cards: one clear card with the video, title, time range, rating in words, and three big buttons: **Approve**, **Reject**, **Export**. Everything else is in **More options**.
6. Every empty screen says what to do next. Every warning says what to do about it.
7. Clean, roomy, readable layout in the Political Lens colors. Works on a laptop and a phone browser.

---

## PROBLEM 5: I CAN'T TELL IF A CLICK WORKED

When I click Approve, Reject, Export, Find or Save, nothing tells me if it worked. Fix this everywhere.

1. **Instant feedback.** The moment I click, the button shows it was clicked: it turns into a spinner with a word ("Saving...", "Exporting..."), and is disabled so I can't click twice.
2. **Clear result messages.** When done, show a big message at the top of the screen:
   - Success (green): "Exported. Your video is ready." with the file name and buttons **Play**, **Open folder**, **Copy path**.
   - Error (red): what went wrong in plain words and what to do next, plus a **Show details** button.
   - Warning (yellow): "Exported, but check these things: ..."
   Keep the message on screen until I close it. Do not let it vanish after 2 seconds.
3. **Export progress.** Show steps with a progress bar and a plain label: Checking, Framing, Captions, Rendering video, Checking quality, Done. Show elapsed time. If it takes long, say "This can take a few minutes. You can leave this page open."
4. **Clip state badge on each card.** Always show one badge: Not reviewed, Approved, Rejected, Exporting, Exported, Problem. The badge must change at once when I click.
5. **Approve and Reject** must show "Saved" and change the card color or badge.
6. **Step 4 Export page:** list every approved clip with its state and, when finished, its Play, Open folder and Copy path buttons.
7. **Notifications log:** a small **Activity** list that shows the last 20 actions with time and result, for example "10:42 Exported clip 3: success".
8. If the page loses connection to the Studio, show a red bar: "The Studio stopped. Restart it in PowerShell."
9. Also show the same success or error lines in the PowerShell window with plain words.

---

## HOW TO WORK

1. First read the current code and save screenshots of every screen into `reports/fix2/ui/before/`.
2. Show me a short plan (10 lines).
3. Fix the problems in this order: 5 (click feedback), 1 (naming), 4 (simple UI), 3 (captions), 2 (framing). Keep going if one is blocked.
4. After each problem, run the related tests.
5. At the end, run ALL tests (Linux, and Windows if you can call powershell.exe). Show pass and fail counts.
6. Re-export 3 clips from `job_863e97df620d` with the new code. Tell me the exact file paths so I can watch them.
7. Save new screenshots in `reports/fix2/ui/after/`.
8. Update `OMNIRUSH_FINAL_REPORT.md`. Mark each fix as PASSED, PARTIAL or BLOCKED, with evidence.
9. Write a short summary in simple words:
   - What I fixed
   - What is still not good enough (be honest)
   - Where to look (the 3 re-exported clips and the before/after pictures)
   - The exact commands to restart the Studio
