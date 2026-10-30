# THE SUPERVISION LOOP — how the original operation runs, clip by clip

The quality does not come from the tools alone. It comes from this loop,
run for EVERY clip. If you are the receiving Muse and you work solo, you
run all three seats yourself, in separate sessions: supervisor, builder,
checker. Never merge the seats.

## The three seats

- **Supervisor** (the Pax seat): picks the moment, writes the job letter,
  checks the finished delivery at decisive spots, and passes or returns it.
- **Builder**: builds ONLY from the job letter, the skills, and the rules.
  No style of its own.
- **Checker**: a separate agent/session that did not build the clip.
  Re-measures the finished file and writes a report file with numbers.
  The builder never checks its own work.

## One job = one job letter

Before building, the supervisor writes a job letter as a file. Use
`JOB_LETTER_TEMPLATE.md` (included in this pack) for its shape:

- The job: source, the exact exchange, the headline, the account/brand.
- What "done" means: the finished file plus the checker's report file.
- The stop rule: fail twice on the same step → write a STUCK note (what was
  tried, what failed, what is needed) and stop. No third silent try.
- Work is proven by files, not chat claims: size, MD5, frames, numbers.

Each new job starts in a FRESH session with the job letter as the first
message, plus the one-page state note of lessons from previous jobs.

## The delivery gate

1. Builder delivers: finished MP4 + build record + edge transcript.
2. Checker runs the FULL gate list (FRIEND_CLIPPER_RULES.md section 8) on
   the actual file and writes its report next to the delivery.
   No report = not done.
3. Supervisor spot-checks: size + MD5, frame 0, a ~20-frame contact sheet,
   caption case at random spots, sound fit at one random moment, and the
   report's numbers. Any failed spot → supervisor full-checks that clip.
   The FIRST clip of any new style gets a full check always.
4. The OWNER is the final eye on every finished clip. Nothing is posted
   before his verdict.
5. A fault that reaches the owner joins the checker's gate list FOREVER,
   and the next 3 clips get the supervisor's full check.
6. One clip at a time. While one builds, the supervisor may research the
   next pick, but never builds two at once.

This loop is slow on purpose at the start. After the owner's verdicts on the
first clips, the lessons go into the state note and the loop speeds up
without dropping the gates.
