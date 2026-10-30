# REVIEW JOSI — Debate Clipper features, Steps 1–4

Updated: 2026-10-08

This report lists the features found in the current Studio implementation. It covers all four steps, the full Review editor, My exports, shared controls, and current limitations. A feature listed here is present in the code; this document is not a claim that every behavior has passed a real-video test.

## The four steps at a glance

| Step | Screen | What you do |
|---|---|---|
| **#1** | **Add video** | Paste a link or choose a video, then press Find clips. |
| **#2** | **Find clips** | Watch the job status while the app prepares clips, or cancel the job. |
| **#3** | **Review** | Watch a clip, approve or reject it, edit its look, and start an export. |
| **#4** | **Export** | Open the finished clip, open its folder, or copy its file path. |

## #1 — Add video

### Add a video link or file

- Paste a YouTube link into the link field.
- Choose a local video using the file picker.
- Drag and drop a file onto the drop area.
- The drop area highlights while a file is being dragged over it.
- The selected file name appears in the drop area.
- Selecting a file clears the link field. If a link is subsequently entered, the link takes priority when starting the job.
- If neither a link nor a file is supplied, a message says **Add a video first**.

### Find clips button

- One large **Find clips** button starts processing in review mode.
- The button changes to **Starting…** and is disabled while the start request is running.
- The selected source, rights choice, and requested number of clips are sent to the local server.
- Local files are copied into the project's input folder before processing starts.
- A successful start moves to the Finding clips screen and begins status polling.
- If starting fails, the app shows **The video could not be started** with the returned error and records the failure in Recent actions.

### More options

The options are closed initially.

**Rights for this video:**

- **I'm not sure** — the default.
- **It is mine**.
- **I have permission**.
- **I have a licence**.
- **Verified public domain**.

An explanation changes with the selection. The default explanation says local review is allowed but publishing stays blocked until rights are checked.

**How many clips should we find?**

- 5 clips.
- **8 clips** — the default.
- 12 clips.

This is the requested number of candidates, not a guarantee that every video produces that many usable clips.

### Recent videos

- Shows up to eight recent jobs, with jobs identified as tests filtered out.
- Each row shows a readable video title, current stage label, and a small progress bar.
- **Review clips** opens candidates for a job that is ready for review or needs review.
- **View problem** opens an error message for a failed job; **Show details** can display its log.
- An empty-state message appears when there are no visible jobs.
- Job and export data are refreshed in the background every five seconds.

### Advanced and Recent actions

- An **Advanced** section contains a **Show Speaker Frame help** checkbox.
- That preference is stored in the browser and gives a saved-setting message.
- **Recent actions** lists the last 20 recorded actions with local dates and times.
- Activity is stored in this browser's local storage, including starts, clip decisions, Speaker Frame changes, exports, and failures.
- A dismissible first-time hint explains that the default options can be left alone.

## #2 — Find clips

### Status screen

- Displays **Step 2 of 4** and the heading **Finding clips**.
- Shows a large percentage and progress bar when the server supplies a known percentage.
- Shows **Working…** and an animated bar when a percentage is unavailable.
- Opening this step without an active job shows **Waiting for a video**.
- A dismissible hint explains that reloading is unnecessary.

### Current stage labels and percentage mapping

The implementation uses fixed stage markers based on job state. These are not measurements of downloaded bytes, processed frames, or remaining time.

| Job state/stage | Displayed wording | Current marker |
|---|---|---:|
| Queued | Starting | 0% |
| Checking the source | Checking your video | 0% |
| Transcription | Listening to the debate | 25% |
| Selection | Finding the best moments | 50% |
| Preparing review | Preparing your clips | 75% |
| Ready for review or passed | Done | 100% |

The server also maps video-making to 50% and quality checking to 90%. The export screen's waiting flow currently does not poll and display those markers; it uses **Working…** instead.

### Automatic updates and completion

- After a successful start, the app checks the job approximately every 1.2 seconds, plus the time taken by each request.
- When the job becomes ready for review, it loads that job's candidates and opens **#3 Review** automatically.
- A failure shows **The video could not be processed**, with optional log details, and returns to Add video.
- A cancelled job returns to Add video.
- A connection error sets the status to **Connection lost, reconnecting** and retries while polling continues.
- The connection banner can also tell the user to restart Studio.

