# UI FIX: MAKE THE STUDIO EASY TO USE

The Political Lens Studio (browser UI) is hard to understand. I am a normal user, not an engineer.
Redesign it so a first-time user knows what to do in 10 seconds.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`

## RULES

- Keep every V5 feature. Do not remove anything. Hide advanced things behind an "Advanced" button instead.
- Keep all security rules (localhost only, XSS and path-traversal protection, rights and integrity blocks).
- Do not break the 76 tests. Run all tests after the change and show the result.
- Do not fake results. Use simple words in the screen text. No code words like "A3", "c_c2ea749286e7", "acoustic", "I-2".
- Use the Political Lens look from `reference image/` (colors, logo).

## WHAT IS WRONG NOW (from my screenshot)

1. The first screen is a plain list of numbers and blue bars. I don't know what to do next.
2. Scores like "narrative, conflict, hook, acoustic 0.00" have no explanation.
3. "unknown: 100% — speaking time, not correctness" is confusing.
4. Clip names like "c_c2ea749286e7 · 79.6 · A3" mean nothing to me.
5. "Blind Label mode" has no explanation.
6. I can't see the video, and I can't see the buttons for approve, reject, edit, or export.
7. The design is plain and cramped.

## WHAT I WANT

### 1. A clear step flow at the top

Step 1 Add video, Step 2 Find clips, Step 3 Review, Step 4 Export.
Always show which step I am on, and one big button for the next step.

### 2. Home screen

- One big box: "Paste a YouTube link or drop a video here."
- Below it: my recent jobs, each with a plain status (Working, Ready to review, Done, Problem) and a progress bar.
- Show plain-language help if something is wrong, such as "Not enough disk space. Free 5 GB."

### 3. Review screen (the most important)

For each clip, show a card with:
- A video player, so I can watch the clip with captions.
- A plain title, the length, and where it starts in the source (for example "12:40 to 13:25").
- ONE overall rating in words (Great, Good, Okay, Weak) with the score as a small number.
- A one-line reason in plain English ("Clear point, strong opening, ends cleanly").
- Big buttons: Approve, Reject, Edit start/end, Export.
- Short warnings in color: "Speaker not identified", "Rights unknown, publishing blocked", "Caption may be wrong".

Put the 8 score bars (narrative, conflict, hook and so on) under a "Why this score?" button. Rename each one in plain words and add a short tooltip. Explain what 0.00 means. If a score is not measured, show "Not measured", not 0.00.

Replace "unknown: 100% speaking time" with a clear line such as "Speaker: not identified yet. Click to name the speaker."

### 4. Search

Name it "Find a moment". Give 3 clickable example searches ("where does he dodge the question?"). Show the results as clip cards.

### 5. Blind Label mode

Move it to Advanced. Add one sentence: "For testers. Hides the system's score so you can rate clips fairly."

### 6. Advanced and Settings

Put these behind a button: score details, model choices, Windows/GPU info, CPU and RAM, logs, analytics. Keep the CPU and RAM line small, in a corner.

### 7. Look

- Clean, modern, roomy layout. Dark or light theme that matches the Political Lens branding.
- Big readable text. Good contrast. Works on a laptop and on a phone browser.
- Every button says what it does. Every empty screen says what to do next.

## HOW TO WORK

1. Look at the current UI code and take screenshots of every screen.
2. Show me a short plan (5 lines).
3. Build the new UI. Keep the old one available at `/classic` so nothing is lost.
4. Run all tests, including the security and XSS checks. Show the results.
5. Take new screenshots of every screen and save them in `reports/ui_fix/after/`. Save the old ones in `reports/ui_fix/before/`.
6. Tell me the exact command to open the Studio and the address to type in my browser.
7. Update `OMNIRUSH_FINAL_REPORT.md`.
8. Give me a short summary in simple words: what changed, what is still hard to understand, what you are not sure about.
