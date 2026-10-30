# NEW APPROACH — Phase 4B Headline Still Fails in jo's Studio (Fix Round 3)
For the OmniRush builder. This file REPLACES the method of PHASE4B_HEADLINE_FIX.md.
The old method failed: your harness passes, jo's real Studio fails — three times now.
Do not repeat it. Follow this file exactly. Scope: Phase 4B ONLY. No Phase 4C.

## 1. WHAT IS DIFFERENT THIS TIME — read and obey
Your tests and jo's screen disagree. One of them is testing something different from
what jo actually runs. From now on:
- NO fresh test clips. NO fresh browser profile with empty cache. NO server you start
  your own way. You must reproduce jo's world first, watch it fail, THEN fix it.
- jo is the acceptance test. Your harness is only a tool to find the cause.

## 2. REPRODUCE JO'S EXACT WORLD FIRST (before any fix)
1. Use jo's EXISTING project data as-is — his real candidates and decisions files.
   Do not reset, seed, or clean anything.
2. Use jo's EXISTING clip that failed: source XzbsCpiA5Q0 (the Political Lens clip from
   his screenshots). If more of his existing clips are available, test on at least two.
3. Start Studio the way JO starts it — the native Windows venv:
   .\work\native_windows\venv\Scripts\python.exe -m dc studio --port 8765
   (If you cannot run the Windows venv from WSL, say so in the report and instead prove
   which server process/code path jo's start command uses, and test against that.)
4. Use a browser WITH NORMAL CACHING ENABLED, and do a FULL PAGE RELOAD between
   Save & Done and reopening Edit. jo's browser may be serving an old studio.js —
   your fresh-profile harness would never see that. Test as jo lives, not as you wish.
5. Record the failing trace (payload sent, value stored, value on reopen) and put it in
   the report BEFORE the fix section. If you cannot reproduce the failure under these
   conditions, STOP: say so plainly, list every remaining difference between your setup
   and jo's, and still ship Section 3 and Section 4 below — they make the truth visible
   on jo's screen either way.

## 3. ARCHITECTURE CHANGE — the server is the only source of truth
Whatever the trace shows, make these two changes so this class of bug cannot hide again:
A. REOPEN READS FROM THE SERVER, FRESH, EVERY TIME.
   When Edit opens, the Headline field (and the rest of the saved decision) must be filled
   from a FRESH server response for that clip — never from in-memory candidate/list data
   the page loaded earlier, never from a cached copy. If the server has a saved headline,
   the field shows it. If the fetch fails, show a plain error — never silently show empty.
B. SAVE & DONE PROVES ITSELF ON SCREEN.
   After Save & Done, immediately read the saved record BACK from the server and show a
   small line under the Headline field:  Saved headline: "<the exact text>"
   (or "Saved headline: (empty)" when cleared.) jo must be able to SEE what the server
   actually stored without reopening anything. This line is part of the fix, keep it.

## 4. KILL THE CACHE PROBLEM PERMANENTLY
- Studio's static files (studio.js, studio.css, speaker-frame.js) must be served so the
  browser can never run an old copy after the code changes: versioned URLs or
  no-cache/must-revalidate headers — choose one, implement it, and state which in the report.
- Verify: load Studio, note the script URL/version, change nothing, reload — the browser
  must be running the current file. This protects every later phase, not only this fix.

## 5. ACCEPTANCE — all of these, on jo's existing clip, jo's start method
1. Type TEST HEADLINE 12345 → Save & Done → the on-screen line reads back exactly that.
2. FULL PAGE RELOAD → reopen Edit → field shows TEST HEADLINE 12345 (from the server).
3. Clear fully → Save & Done → read-back line shows (empty) → reload → reopen → still empty.
4. Type SECOND 678 → save → reload → reopen → shows SECOND 678.
5. Restart the server (jo's way) → reopen → still SECOND 678.
6. Repeat steps 1–2 on a SECOND existing clip of jo's — same result.
7. No JavaScript errors anywhere. Trim still passes its Phase 4B checks.
8. Full regression suite passes (PHASE4B/4A/3B/3A/2/1 smokes + full suite).

## 6. REPORT — reports/PHASE4B_HEADLINE_FIX2_REPORT.md
- REPRODUCTION: the failing trace from Section 2 (or the honest list of differences
  if you could not reproduce).
- ROOT CAUSE: the exact step that lost jo's headline, file + line. "It works in my
  harness" is not a root cause.
- THE FIX: what changed, including the Section 3 read-back line and Section 4 cache method.
- ACCEPTANCE: Section 5, step by step, pass/fail, on jo's real clip.
- NOT VERIFIED: anything left for jo. It is acceptable for this section to name jo's own
  re-test — jo will do check 3 and check 4 himself, and HIS result is final.

Never write "fixed" because a test you wrote passed. Write what the evidence shows.
