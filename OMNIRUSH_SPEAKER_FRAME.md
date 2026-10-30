# NEW OPTIONAL FEATURE: SPEAKER FRAME (PHASES 1 AND 2)

Build an OPTIONAL tool called **Speaker Frame**. I use it only when a clip needs it.
It must never get in the way of the normal flow.
Use simple words in the screen text and in your reports.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`

## RULES

- **It is optional and OFF by default.** The normal flow (Approve, then Export) must work exactly as before when I do not use it.
- Keep all V5 features, tests and security rules (localhost only, XSS and path-traversal protection, rights and integrity blocks).
- Do not break the existing tests. Run all tests at the end.
- Do not fake results. If a measurement is not possible, say "Not measured."
- Never name a person from their face. I type the names myself.
- Match the Political Lens layout in `reference image/` (header, headline, video window, white areas). Do not change the header or branding.
- Do not stop the build over one problem. Note it and keep going.

## WHERE IT FITS: AFTER AUTO REFRAME

The order for every clip is:

1. **Auto Reframe runs first**, by itself, like it does now. It makes the first framing and the preview.
2. I look at the result in the clip card.
3. **If the framing is good**, I approve and export. Speaker Frame is never used.
4. **If the framing is wrong or unsure**, I click **Speaker Frame** to correct it.

Rules for this order:
- Speaker Frame starts from what Auto Reframe already chose. When I open it, show the boxes and layout that Auto Reframe used, so I can fix them instead of starting from zero.
- If Auto Reframe found faces, show them as suggested boxes that I can accept, move or delete. Mark them "Suggested by Auto Reframe."
- Add a **Back to Auto Reframe** button that removes my changes and returns to the automatic result.
- In the clip card, show which one is active: "Framing: Auto" or "Framing: Speaker Frame (edited by you)."
- If I re-run Auto Reframe on a clip that has Speaker Frame, ask me first: "Keep your Speaker Frame changes or replace them?"
- Auto Reframe must not be slowed down or changed by this feature.

## WHEN IT SHOULD APPEAR

1. On every clip card, under **More options**, add a button: **Speaker Frame**. It does nothing until I click it.
2. Show a small yellow hint on a clip card only when it is really needed:
   - the system is not sure who the speaker is, or
   - two people matter in the clip, or
   - the framing check says "face not safe" or "Not measured".
   The hint says: "Framing may be wrong. Try Speaker Frame." It never opens by itself.
3. Add a switch in Settings: **Show Speaker Frame hints** (default ON for hints, but the tool itself is always opt-in).
4. If I never click it, the clip is exported the normal way.

## PHASE 1: MANUAL SPEAKER BOXES

When I click **Speaker Frame**:

1. Show a frame picker: the clip's video with a slider. I choose a frame where the speakers are visible.
2. Let me **draw a box** around each speaker's face and upper body. Up to 2 speakers for now. Let me move, resize and delete boxes.
3. Let me **type a name** for each box (for example "Host", "Guest"). Names are labels only.
4. Let me choose a layout:
   - **One speaker:** show one chosen speaker, large, with natural headroom.
   - **Both (stacked):** two panels, one above the other, like the screenshot I gave you. Each panel shows one face large, inside the safe area. No stretching or squashing.
   - **Auto:** (Phase 2) switch by who talks, and show both when both talk.
5. Show a **live preview** of the result in the video window, using the Political Lens layout. Show where the safe area is.
6. Buttons: **Save**, **Reset**, **Cancel**. After clicking Save, show a clear message: "Speaker Frame saved for this clip." Show a small badge on the clip card: "Speaker Frame: ON".
7. When I export, the renderer uses these boxes. Save them with the clip so I can open and change them later.
8. Smooth movement only. No sudden jumps. Keep the face inside the safe area. Never stretch.

## BLEND LAYOUT (TWO PEOPLE, SOFT JOIN)

Add one more layout choice: **Both (blended)**. I will give you a picture of what I want: two people side by side, left and right, where the two shots melt into each other in the middle with a soft fade, with no hard line between them. The caption sits in the middle of the frame.

Rules:
1. Both (blended) is a layout I choose under Speaker Frame. It is never used unless I choose it. Layouts are now: One speaker, Both (stacked), Both (blended side-by-side), Auto.
2. Blend style: the left person fades into the right person across a soft gradient strip in the middle. Use a smooth mask, not a hard edge and not a sudden cut.
3. Give me simple controls with a live preview:
   - **Blend width:** Softer / Sharper (default medium).
   - **Blend position:** Move the soft join left or right.
   - **Swap sides:** put Speaker A on the right instead of the left.
   - **Direction:** Side by side (default), or Top and bottom with a soft fade.
4. Keep both faces **outside** the blend strip. The strip must never cover a face. If a face would be in the strip, show a yellow warning: "A face is in the blend area. Move the join or choose Stacked." and do not hide it.
5. Each person gets about half the width, so crop each box into a tall strip. Keep each face large enough to read, with natural headroom. Never stretch or squash. If the source resolution is too low to keep both faces sharp, say so in plain words and suggest the Stacked layout.
6. Show the same Political Lens header, headline and layout as the reference. Only the video window content changes.
7. Captions stay in the position that the reference uses, over the join, readable, and not over faces if the position can be moved.
8. The Auto mode (Phase 2) can use the blended layout when both people talk, if I chose "Use blended when both talk." Short interruptions must not flip the layout.
9. Test the blend on a real two-person clip: check the soft join has no flicker, no visible seam, no color jump, and the faces stay clear. Save before and after frames in `reports/speaker_frame/blend/`.

## PHASE 2: SWITCH BY WHO IS TALKING

Only inside Speaker Frame, when I choose **Auto**:

1. Use the speaker turns from the audio (diarization) that the pipeline already makes.
2. Show me a small box: "Which voice is which?" Play a short sample of each voice and let me link each voice to one of my boxes. I do this once per clip.
3. Then the app does this:
   - One person talks: show that person (large).
   - Both talk for a meaningful time: show both stacked.
   - Short interruptions are ignored. Use a minimum shot length of about 1.5 seconds and a short smooth transition. Do not flip back and forth.
4. If the audio is not clear (crowd noise, overlap), choose the safe layout and tell me: "Audio unclear. Showing both." Do not guess.
5. Show a timeline under the preview that marks who is shown at each time (colored bars: Speaker A, Speaker B, Both). Let me click the timeline to fix a moment by hand: choose A, B or Both for any time range.

## CAMERA CUTS (SAFE HANDLING FOR NOW)

My source videos are live outdoor debates. The camera moves and cuts between angles, so a box drawn on one frame can become wrong.

1. Detect camera cuts in the clip.
2. At each cut, mark the timeline: "Camera changed here." Keep the old boxes only if the shot looks the same. If not, show a yellow warning: "Camera changed. Check the boxes," and let me set new boxes for that part.
3. If a speaker is not on screen (for example a student at a microphone who is out of frame), do not invent a face. Use the wide shot, or the other speaker, and say so.
4. Do not build full automatic tracking now. If you try a simple tracker, mark it **Experimental** and OFF by default.

## HONEST CHECKS

For each clip with Speaker Frame, write these in plain words in `export_report.json` and on the card:
- Faces inside the safe area: yes, no, or Not measured.
- Headroom: good, too little, too much, or Not measured.
- Number of camera moves and the speed of moves.
- How many seconds each layout was shown.
- Warnings: audio unclear, camera changed, speaker off screen.
Never write "passed" for something you did not measure.

## FEEDBACK ON EVERY CLICK

Follow the same click rules as before: busy words ("Saving...", "Rendering preview..."), disabled buttons while working, persistent green, yellow and red messages, and an entry in the Activity list.

## HOW TO TEST

1. Make a test clip with two real speakers (use a clip from my reference videos or golden videos). Use Speaker Frame with Both (stacked). Check both faces are large and inside the safe area.
2. Test One speaker, and test Auto with a clip that has real turns.
3. Test a clip where the camera cuts. Check that the warning appears.
4. Test a clip where the speaker is off screen. Check that it falls back safely.
5. Test that clips WITHOUT Speaker Frame export exactly as before. Compare the results.
6. Test security: boxes and names accepted only as safe values (numbers in range, short plain names). Reject anything else. Test for XSS in the names.
7. Run all tests on Linux and on native Windows if you can. Show the counts.
8. Save before and after frames and side-by-side pictures in `reports/speaker_frame/`.
9. Update `OMNIRUSH_FINAL_REPORT.md`.

## FINAL REPORT TO ME (simple words)

1. What you built, and where the button is.
2. A table of what works, what works partly, and what does not work (be honest).
3. The paths of the test exports so I can watch them.
4. What is still hard (camera cuts, tracking, off-screen speakers) and what you did instead.
5. The exact commands to restart the Studio.
