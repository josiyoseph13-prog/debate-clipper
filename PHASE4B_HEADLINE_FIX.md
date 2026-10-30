# SERIOUS FIX INSTRUCTION — Phase 4B Headline Does Not Save (Real Studio)
For the OmniRush builder. Read this whole file before touching code. Follow it exactly.
Scope: Phase 4B ONLY. Do not start Phase 4C. Do not change any other behaviour.

## 1. THE BUG — jo's real test, failed TWICE
In the real Studio (http://127.0.0.1:8765/), with a real clip:
1. Open the clip in Review → Edit.
2. Type a NEW headline in the Headline field.
3. Tap **Save & Done**.
4. Reopen the same clip → Edit.
5. **The Headline field is EMPTY. The typed headline is gone.**

This failed in jo's real Studio test, was "fixed" once (Save & Done reading the live input
value), the PHASE4B smoke test passed again — and then it **failed again in jo's real Studio**
(screenshot evidence: Edit open, Headline field empty for source XzbsCpiA5Q0).
A smoke test passing is NOT proof. It has now been wrong twice. Treat your own test as suspect.

## 2. WHY THIS KEEPS HAPPENING — find the real break in the chain
Do NOT guess and do NOT patch the first plausible line. Trace the headline through the
WHOLE chain, in the real running app, and find the exact step where the value is lost:

  STEP A — CAPTURE: when Save & Done is clicked, what headline value actually leaves
           the browser? (The live DOM input value for THIS clip — log/print it.)
  STEP B — REQUEST: what does the save request payload contain? (Endpoint, clip/candidate ID,
           headline field — the actual bytes sent, not what the code "should" send.)
  STEP C — SERVER: does the server receive that value and store it? Where — decisions store,
           candidate data, both? Does the stored record belong to the same candidate ID
           the Review screen reopens?
  STEP D — PERSISTENCE: after the save, read the store back. Is the new headline there?
           Does anything overwrite it afterwards (a refresh, a re-render, a candidate
           reload that restores the original empty headline)?
  STEP E — REOPEN: when Edit reopens, which value fills the Headline field, and from where?
           If the field is filled from candidate/source data instead of the saved decision,
           THAT is your bug — the reopen path must show the SAVED headline.

Report which step (A–E) loses the value, with the evidence (logged payload / stored record /
reopen value). If two steps lose it, fix both and say so.

Watch specifically for these known patterns in this codebase:
- The Edit panel being rebuilt from candidate data on refresh/re-render, restoring stale values.
- The save going to a different candidate/clip ID than the one reopened.
- A second save (e.g. an automatic decision save) firing after Save & Done with an empty
  headline and overwriting the good one.
- The headline being saved but the reopen path reading a field with a different name
  (headline vs title) and silently defaulting to empty.

## 3. MANDATORY ACCEPTANCE TEST — real browser, real server, real clip
Your fix is accepted ONLY if this exact test passes in the native Studio browser harness
(tools/studio_browser.py) against the REAL running Studio and a REAL clip — real typing,
real clicks, no direct function calls, no mocked save:

  1. Open Studio, open a real clip, tap Edit.
  2. Type the headline: TEST HEADLINE 12345
  3. Tap Save & Done.
  4. Reopen the same clip, tap Edit.
  5. READ the Headline field: it must show exactly "TEST HEADLINE 12345".
  6. Clear the field completely, Save & Done, reopen: field must be EMPTY
     (no old headline, no sample/invented headline).
  7. Type a second headline: SECOND 678, Save & Done, reopen: it must show "SECOND 678".
  8. Also restart the Studio server, reopen the clip: the last headline must STILL be there
     (saved to disk, not only in memory).

Run this test BEFORE your fix and show it failing. Run it AFTER your fix and show it passing.
If you cannot run the real-browser test, say so plainly in the report and give jo the exact
manual steps instead — do NOT write "fixed" on the strength of the smoke test alone.

## 4. FIX RULES
- Fix the real path jo uses (Review → Edit → Save & Done → reopen). Nothing else.
- Do NOT "fix" it by inventing, defaulting, or restoring a sample headline: a headline the
  user cleared must stay empty, and a headline the user never typed must never appear.
- Do NOT weaken, skip, or delete any existing check to make tests pass.
- Trim must keep working exactly as Phase 4B built it (sliders, seconds, length, bad-range refusal).
- No JavaScript errors in the real browser during the whole acceptance test.
- Run the full regression suite afterwards: PHASE4B, PHASE4A, PHASE3B, PHASE3A, PHASE2,
  PHASE1/UI smokes + the full suite must all pass, with the same or better result as before.

## 5. REPORT FORMAT — evidence, not claims
End with a report file `reports/PHASE4B_HEADLINE_FIX_REPORT.md` containing:
- ROOT CAUSE: the exact step (A–E) that lost the headline, file + line, in plain words.
- EVIDENCE: the save payload value, the stored value read back, and the reopen field value —
  before the fix (failing) and after the fix (passing).
- ACCEPTANCE: the Section 3 test, step by step, pass/fail each — including the server-restart step.
- FILES CHANGED: list only.
- REGRESSIONS: full-suite result.
- NOT VERIFIED: anything you did not test in the real browser. If this section is not empty,
  the fix is not complete — say what jo must check manually instead.

Do not write "Fixed" in the report title or summary unless every Section 3 step passed
in the real browser. jo will re-test check 3 and check 4 himself in Studio; his result decides.
