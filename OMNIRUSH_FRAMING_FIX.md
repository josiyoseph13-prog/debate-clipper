# FRAMING AND LAYOUT FIX: MATCH THE POLITICAL LENS REFERENCE

I compared my exported clip with my real Political Lens reference. The export is wrong. Fix it.
Use simple words in reports.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`

Two pictures I am giving you:
- BAD (our export): `exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_01_okay-so-what-if-you-make-fun-of-a-white-person_7m55s-8m23s_c_a9ef26901548_f6f886c6/01_okay-so-what-if-you-make-fun-of-a-white-person.mp4`
- GOOD (my reference): the Political Lens reference images and videos in `reference image/` and `reference videos/`. The best example is the frame with the headline "Should hiring be completely blind to RACE, AGE, AND GENDER?" and the speaker in a big, clear frame.

## RULES

- The reference is the visual authority. Match the layout and the framing quality. Do not copy one clip exactly.
- Keep all tests and security rules. Do not break anything.
- Do not fake results. Do not claim a face is safe unless you measured it.
- Do not stop for one problem. Note it and keep going.

## WHAT IS WRONG IN OUR EXPORT

1. **Wrong subjects.** It shows a split screen with a bodyguard and a crowd. The real speaker is cut off at the edge. The person who talks is not clearly in the frame.
2. **Hard split-screen seam** down the middle. The reference uses one clean, large shot of the speaker.
3. **Speaker is too small and not centered.** The reference shows the face and upper body large, with natural headroom.
4. **The header is missing.** The reference has the round Political Lens emblem, the "POLITICALLENS" wordmark, the blue verified tick and the handle `@_political_lens` at the top. Our export only shows the headline.
5. **Layout is different.** The reference has: white top area with the header, then the headline, then the video window, then a white area below. Our video window is positioned and sized differently, and it has black edges.
6. **Text at the bottom of the frame** looks like the file name (`01_okay-so-what-if-you-make-fun-of-a-white-person.mp4`). Check if it is burned into the video. If it is, remove it. If it is only my video player, tell me.
7. **Captions** sit over the middle of the picture. Put them in the position that the reference uses, and keep them off the speaker's face.

## WHAT I WANT

### 1. One clean, large speaker shot (default)

- Show the ACTIVE speaker, large, with the face fully inside the safe area and natural headroom, like the reference.
- Fill the video window. No black bars. No stretching or squashing.
- Smooth, slow camera moves. No jumps. Limit the speed of pan and zoom.

### 2. Follow the speaker when the view changes

- When the person who talks changes, move to the new speaker. Use a clean cut or a short smooth move. Do not hold on the wrong person.
- Hold a shot long enough to be calm. Do not flip back and forth during short interruptions.
- Use real evidence to find the active speaker: speaker turns from the audio, face detection, and mouth movement. Use licensed local models. Do not use face recognition to name anyone.
- If the camera angle in the source video changes (wide shot, close-up, crowd shot), re-frame the new shot properly.

### 3. Split screen only when it is really needed

- Use the two-person layout only when two real speakers are both in the picture and both matter.
- If used, show both faces large, one above the other (or a clean side-by-side), never a bodyguard, a crowd or an empty edge.
- If the system is not sure, choose the safe single wide shot of the active speaker. Never guess.

### 3b. Questioner at a microphone

In clip 1, a student at a microphone asks the question. Show the student when they speak, and show the answering speaker when they answer. Do not show a crowd shot as the main picture.

### 4. Match the reference layout exactly

- White top area with the emblem, the POLITICALLENS wordmark, the blue verified tick and the `@_political_lens` handle.
- The headline below, in the same font, size and position as the reference.
- The video window in the same position and size as the reference.
- White area below, as in the reference.
- Use the real logo file. Do not redraw it. If the wordmark file is missing, use the fallback and tell me clearly.
- Check the layout positions against my reference frames with a measurement (for example pixel boxes). Show the numbers.

### 5. Remove anything that should not be burned in

- No file name, no debug text, no job ID on the video.

### 6. Honest face and framing checks

- Measure: face found, face inside safe area, headroom, speaker size, number of camera moves, and speed of moves.
- Write the results in plain words in `export_report.json` and on the clip card.
- If a measurement is not possible, say "Not measured." Do not say "passed."

## HOW TO TEST

1. Look at the BAD clip and at 6 frames of it. Save them in `reports/fix3/before/`.
2. Take 6 frames from my reference videos. Save them in `reports/fix3/reference/`.
3. Fix the code.
4. Re-export these 3 clips from job `job_863e97df620d`:
   - the "make fun of a white person" clip (7m55s to 8m23s)
   - the "Christian teaching on love" clip (3m10s to 3m38s)
   - the "all that matters to god" clip (5m21s to 5m53s)
5. Save 6 frames of each in `reports/fix3/after/`.
6. Make a side-by-side image for each clip: reference, before, after. Save in `reports/fix3/compare/`.
7. Run all tests (Linux and native Windows if possible). Show the results.
8. Also test on 1 different video from `reference videos/` or the golden videos, so the fix is not made only for these 3 clips.
9. Update `OMNIRUSH_FINAL_REPORT.md`.

## FINAL REPORT TO ME (simple words)

1. What was wrong, and what you changed.
2. The file paths of the 3 new exports.
3. A table: for each clip, did the active speaker appear large and centered? Did the view follow the speaker? Is the header correct? Is anything burned in that should not be?
4. What is still not good enough (be honest).
5. The exact commands to restart the Studio.
