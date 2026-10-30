# My TODO — files and answers to give the builder

Put all files under the project folder:

`D:\charlie youtube long videos\clipping automation\debate_clipper`

The seven supplied golden videos already exist. Do not rename them. Their
label folders and templates are listed below. Fill the templates with real
answers. Do not guess labels, rights, names, speakers, or scores.

## 1. Rights for every supplied golden video

**What it is:** Proof that the video may be used for testing. Choose one:
`own`, `permission`, `licensed`, `public_domain_verified`, or `unknown`.
Include your name, a short note, and a permission/licence/evidence link.

**Where to put it:** In the same folder as that video's `labels_template.json`.

**File name:** `rights_attestation.json`

Make one file in each folder:

- `reports/supplied_media/58aeb69ed5b2ba88/rights_attestation.json`
- `reports/supplied_media/e54bcc72754290db/rights_attestation.json`
- `reports/supplied_media/b29ea28940d29326/rights_attestation.json`
- `reports/supplied_media/c39b2aaafa563f2c/rights_attestation.json`
- `reports/supplied_media/ba9ef1babda331f6/rights_attestation.json`
- `reports/supplied_media/a5f7e41589f9a086/rights_attestation.json`
- `reports/supplied_media/f4330a3bf5c47396/rights_attestation.json`

Unknown rights are allowed for review, but they keep Auto and publishing
blocked.

## 2. The original full debate sources

**What it is:** The full, raw debates used to make the seven finished shorts.
Finished portrait shorts are not enough. We need the original video to know
what the system missed or what response was cut.

**Where to put them:**
`input/golden_sources/`

**File names:** Keep the original names, or use these simple names:

- `golden_01.mp4`
- `golden_02.mp4`
- `golden_03.mp4`
- `golden_04.mp4`
- `golden_05.mp4`
- `golden_06.mp4`
- `golden_07.mp4`

Give at least **5 different full sources**. For the diarization test, give at
least **10 excerpts that are 5 minutes each**. None of the current short files
can replace those full sources.

## 3. Source-to-short map

**What it is:** A map showing which full source made each finished short.
Include the raw source SHA-256, the source timestamps, and every kept/cut span.

**Where to put it:** `reports/supplied_media/`

**File name:** `golden_source_map.json`

Use the supplied media IDs and hashes from:
`reports/supplied_media/inventory.json`.

## 4. Two independent raters

**What it is:** Two people who rate the clips independently. Use stable IDs,
such as `rater_01` and `rater_02`. Record who made each label. Do not show
system-selected clips before the blind recall labels are finished.

**Where to put it:** `reports/golden/`

**File name:** `raters.json`

Need at least **2 independent raters**.

## 5. Blind clips each rater would post

**What it is:** Before seeing system results, each rater marks the source
start/end and explains why they would post that span. These are the expected
clips for recall@10.

**Where to put it:** `reports/golden/`

**File name:** `blind_would_post_spans.json`

The test uses time IoU of at least **0.5**.

## 6. Candidate ratings

**What it is:** Ratings for at least **100 candidates**, rated by both people.
For every candidate include:

- candidate ID
- source hash
- start and end time
- system score
- each rater's result: `usable_as_is`, `trivial_trim`, or `not_usable`
- context reason
- start/end reason
- speaker reason
- caption reason
- fairness reason

**Where to put it:** `reports/golden/`

**File name:** `rated_candidates.json`

At least **40 candidates must score 90 or higher** for the precision@90 gate.
The target rules are recall@10 at least **0.60**, precision@90 at least **0.70**,
Cohen's kappa at least **0.40**, no duplicates, and a Wilson 95% confidence
interval.

## 7. Framing windows

**What it is:** Labeled 60-second source windows. For every second, mark:

- active speaker cluster
- silence or crosstalk
- face boxes
- whether the face is in the safe area
- acceptable layout: single, dual, or wide

Speaker names must be verified labels. Do not use face recognition.

**Where to put it:** `reports/golden/`

**File name:** `framing_windows.json`

Need at least **20 labeled 60-second windows**. The target rules are wrong
speaker at most **15%**, face safe-area at least **98%**, and at most **8
switches per minute** outside interruption bursts.

## 8. Hand-timed words

**What it is:** Exact spoken words with the real start/end time, speaker, and
an independently checked source timestamp. Also mark caption transcription
mistakes.

**Where to put it:** `reports/golden/`

**File name:** `hand_timed_words.json`