### Cancel

- **Cancel** changes to **Stopping…** while the request is being sent.
- For a pending Find clips job, it sends a cancellation request to the server.
- On success, it returns to Add video, records the action, and shows a **Stopped** message.
- If cancellation fails, it shows **Could not stop this video**.
- The button is disabled if the displayed progress reaches 100%.

## #3 — Review

Review is where you watch the clips, choose which ones to keep, adjust their appearance, and start exporting them.

### Clip list

On the left, you get:

- The number of clips found.
- A short title for each clip.
- A thumbnail when an export cover is available.
- The clip's starting time.
- A plain rating: **Great, Good, Okay, Weak**, or **Not measured**.
- A highlighted border around the selected clip.
- Click any clip to switch the preview.

Jobs marked as tests are filtered from the displayed clip list. Candidates normally arrive ranked by score from the server. If there are no candidates, the screen offers **Go to Add video**.

### Video preview

In the center:

- One large player for the selected clip.
- Play/pause, seeking, volume, and browser fullscreen controls.
- The finished export is used when available; otherwise it tries a smaller preview video, then the clip or original video.
- Switching clips rebuilds the player and stops/unloads the previous one. Add video, Find clips, Export done, and My exports also call the shared stop/unload routine.
- The shared playback rule pauses other registered videos when another starts playing.
- Videos are paused when they scroll out of view.
- A badge shows **Framing: Auto** or **Framing: Speaker Frame**.

### Four main buttons

| Button | What it does |
|---|---|
| **Approve** | Saves your approval and current framing/caption settings. |
| **Reject** | Records that you do not want the clip. |
| **Edit** | Opens the editing panel beside the video. |
| **Export** | Saves approval and settings, then makes the finished video. |

Buttons show saving/working feedback and a success or error message.

**Export also approves the clip**, so you do not have to press Approve first.

### Why this rating?

This is closed until you open it. It explains the rating using:

- Complete story.
- Disagreement.
- Strong opening.
- Easy to follow.
- Response included.
- Clean ending.
- Enough context.

Measured clues show percentages. Missing clues say **Not measured**. These ratings are selection clues, not predictions of views.

### Inside Edit

Editing hides the clip list and the four main action buttons. You get **Done** and three tabs. On a wide screen, the panel sits beside the video and can scroll independently. Narrow-screen styles stack it below a sticky preview.

### Framing tab

**Who should be on screen?**

- Auto.
- Both people.
- Show more room.

**How close should it feel?**

- Farther.
- Normal.
- Closer.

**Move the picture**

- Left.
- Right.
- Up.
- Down.

Zoom and movement adjustments change the on-screen picture.

### Captions tab

**Caption size**

- Smaller.
- Normal.
- Bigger.

**Highlight color**

- Green.
- Yellow.
- Red.

**Caption look**

- Bold.
- Calm.
- Light.

These settings are saved when you press Approve, Reject, or Export.

### Speaker Frame tab and full editor

The tab offers four picture choices:

- **One person** — show one speaker.
- **Both blended** — both people with a soft join.
- **Both stacked** — one above the other.
- **Duo style** — switch between both people and one person.

Opening a choice launches the full Speaker Frame editor.

#### Beginner guidance

- Beginner mode starts **on**.
- Three-step guide: pick a look → check the boxes → preview and save.
- Advanced controls start closed.
- Turning Beginner mode off opens both the Advanced controls and Advanced timeline.
- Small **?** buttons explain individual settings.

#### Person boxes

- Draw up to two boxes around the people.
- Drag a box to move it.
- Drag its bottom-right corner to resize it.
- Select Person A or Person B.
- Give each box a name.
- Delete a box.
- Mark a person as off-screen.
- See the automatic crop outline alongside your boxes.

#### Preview

- Choose a moment using the time slider.
- Play/pause the source picture.
- See a composed framing preview with the existing export artwork and safe-area outlines.
- See messages about preview problems.
- Layout and option changes request a refreshed framing preview after a short delay.
- Saving is disabled while that preview request is running.

