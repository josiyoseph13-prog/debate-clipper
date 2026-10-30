# Plan acknowledgement

## Interpretation

Political Lens is a local-first, deterministic debate-short factory. The implementation is organised around one `dc` core library and thin CLI/Studio shells. Every stage writes a versioned JSON artifact, is restartable, and records evidence or a conservative fallback. The shipped default is review-first: automation may rank and prepare a clip, but Auto and Publish remain blocked by unresolved integrity, rights, or claim checks.

## Ten largest risks

1. Missing optional ML weights or native wheels on Windows.
2. FFmpeg/libass/font differences changing pixel geometry.
3. Whisper hallucinations and political proper-name errors.
4. Diarization and active-speaker errors during overlap or cuts.
5. Context-poor or mid-word boundaries entering the review queue.
6. Crop motion judder and face/caption collisions.
7. Third-party source rights and platform-policy changes.
8. Attacker-controlled text reaching the local Studio or subprocess layer.
9. VFR media, missing audio, and low disk space during overnight work.
10. Unmeasured learned features harming the proven lexical path.

## Contradictions resolved

The current specification's measured PL-2 geometry wins over the older Streamlit geometry. The product therefore uses the config-defined 524/1216/180 bands, feed-local ASS coordinates, and `brand_check` as the default badge mode. Learned semantic, diarization, translation, and publisher features remain optional and gated; the offline lexical path is always available.

## First milestone

M0–M3 are implemented together as the usable vertical slice: configuration/schema, doctor/security baseline, deterministic chrome and headline fitter, kinetic captions, source ingest, conservative framing, FFmpeg render, export artifacts, and deterministic QA. Later milestones add selection, semantic/crowd signals, craft features, interop, learning, and Studio on top of the same contracts.