Need at least **100 words**. The target is median onset error at most **100 ms**
and p95 at most **250 ms**.

## 9. Proper names and non-name negatives

**What it is:** Every tested spoken name, including:

- spoken name
- ASR text
- correct spelling
- timestamp
- whether it is a name or not a name

Include non-name examples so wrong replacements count as errors.

**Where to put it:** `reports/golden/`

**File name:** `name_occurrences.json`

Need at least **100 real name occurrences**, plus non-name negatives. The target
replacement precision is at least **0.98** and the name error rate must fall.

## 10. Diarization excerpts

**What it is:** Full speech intervals with speaker cluster labels. Include
overlap and silence, not only clear speech.

**Where to put it:** `reports/golden/`

**File name:** `diarization_excerpts.json`

Need at least **10 labeled excerpts of 5 minutes each**. This is needed to
compare the two licensed diarization stacks using the 0.25-second collar and
record DER, RAM, and real-time factor.

## 11. Intent and paraphrase queries

**What it is:** Blind search questions and the expected source span for each
question. Include normal wording and paraphrases, for example “where does he
avoid the question?” and “where does he dodge the answer?”

**Where to put it:** `reports/golden/`

**File name:** `intent_queries.json`

Candidate ratings alone do not test prompt search. The target is the correct
labeled clip in the top 5 for at least **70%** of queries.

## 12. Learned-layer comparison labels

**What it is:** Paired results for the local L0 system, L1 models, and any L2
model. Use the same labeled set. Record recall, precision, mid-thought cuts,
wrong context, and the source/candidate IDs.

**Where to put it:** `reports/golden/`

**File name:** `semantic_layer_comparison.json`

The learned layer can only be enabled if its bootstrap 95% gain interval is
above zero and it does not add mid-thought or wrong-context errors. Otherwise
it stays off.

## 13. Brand files for exact visual matching

**What it is:** The separate horizontal Political Lens wordmark and one clean,
unannotated 1080×1920 export frame.

**Where to put them:**

- Wordmark: `assets/wordmark.png` or `assets/wordmark.svg`
- Clean frame: `reference image/clean_full_export.png`

The existing emblem is already used. Do not redraw it.

## 14. Platform and human-use files

**What it is:** Real safe-zone screenshots and the account/audit information
needed before any publisher can be enabled.

**Where to put them:** `reports/platform/`

**File names:**

- `youtube_safe_zone.png`
- `tiktok_safe_zone.png`
- `instagram_safe_zone.png`
- `account_audits.json`

Also use native Windows Studio, watch three exports, test the phone queue, and
measure the real number of manual steps. Write the result in:
`reports/platform/human_acceptance.json`.

## 15. Commercial comparison files

**What it is:** Comparable outputs from Opus Clip and Klap for the same **10
diverse sources** and comparable settings. Also provide at least **3
independent raters** for blind paired review.

**Where to put the videos:**
`reports/bakeoff/opus/` and `reports/bakeoff/klap/`

**File name for the rater list:** `reports/bakeoff/raters.json`

Do not change the fixed rubric after seeing the results. The comparison uses
source-level paired results and bootstrap 95% confidence intervals.

## 16. Channel data for the learning loop

**What it is:** Your own platform results for each clip: views, average percent
watched, swipe-away at 3 seconds, shares, and variant ID.

**Where to put it:** `reports/analytics/`

**File name:** `channel_stats.csv`

At least **60 clips** are needed before the analytics model can make a proposal.
It remains proposal-only until you approve it.

## 17. Recurring-name glossary (optional but useful)

**What it is:** Correct spellings of recurring people, places, groups, and
terms used to protect ASR names.

**Where to put it:** `config/`

**File name:** `glossary.json`

This is optional. It does not replace the 100-name accuracy labels.

## Quick check before sending

- Full sources are in `input/golden_sources/`.
- Rights files say who supplied the right and include evidence links.
- The source map connects each short to its full source.
- Two raters are listed before system clips are shown.
- Blind spans are complete.
- There are at least100candidate ratings,20framing windows,100hand-timed
  words,100name occurrences, and10five-minute diarization excerpts.
- Search queries include paraphrases.
- The wordmark and clean frame are separate files.
- Platform screenshots, account details, human review, bake-off exports, and
  channel data are in the named folders.

The exact field guidance and pass rules are in
`reports/supplied_media/golden_requirements.md`. Unknown rights, missing
labels, or missing human review continue to block the related acceptance gate.
