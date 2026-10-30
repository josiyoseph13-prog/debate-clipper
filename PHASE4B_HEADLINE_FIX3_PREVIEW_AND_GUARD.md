# PHASE 4B — FIX 3: the saved headline must appear ON the clip and survive Export

Status context (verified by Pax on the real machine, 2026-10-11):
- Headline PERSISTENCE is fixed (FIX 2): jo typed a headline, Save & Done,
  reopened — the box shows it and the green read-back line confirms it.
  Server-side proof: work/job_7422d0f93cd1/decisions.json contains the
  save record (candidate c_b08dcd6a3b97, headline stored). Do NOT redo this.
- What jo found next, in his own words: "it didn't change it, just saved."
  He is right. Two defects remain. Fix exactly these two.

## Defect A — the headline on the video never changes (Studio preview)

- The banner text on the clip is the candidate's AUTO headline
  (hook.headline_options[0]), baked into the pre-rendered chrome image.
  Proof: work/job_7422d0f93cd1 chrome manifest headline text is the auto
  headline, not the saved decision headline.
- Saving a headline triggers no re-render and no preview update, so in
  Edit jo still sees the old automatic title on the video itself.
- Required: in Studio Edit, the banner ON the clip must show the
  current headline — the same value as the Headline box
  (titleFor / currentHeadlineFor already resolve it: decision headline
  first, auto fallback). Implement it as a live overlay fitted with the
  existing /api/fit logic, or by re-rendering the chrome when the Edit
  screen opens and after Save & Done — your choice, but the result must
  be: on open, after save, and after reopen, the banner text the user
  sees EQUALS the headline that will be exported. Clearing the headline
  returns the banner to the auto headline. It must update without a
  page reload.

## Defect B — Export hard-fails a manually typed headline (fidelity guard)

- dc/cli.py command_render resolves the headline correctly (explicit arg,
  else the saved decision headline, else auto) — but then
  headline_fidelity() aborts the whole render with SystemExit when the
  headline contains words absent from the candidate's text.
- That guard is correct for AUTO-GENERATED headlines. It is wrong for a
  headline the USER typed and saved: jo's test headline (and any real
  headline using synonyms or framing words) makes Export die with
  "Headline contains words or claims absent from this clip".
- Required: keep the hard fail ONLY when the headline is auto-generated
  (no decision headline exists). When the headline comes from the saved
  decision, the render must PROCEED, and the fidelity result must be
  recorded as a visible warning in the export receipt/report (and shown
  in the Studio export status), not as a failure. The fit_headline
  physical-fit gate stays in force for every headline.

## Acceptance — evidence, in the real app (house rules)

Use the real clip: job job_7422d0f93cd1, candidate c_b08dcd6a3b97
(source XzbsCpiA5Q0).

1. Set headline to: THE QUESTION HE COULD NOT ANSWER
   (deliberately uses words outside the clip's speech)
   Save & Done → the banner on the clip in Edit shows THAT text.
   Reopen the clip → banner still shows it, box still shows it.
2. Export that clip → the render COMPLETES. The exported title equals
   the typed headline, and a fidelity warning is recorded in the
   export receipt/report — not a failure.
3. Clear the headline, Save & Done, reopen → banner shows the auto
   headline again.
4. Full regression suite passes. Report real timings.

## Constraints

- Back up every file you touch before editing (project convention).
- Do not change the decision file format. Do not weaken the fidelity
  gate for auto-generated headlines. Do not touch unrelated features.
- Do NOT start Phase 4C.
- Write the report to reports/PHASE4B_FIX3_REPORT.md: files changed,
  how each acceptance step was verified (real Studio/browser
  evidence, not only unit tests), timings, and anything you could
  not verify. Never write "fixed" for a step you did not run.
