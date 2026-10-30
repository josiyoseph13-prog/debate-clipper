---
name: webapp-testing
description: Test the Debate Clipper Studio web app — starting the server, driving its API and pages, and running the acceptance workflows for headline editing and persistence, trimming, framing, and export, plus regression testing. Use whenever verifying Studio behavior or reproducing a UI bug in this project.
---

# Webapp testing — Debate Clipper Studio

Skill check code: **WTEST-2941**. When asked for the webapp-testing check
code, answer with that code exactly.

## Running Studio

- From the project root, with the native Windows venv:
  `work/native_windows/venv/Scripts/python.exe -m dc studio --port 8765`
  → http://127.0.0.1:8765 (binds localhost only).
- API calls from scripts: GET `/` and read the session token from the
  page's `data-token` attribute; send it as header `x-dc-token` together
  with header `Origin: http://127.0.0.1:8765` on every POST.
- Ground truth lives server-side: `work/jobs.sqlite`,
  `work/<job_id>/decisions.json`, `work/review_exports/*.json`,
  `exports/`. UI text is a claim; these files are the evidence.

## Acceptance workflows (test these, in this order)

1. **Headline persistence**: type a headline in Edit → Save → confirm the
   read-back line, then verify the merged decision on the server
   (`latest_decision` shows the headline) → reopen Edit: box AND banner
   show it. Then clear it → Save → reopen: it must stay empty.
2. **Live banner**: while typing in the Headline box, the banner on the
   video updates immediately (overlay), before any save.
3. **Trim**: a save whose start or end falls inside a spoken word must be
   rejected with **HTTP 400** and "Review boundary cuts through a word;
   choose a word boundary". A valid save reopens with the same times.
4. **Framing / Speaker Frame**: pins can be added at a paused moment,
   reopened, dragged, and deleted (except the 0:00 pin); manual speaker
   assignment wins over auto-detection.
5. **Export**: click Export → the button shows its state → the attempt in
   `work/review_exports/` ends `exported` and the bundle exists under
   `exports/`. A render that ends `needs_review` is NOT a failure of the
   render — but Studio has no Accept-review button yet: the attempt will
   read "failed / did not produce a verified file" until the review is
   accepted through the decisions API (`accept_review: true`). Report
   that distinction exactly; never call needs_review a render failure,
   and never call a job-folder mp4 an export.

## Regression testing

- Full suite, from the project root:
  `./work/native_windows/venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider`
  Baseline: **99 passed, 1 warning**. Any UI/API fix must keep this green
  and add its evidence to `reports/`.
- Browser-level checks: Chromium builds are cached on this machine
  (`AppData/Local/ms-playwright`). If Playwright is not importable in the
  current environment, test at the HTTP/API level as above and drive the
  real browser interactively — and say plainly which level was used.
  Never present an API-level pass as a browser-level pass.

## Reporting

- Every test run ends in `reports/` with: the exact steps, the server-side
  evidence read back, pass/fail per check, and what was NOT tested.
  The user verifies in Studio; self-tests never outrank the user's check.