#### Advanced layout controls

- One speaker, stacked, blended, Auto, or Duo.
- Choose Person A or Person B.
- Adjust join softness and position.
- Side-by-side or top-and-bottom blending.
- Swap sides.
- Use the blended layout when both people talk.

#### Duo controls

- Always Duo.
- Always Full.
- Smart switching.
- Adjust when it jumps to one person.
- Adjust the delay before returning to both people.
- Listen to available voice samples and link each voice to Person A or Person B.
- When identified voice samples are unavailable, the editor reports that the audio is unclear instead of inventing speakers.

#### Advanced timeline

- Click a block to preview that moment.
- Enter a start and end time.
- Choose **Person A, Person B, Both, or Wide** for that range.
- Apply or clear timeline corrections.
- Jump to detected camera changes.
- Save different boxes for different camera sections.

#### Saving and resetting

- **Save** — saves Speaker Frame changes.
- **Reset** — restores the initial suggestions locally; save afterward to apply.
- **Cancel** — closes without saving.
- **Reset to Auto** — disables Speaker Frame for that clip.
- **Re-run Auto Reframe** — refreshes the automatic suggestions, with a keep/replace choice for saved edits.

## #4 — Export

### Starting an export from Review

- Pressing **Export** saves approval and the current basic framing/caption settings.
- It requests one finished clip through the existing video-making backend.
- The server allows one render request at a time and reports an error if another is already running.
- While waiting, the Studio reuses the Finding clips panel, changing the heading to **Making your video** with **Working…** and an animated bar.
- When the request returns, the app refreshes jobs and exports and looks for the selected clip's export.
- If an export is found, it opens the Export done screen and records the completion in Recent actions.
- If no export is found, it shows **The video finished with a check** and returns to Review.
- A failed request shows **The export did not finish**, with optional log details, and returns to Review.

### Export done screen

- Displays **Step 4 of 4**.
- Shows a green confirmation: **Your clip is ready**.
- Shows the readable MP4 file name.
- Includes a first-time hint that the file is local and nothing is uploaded automatically.

| Button/link | What it does |
|---|---|
| **Play** | Opens the finished video's local server URL in a new browser tab. |
| **Open folder** | Requests that the host computer open the export folder. On Windows this uses the normal folder-opening action. |
| **Copy file path** | Copies the MP4's full local file path to the clipboard. |
| **Back to my clips** | Returns to Review. |

Folder opening reports success or displays the path if an opening tool is unavailable. Errors are shown in a message. If copying fails, the message displays the path so it can be copied manually. Folder opening is available from localhost, not a remote LAN session.

### Before an export exists

- Clicking the top **Export** step without a last export shows **Your finished videos** with instructions to export from Review.
- **Back to my clips** returns to Review.
- Once an export has completed in the current page session, the Export step reopens that clip's ready screen.

### My exports

This extra page is available from the header on any Studio step.

- Lists local exported videos, newest first.
- Displays the cover image when available.
- Shows the clip title and original video title.
- Shows the original start/end times, local date/time, and file size.
- Each file has **Play**, **Open folder**, and **Copy file path** actions.
- **Add another video** returns to #1 Add video.
- Shows Recent actions when activity has been recorded.
- Shows an empty-state explanation when there are no exports.
- Existing older and newer export folder formats can be read by the export catalog.

## Shared features across the Studio

- **Debate Clipper** product name and a home link in the header.
- Four clickable numbered step buttons, with the current view highlighted.
- Earlier numbered steps turn green based on which view is open; this is navigation styling, not independent proof that work has completed.
- **Help** opens a short explanation of all four steps.
- **My exports** opens the export library.
- **Classic view** opens the preserved older interface at `/classic`.
- Header displays CPU and RAM readings when available, or **Not measured** when unavailable.
- Success, warning, error, and working messages have a **Close** action.
- First-time hints on Add video, Find clips, Review, and Export done can be dismissed with **Got it**; dismissals persist in this browser.
- Keyboard focus outlines are styled for buttons, fields, selectors, and expandable sections.
- Responsive styles adapt cards, navigation, Review, and the editor for smaller windows.
- Dark-color styles follow the browser/system dark preference; there is no visible manual theme switch.
- Reduced-motion preferences disable animations, transitions, and smooth scrolling.
- The interface loads its scripts and styles locally. Downloading a video link still requires network access; local-file review and local exports do not require a cloud UI service.

