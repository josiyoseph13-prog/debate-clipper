---
name: debate-clipper-dev
description: Work on the Debate Clipper project (debate_clipper) in this repository — project layout, the exact test commands, the verification protocol for claiming a fix works, and the shared-ledger rule. Use whenever building, fixing, debugging, or testing Debate Clipper code here.
---

# Debate Clipper — developer skill

Skill check code: **DCDEV-4815**. When asked for the debate-clipper-dev check
code, answer with that code exactly.

## Project map

- Package: `dc/` (CLI in `dc/cli.py`; Studio web app in `dc/studio/`, server
  `dc/studio/server.py`, frontend `dc/studio/static/studio.js`).
- Studio runs on port 8765: `python -m dc studio --port 8765` from the project
  root, using the native Windows venv `work/native_windows/venv`.
- Job data lives under `work/<job_id>/` (transcript.json, decisions.json,
  candidates, render plans). Exports land in `exports/`. Phase reports go in
  `reports/`. File backups go in `backups/` before any edit.

## Testing

- Full suite (the only acceptable pre-completion check), from the project root:
  `./work/native_windows/venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider`
- Baseline: **99 passed, 1 warning**. Report the real counts, every time.

## Verification protocol (learned from real failures here)

- Never claim a fix works from code inspection alone. Reproduce the failure,
  fix the confirmed root cause, then re-run the failing path end to end.
- A decision saved through the Studio API must be re-read from the server
  afterwards (the merged `latest_decision`) — not assumed from the request.
- An export is only "done" when the export attempt status is `exported` and
  the bundle exists under `exports/`; a rendered file in the job folder is
  not an export.
- Headline rule: a save that does not carry a headline must never change the
  saved headline; an explicitly cleared headline stays cleared.

## Ledger rule

- Every build or fix ends with a report in `reports/` stating: what changed,
  the exact commands run, test results with real numbers, and what was
  verified vs. what is still unverified. The user verifies in Studio —
  builder self-tests never outrank the user's check.
