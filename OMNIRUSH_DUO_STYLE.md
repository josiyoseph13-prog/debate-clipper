# DUO STYLE: LEARN FROM MY REFERENCE VIDEO AND BUILD IT (OPTIONAL)

I will give you a real edited video that shows a two-person style. Study it, find the rules it follows, and build an optional **Duo style** that does the same. Use simple words in reports.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`
Reference video folder: `reference videos/duo_style/` (I will put the video or videos there. If the folder is empty, look in `reference videos/` for the newest file and tell me which one you used.)

## THE STYLE IN MY WORDS

- Most of the time: **two people side by side**, the left shot fading softly into the right shot in the middle. No hard line. The caption sits over the join.
- Sometimes: **one speaker full screen** while that person talks, then it changes to the other speaker when that person talks.
- This is **not consistent** through the whole video. The full-screen single speaker happens when a speaker asks a question or says something long or big. Your job is to find out what really triggers it.

## RULES

- Keep all V5 features, tests and security rules. Do not break anything.
- The Political Lens header, headline and layout from `reference image/` stay as they are. Only the video window changes.
- This is **optional and OFF by default**. It is a style I choose under Speaker Frame. Auto Reframe still runs first. Clips without it export exactly as before.
- Do not copy the reference video's exact timings or crop. Learn the pattern, not the clip.
- Do not fake results. If a rule is a guess, label it "Guess" and show the evidence. If you only have one video, say that the rules are weak.
- Never name a person from their face.
- Do not stop the build over one problem. Note it and keep going.

## PART 1: STUDY THE REFERENCE VIDEO

1. Extract frames every 0.5 seconds. Save a contact sheet in `reports/duo_style/frames/`.
2. For every moment, label the layout: **Duo** (both, blended), **Full A** (speaker A full screen), **Full B** (speaker B full screen). Make a timeline file `reports/duo_style/timeline.json` and a picture of it.
3. Measure from the video:
   - How long each layout stays on screen (shortest, longest, average).
   - How long the change from one layout to another takes, and how it looks (soft fade, quick cut, zoom, slide).
   - The size and position of the soft join in Duo (width of the fade strip, where it sits, left/right boxes).
   - How big each face is in Duo and in Full, and the headroom.
   - Where the captions sit in Duo and in Full, and their size.
   - Whether the speakers swap sides.
4. Use the audio to find who talks and when (speaker turns). Compare the audio timeline with the layout timeline.
5. Find what triggers a switch to Full. Test these ideas against the evidence, and report which ones really match:
   - One person talks without being interrupted for more than N seconds (find N).
   - A question or a long answer.
   - The other person is silent.
   - A louder or more emphatic voice.
   - A topic or sentence length.
   - Something else you find.
6. Find what triggers going back to Duo. Report the delay between the end of the long speech and the return.
7. Write `reports/duo_style/STYLE_RULES.md` in simple words. For each rule: the rule, the measured numbers, the evidence (timestamps), and **Confident** or **Guess**. Be honest about what one video cannot show.

## PART 2: BUILD THE DUO STYLE

Add **Duo style** as a layout inside Speaker Frame (next to One speaker, Both stacked, Both blended, Auto). It uses the rules you found.

1. Start from the boxes and layout that Auto Reframe chose. I can accept, move or draw the speaker boxes myself.
2. The default is the blended side-by-side Duo.
3. Switch to **Full (one speaker)** when your rules say so, for example "one person has talked alone for more than N seconds". Switch back using your rules.
4. Use a minimum time on screen for each layout, and a smooth transition like the reference. No flicker. No rapid flipping during short interruptions.
5. Keep faces outside the soft join. Keep faces large, inside the safe area, with headroom. Do not stretch.
6. If the audio is unclear (crowd noise, overlap), stay in Duo and tell me. Do not guess.
7. If a speaker is not on screen, do not invent a face. Use a safe layout and tell me.

### Controls (simple words, with live preview)

- **Style:** Always Duo, Always Full, or **Smart (like the reference)**.
- **Switch to full screen after:** a slider in seconds (default = the number you measured).
- **Go back to Duo after:** a slider in seconds.
- **Blend width:** Softer / Sharper. **Move the join.** **Swap sides.**
- A **timeline** under the preview with colored bars: Duo, Full A, Full B. I can click the timeline and change any moment by hand, or drag the edges of a bar.
- **Back to Auto Reframe** button.

## PART 3: PROVE IT

1. Re-create the style on the same reference video, using only the rules, with no hand editing. Make a side-by-side video or contact sheet: my reference vs your version. Save it in `reports/duo_style/compare/`.
2. Make the same style on a **different clip** from the test job `job_863e97df620d` or from the other reference and golden videos, to show it is not made for one clip only.
3. Tell me where your version is the same, where it differs, and where it fails. Do not say "matches" unless you measured it.
4. Test that clips without Duo style export exactly as before.
5. Test security: boxes, names and slider values accepted only as safe values.
6. Click feedback: busy words, disabled buttons, persistent green, yellow and red messages, Activity list entry.
7. Run all tests (Linux, and native Windows if you can). Show the counts.
8. Update `OMNIRUSH_FINAL_REPORT.md`.

## FINAL REPORT TO ME (simple words)

1. The rules you found in the reference video, each marked Confident or Guess. Say how many videos you studied.
2. What the style does, and where the button is.
3. Paths of the test exports so I can watch them.
4. What works, what works partly, and what does not (be honest).
5. What I should check by eye.
6. The exact commands to restart the Studio.