## Current limitations and incomplete behavior

### #1 Add video

- The five-second background refresh rebuilds the Add video form, so an entered link, chosen file, or unsaved option selection can be cleared.
- The **Show Speaker Frame help** preference is saved, but the current Review/editor code does not use it to hide the guide.
- The input is labelled for YouTube; the start endpoint checks for an HTTP/HTTPS link rather than validating that it is specifically a playable YouTube video.

### #2 Find clips

- Percentages are fixed job-stage markers, not real byte/frame-based progress measurements or a time estimate.
- The 100% marker is based on the job state. This progress helper does not independently check that a result file exists.
- There is no download-byte progress display, estimated completion time, or per-stage elapsed-time display.
- Failure handling returns to Add video and clears the displayed progress rather than keeping the percentage where processing stopped.
- Polling ends after 180 attempts. There is no explicit timeout message or automatic continuation beyond that limit.
- An active job is not automatically reattached to this polling flow after a browser reload.

### #3 Review

Some prototype details are still incomplete:

- **Done closes Edit; it does not save to disk.** Use Approve or Export afterward. Speaker Frame has its own Save button.
- The main caption preview is a static text overlay, not word-by-word synchronized captions.
- Basic framing-layout and caption-style choices do not yet show a fully accurate live export preview.
- Speaker Frame opens in a separate dialog.
- Box arrow buttons, Smaller/Bigger buttons, one-click 2/4/8-second overrides, and “click the timeline block again to change it” are not implemented.
- Clip start/end trimming and headline editing remain available in `/classic`, not the new Review panel.
- Most tab and choice clicks rebuild the player, which can pause/reset playback instead of allowing uninterrupted watching while editing.
- The clip list shows starting time rather than clip length, and does not currently display Approved/Rejected badges.
- Selecting the preview uses the unfiltered candidate array, so filtering test jobs from the list does not guarantee that a test candidate cannot become the initial preview.
- The basic caption overlay is also drawn over finished exports, so it is not an exact display of the encoded captions.
- Auto voice switching depends on available identified turns and the Person A/B voice mapping. Its accuracy must be checked against the actual conversation.
- The control labelled **Shortest time on one shot** edits the return-to-Duo delay, not a separate minimum-shot-duration setting.
- The mobile panel is not independently height-limited; it uses page scrolling under the sticky preview.

### #4 Export and My exports

- The export waiting view does not show frame-level progress, and it still identifies itself as Step 2 because it reuses the Find clips panel.
- The waiting panel's **Cancel** action does not attach a pending job ID for the export flow, so it does not reliably cancel the running export.
- Export lookup can find an older export for the same clip. The ready screen does not independently confirm that the found bundle came from the latest request.
- **Play** opens another browser tab, so playback there is outside the current page's one-video registry. Multiple exported videos opened in separate tabs are not coordinated.
- The Play action uses a new-tab call with `noopener`; its popup warning may appear even when the new tab opens, depending on the browser's return value.
- My exports does not provide search, filtering, renaming, deletion, batch export, or automatic posting controls.
- There is no separate Download button; the available file actions are Play, Open folder, and Copy file path.

## Where these features were found

- `dc/studio/static/studio.js` — the four screens, decisions, basic editing, job polling, file actions, Help, and My exports.
- `dc/studio/static/speaker-frame.js` — shared video registry, Speaker Frame, boxes, Duo controls, preview, timeline, and save/reset actions.
- `dc/studio/static/studio.css` — layouts, sticky preview, responsive styles, dark colors, and reduced-motion/focus styling.
- `dc/studio/server.py` — page shell, job start/status, stage markers, decisions, export requests, media delivery, logs, and folder opening.
- `dc/export_catalog.py` — export listings, readable names, file information, and the local export index.

## Open Studio

From the Debate Clipper project folder on Windows:

```powershell
work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
```

Open `http://127.0.0.1:8765/`.
