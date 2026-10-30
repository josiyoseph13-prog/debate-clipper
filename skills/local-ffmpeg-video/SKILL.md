# Local ffmpeg video

Local media work and above all independent verification. A renderer report is a claim and the file itself is the evidence, so probe the file, look at many moments at full size, then judge.

## Probe the file first

- Run `ffprobe` with stream and format output in JSON on the actual output file before judging any render or export.

- Check that a video stream is present with the expected dimensions and frame rate, an audio stream is present, the duration matches the claim and the container is sane.

- Report mismatches plainly with the numbers the tools printed and do not round a failure into a pass.

- Work on Debate Clipper media through the PC wrappers under ~/workspace/tools/pax-pc and copy a file to this VM only when you need to inspect it directly.

- Slice probes before big operations by proving any filter graph or setting on a 5 to 10 second slice before it touches a full file.

- Treat this VM as having no OpenCV and no MediaPipe, so run the project vision code read only on the PC through the wrappers only when a detector measurement is genuinely needed.

## Check many moments, not one frame

- Build a frame series or contact sheet for every clip you verify, sampling at least every 2 to 4 seconds and also at every framing segment change, speaker change, cut and wide moment.

- View every sampled frame yourself before calling a clip checked, good or passed.

- Never support a verification claim with one frame per clip or with start, middle and end frames alone, because defects that appear only in short or wide moments stay invisible that way.

- Inspect shape, seams and containment at full resolution, not only on a downsized contact sheet, because a small sheet hid a hard seam and a sideways stretch that the user later caught.

- For every shot, compare its displayed width to height against the same shot in the source and fail the clip when the difference is over about 2 percent.

- For every wide shot, inspect the full size frame for a visible seam line and fail the clip when any line shows through the picture or the banner.

- For every frame, confirm only the intended view is present and fail the clip when a split view or a thin sliver of another picture appears at an edge.

- Check in the sampled frames that every expected face is fully inside its box, headroom is sane, faces stay clear of captions and the banner, and the layout matches the moment.

- Check the right and left edges of split and blended frames for a thin slice of the other picture, and check wide or small moments for blur bands above and below the picture.

- Hold or widen the framing at a moment where a face leaves or is covered, and flag any snap to a wrong face or any freeze on a stale crop as a defect.

- Treat the project Haar layout labels as heuristics, because analysis frames are downscaled to 320 pixels wide and soft blend content can still label as unknown, and treat MediaPipe as the measurement engine for face checks.

- For a disputed detector claim, re-run the project classifier read only on the PC on the same frame and compare its output with the claim before accepting it.

## Measure audio and read the numbers

- Measure loudness with the ffmpeg loudnorm filter and parse the measured values instead of guessing from playback.

- Detect dead air and long pauses with the ffmpeg silencedetect filter at noise minus 45 dB and duration 1.5 seconds.

- Cross check the export report QA values against their limits, with camera movement at or under 180 px per second and zoom change at or under 0.18 fraction per second.

- Treat any value reported as not measured as not measured in your report, never as a pass.

- Rest active speaker claims on face tracks or manual assignment, because diarization in the Debate Clipper project is not configured and its turns carry speaker unknown today.

- Let manual speaker assignment win over auto detection in every check and every report.

## Repair a verified defect

- Keep the parts of the original render that already check out and splice in a corrected look only at the defective moments, instead of remaking the whole clip in a new style.

- Take the defective moment ranges from the job framing data, such as framing.json, rather than from memory or from one viewed frame.

- Center a corrected blend box on the real speaker face and verify the speaker sits fully inside the box on a frame from that exact moment before rendering the repair.

- Re-run the full many moments check on the repaired file, not only on the moments you changed.

## Trim and convert

- Prefer lossless stream copy cuts when the container allows and warn that copy mode cuts land on keyframes.

- Re-encode only when the task needs a crop, scale, caption burn or similar change, and state the settings used plus the measured time it took.

- Keep aspect math explicit for vertical exports at 1080 by 1920, scaling then padding and never stretching.

- Write outputs to a new filename and never modify the only copy of a file.

- Quote the decisive ffmpeg error line and explain it in plain words when a command fails, instead of retrying blindly with random flags.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Compare a candidate framing change against production on the same 10 to 15 second window of a real clip, using face in frame share, camera move count, limit compliance and viewed frames, before the candidate enters a production render.

- Report each result as measured, observed by eye, not measured or blocked, and name what blocked it.
