# TIER 1 INSTRUCTION FOR OMNIRUSH

Keep working in this same session. Do not stop the build over any single item.
If one item is blocked, note it, move on, and tell me at the end.

## GENERAL RULES

- Do not fake results. If you can't prove something, say so.
- Do not delete or change any file I did not name.
- Do not redraw or recreate any logo or wordmark.
- Never set rights to "own" or "permission". Use "unknown" unless I say otherwise.
- Use simple words.

## PROJECT PATH (WSL)

`/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`

## ITEM 1: CLEAN REFERENCE FRAME

File: `reference image/clean_full_export.png`

1. Check it is exactly 1080x1920.
2. Check it is clean: no captions, arrows, boxes or marks drawn on it.
3. Check it shows the Political Lens layout (logo, header, caption area).
4. If good, use it as the clean reference frame and update the report.
5. If something is wrong, tell me in simple words what to fix.

## ITEM 2: WORDMARK

File: `assets/wordmark.png` (or `assets/wordmark.svg`)

1. If the file exists: check it says "Political Lens", has a transparent background, and matches the logo style. Use it where V5 needs the wordmark.
2. If the file does not exist: mark it "missing, waiting for user". Do not make one. Keep building.

## ITEM 3: PLATFORM SAFE-ZONE SCREENSHOTS

Folder: `reports/platform/` (it may be named `PLATFORM` in capitals. Find it either way.)
Files (JPG is fine, do not make me convert them):
- `youtube_safe_zone.jpg`
- `tiktok_safe_zone.jpg`
- `instagram_safe_zone.jpg`

1. Check each screenshot.
2. Use them to set the safe areas for captions, logo and header for YouTube, TikTok and Instagram.
3. Tell me what you changed and what is still missing.

## ITEM 4: RIGHTS FILES

Create `rights_attestation.json` in each of these 7 folders under `reports/supplied_media/`:
- 58aeb69ed5b2ba88
- e54bcc72754290db
- b29ea28940d29326
- c39b2aaafa563f2c
- ba9ef1babda331f6
- a5f7e41589f9a086
- f4330a3bf5c47396

Use the format in MY_TODO.md and `reports/supplied_media/golden_requirements.md`.
- Rights type: "unknown" for all 7.
- My name and evidence link: "TODO".
- Note: "Downloaded from YouTube. Rights not verified."

Then check all 7 files are valid and tell me the result.

## ITEM 5: FULL ORIGINAL DEBATES

File: `golden_links.txt` in the project folder. It holds my guesses for the YouTube links. Some may be wrong. If the file has no links, skip this item and tell me.

1. Download each full video with yt-dlp into `input/golden_sources/`. Name them `golden_01.mp4`, `golden_02.mp4`, and so on. Keep each link in a text note.
2. For each of my 7 golden shorts, find where it comes from inside these videos. Match by speech and by picture.
3. Fill in `reports/supplied_media/golden_source_map.json` with the source video, start and end time, and cut spans. Mark each as "sure", "likely" or "no match".
4. For shorts with "no match", tell me what to search for on YouTube (speaker names, topic, title) so I can find a better link.
5. Do not guess a match without evidence.

## AFTER THE 5 ITEMS

1. Keep finishing every Group A engineering item. Do not wait for me.
2. Update `OMNIRUSH_FINAL_REPORT.md`. For every gate, say clearly: PASSED, BLOCKED (waiting for me), or OPTIONAL.

## SHORT REPORT TO ME (simple words)

1. Item 1 to 5: result of each, one line.
2. What I must still give you.
3. Which shorts have no matching full video yet.
