# DO ALL THREE TASKS, IN ORDER, WITH CHECKPOINTS

Do these three files, one after the other, in this exact order. Do not mix them. Finish one, check it, save a checkpoint, then start the next.

Project: `/mnt/d/charlie youtube long videos/clipping automation/debate_clipper`

1. `OMNIRUSH_FRAMING_FIX.md`
2. `OMNIRUSH_SPEAKER_FRAME.md`
3. `OMNIRUSH_DUO_STYLE.md`

Task 3 needs my video in `reference videos/duo_style/`. If that folder is empty, skip task 3, tell me clearly, and finish tasks 1 and 2.

## RULES FOR THE WHOLE RUN

- Task 2 builds on task 1. Task 3 builds on task 2. Never start a task before the earlier one is working.
- Keep every V5 feature, all tests and all security rules. Do not break anything.
- Do not fake results. Do not write "passed" for something you did not measure. Say "Not measured."
- Do not stop the whole run because one item is blocked. Note it, move on, and report it.
- Use simple words.

## CHECKPOINT AFTER EACH TASK

After each task, do all of this before you go to the next one:

1. Run all tests (Linux, and native Windows if you can). If any test that passed before now fails, fix it first. Do not continue with a broken build.
2. Make sure a clip that does not use the new features exports exactly as before.
3. Write `reports/checkpoints/CHECKPOINT_<task number>.md` in simple words:
   - what was built,
   - what works, what works partly, what does not,
   - the test counts,
   - the paths of the test exports I should watch,
   - what is still not good enough.
4. Add a short entry to `OMNIRUSH_FINAL_REPORT.md`.
5. Make a backup copy of the code that works: `backups/after_task_<number>/`. Do not delete anything.

## IF YOU ARE RUNNING OUT OF ROOM

If your working memory (context) is nearly full, stop at the next safe point. Write `reports/checkpoints/RESUME_HERE.md` with exactly what is done, what is next, and the files you changed. Then tell me to start a new session and give me the one message to send to continue.

## AT THE VERY END

Give me one short report in simple words:

1. Task 1, 2, 3: DONE, PARTIAL or NOT STARTED, one line each.
2. The paths of the exports I should watch, grouped by task.
3. What I must check by eye.
4. What is still not good enough, honestly.
5. What I must give you, as a checklist.
6. The exact commands to restart the Studio.
