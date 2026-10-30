# computer-vision (Pax, independent verification)

Pax vision capability is evidence based review, not a second production stack: extract frames, look at them, and read the project own measured outputs. Never upgrade a builder claim that it works into a pass without frames.

## Environment truth

- This VM has no OpenCV and no MediaPipe. Do not pretend to run detectors locally.

- Pax can extract frames with ffmpeg and inspect them visually, read vision outputs stored in job artifacts, and run the project own vision code read only on jo PC through the wrappers when a measurement is genuinely needed.

## The project vision stack

- The project code stores validated accuracy as false for its Haar layout labels, so its labels are heuristics. Analysis frames are downscaled to 320 pixels wide.

- MediaPipe FaceLandmarker is the measurement engine for face checks. A value reported as not measured must be reported as not measured, never as a pass.

## Verification protocol

- Get frames at the timestamps that matter from the actual output file, not the preview.

- Judge composition directly: every expected face in frame, headroom sane, faces clear of captions and banner, correct layout read.

- Cross check numbers in the export report and the render plan framing segments.

- For a disputed claim, re-run the project classifier read only on the PC on the same frame and compare with the claim.

## Available connectors

- Use `muse.connector_search` to find the current connector docs before following recovered instructions.
