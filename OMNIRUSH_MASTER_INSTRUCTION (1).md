# MASTER INSTRUCTION FOR OMNIRUSH (V5 BUILD)

Keep working in this same session. Do not stop or restart the project.
Do not stop the build over any single problem below. If one thing is blocked, note it, move on, and tell me at the end.

## GENERAL RULES

- Do not fake results. If you can't prove something, say so.
- Do not mark anything "implemented" without a test ID, QA hook, or off-switch.
- Publishing blocked when rights are unknown is correct behavior. Keep it.
- Do not invent new requirements. Work from MASTER_BUILD_PLAN_V5.md, your traceability matrix (T-01 to T-36), and the files I give below.
- Use simple words in your reports.

## PATHS (WSL)

- Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`
- Logo: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper/dd12b684ebfbbd0a60845e8ecdb5c13e~tplv-tiktokx-cropcenter_1080_1080.jpg`
- Reference images: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper/reference image`
- Reference videos: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper/reference videos`
- Golden accuracy videos: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper/golden accuracy video`

## PROBLEM 1: LOGO

The file above is the real Political Lens logo, not a placeholder.

1. Inspect the image.
2. Check if it contains the logo/wordmark that MASTER_BUILD_PLAN_V5.md needs.
3. Use it in the branding/export pipeline wherever V5 requires the logo.
4. Do NOT redraw, recreate, or replace it with an approximation.
5. Keep its look as close as technically possible.
6. Check the real rendered video shows the logo correctly.
7. Update the report so this item is no longer "missing" if it passes.

Note: it is a cropped square JPG. If V5 needs a clean transparent logo, tell me clearly, and keep going.

## PROBLEM 2: REFERENCE IMAGES

Inspect every image in the reference image folder. Use them as the visual specification (layout, caption style, safe zones, branding placement).
They are NOT video overlays. Do not paste them onto the output.

## PROBLEM 3: REFERENCE VIDEOS

These are real, manually edited Political Lens videos. They are style and quality references, NOT rigid templates.

- Study what is the same across all the videos (the design language).
- Do NOT copy one video's exact crop, caption line breaks, timing, or framing onto every future clip.
- Differences between debates and speakers are normal.

## PROBLEM 4: GOLDEN ACCURACY VIDEOS

These videos are for testing whether Debate Clipper makes correct automated decisions (speaker choice, framing, clip quality, captions, ranking). Do NOT copy their editing.

- Build measurable expected results from them.
- Tell me exactly what labels (correct answers), rights attestations, and independent raters V5 needs for the accuracy gates.
- If labels or raters are missing, mark the gate "cannot be proven yet." Do not make up a score.

## PROBLEM 5: WINDOWS ACCEPTANCE

You run in WSL (Linux). A Linux test alone does not prove the app works on native Windows.

- Detect whether you are in WSL or native Windows.
- Test whether you can call Windows programs from WSL (powershell.exe, cmd.exe). Do not assume it works.
- If it works, run real end-to-end tests on the Windows side.
- Do not claim "Windows acceptance passed" unless you truly ran and checked the Windows environment.
- If a test needs a human (clicking the UI, watching the final video), record it as a "human acceptance gate." Do not pretend it passed.

## PROBLEM 6: CAPTIONS AND FONTS

Use the Political Lens reference images and videos as the visual authority.
Do not assume Poppins, Anton, or any other named font is correct, even if the V5 doctor lists it. The original edits were made in CapCut using the Viral style, so the exact font is unknown.

Reproduce the Hormozi-style captions seen in the references:

- Heavy, bold ALL-CAPS text
- White main text
- Thick, high-contrast black outline
- Word-by-word highlighting in bright neon green (match the reference)
- Easy to read over moving footage
- Placement follows the Political Lens reference
- Line wrapping and size adapt to each spoken sentence, not one fixed layout

Find the closest legally usable or local font and render settings that match by appearance. Montserrat Black, Anton, and Bebas Neue are common for this style, but they are hints only. If an exact match can't be verified, use the closest fallback and report the difference clearly.

## PROBLEM 7: FIND YOUR OWN GAPS

Review your V5 traceability matrix (T-01 to T-36) and your latest report.

1. List every item that is still open, partial, or blocked.
2. Sort each item into one group:
   - A. You can finish it yourself. Do it now, without waiting for me.
   - B. It needs something from me (files, rights attestations, Windows testing, human review).
   - C. It cannot be proven yet (for example, accuracy tests with no labels).
3. Keep building. Finish group A first.

## PROBLEM 8

(Empty. Nothing to do.)

## ORDER OF WORK

Problems 1 to 6 first, then Problem 7. Keep building the whole time.

## FINAL REPORT (short, simple words)

1. Done: what passed, with test IDs or evidence.
2. What I must give you: a simple checklist.
3. What cannot be proven yet, and why.
4. Differences: any font, logo, or style difference from the references.
5. Human acceptance gates still open.

Write this report to a file named `OMNIRUSH_FINAL_REPORT.md` in the project folder.
