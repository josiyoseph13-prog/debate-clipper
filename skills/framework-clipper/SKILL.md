# Framework Clipper

Transcript-first debate clipping for jo's accounts (Political Lens / Open Debate), built from the Mind Clash framework studies (~/workspace/mindclash/FRAMEWORK_STUDY_2026-10-14.md and FRAMEWORK_STUDY_V2_2026-10-14.md — the V2 rules R1–R7 come from the 7 extra million-view hits). The unit of selection is an EXCHANGE — question → build → verdict — never a bare time window. Use whenever picking, cutting, or verifying a debate clip for jo, including hit-mining picks and one-off test clips. Works with local_ffmpeg_video (media checks) and the Debate Clipper app on jo's PC (renders).

## The workflow — no step may be skipped

1. **Words before pictures.** Get the word-timestamped transcript of the source debate first (the app writes work/<job>/transcript.json; for a fresh source, run the app or faster-whisper). Never choose a window from the candidate list alone.
2. **Scan for exchanges.** Run `scripts/exchange_scan.py <transcript.json>` — it ranks windows that start on a question/claim and end on a full line, and flags BAD END (open question) and BAD START (connective tissue). Use its output as the shortlist, then read the actual exchange yourself.
3. **Apply the framework rules** (below) to pick ONE exchange per clip.
4. **Set trims on word boundaries only.** Start = the word-start of the first kept word; end = just after the verdict word (the render rejects mid-word boundaries, and a start inside a sentence the framework would reject anyway).
5. **Cut the middle honestly.** Off-topic lines inside the window come out (segment-level cuts); real words only, meaning unchanged. Keep the natural small pause at speaker changes and any reaction beat that carries meaning — never tighten to wall-to-wall speech.
   - **Hide big-removal joins (jo-endorsed 2026-10-18, from the @ginyboi jump-cut reel jo sent):** when a cut removes a big chunk inside one speaker's turn, the pose jump gives the cut away. Fix in this order: (1) keep the AUDIO continuous across the join — bridge it, never let the sound jump where the picture does; (2) close the gap fully, kept pieces tight against each other; (3) cover the exact cut moment with a short insert laid over the join — the listener's reaction, a wide two-shot, or real B-roll from the same exchange — so the eye is on the insert while the pose resets underneath. Only where a jump would actually show; a clean small trim needs no cover. The insert must be honest footage from the same exchange, never invented context.
6. **Sound.** Lens bed = MindClash's actual tracks — "TERSTOSTERONE" and "LAZY?" by BASS MEDIA — by jo's override (2026-10-23, which killed the old clean-pool-only rule; the copyright risk was named and jo accepted it). The official-copy hunt found nothing downloadable anywhere and is PARKED by jo (2026-10-23) — he finds the solution himself; until then use the standing Crypto bed. The bed is never flat: it rises and hits WITH the picture — cuts, switches, the big moment (jo, 2026-10-23). Speech stays clearly on top; final loudness −18 to −21.5 LUFS.
7. **Verify before calling it finished** (the battery below). A clip that fails any check is not finished.

## Framework rules

**Start (first ~5s)**
- Speech at ~0s, mid-exchange. No intro or setup.
- First line is a question naming the topic, a bold claim, a claim + instant rebuttal, or a dare/hypothetical. The topic word is inside the first sentence — a cold viewer knows the fight in ~2 seconds.
- A mid-sentence start is allowed only when the fragment kept IS the claim. Never start on connective tissue ("which is that…", "but then you would…").

**Middle**
- ONE topic, zero side-lines. Every kept line adds a number, a comparison, a narrower question, or a personal stake. No point made twice — except the core question may return as a **refrain** after a deflection, each time with more pressure (V2 R1).
- Prefer the trap ladder: claim → small question → smaller question → their own answer contradicts the claim.
- **Numbers ladder + lock-in (R2/R5):** if they give a statistic, keep its step-by-step conversion into a concrete picture, then the lock-in beat ("Is that your position?" → "Yes") before the verdict.
- **Define + one example (R3):** if the claim rests on a heavy word, keep the demand for the definition and for ONE specific example; failure at either step is the content.
- **Mercy warning (R4):** an offered exit right before the trap springs ("Do you really want to do this?") marks the peak — keep it.
- **Emotional variant (R6):** a story clip opens on the story claim, keeps one real question in the middle, and lets the other person's answer be the heart.
- Short turns; the last substantive beat belongs to the verdict side.
- Length is earned: 24–52s by default; longer only when a refrain or ladder keeps building.

**End (last ~5s)**
- The last line is the VERDICT: a self-own answer, Charlie's closing statement, a dry button, a retreat/exit, an emotional reveal, or a completed list. It may also be the challenger's own short confirming answer when that completes the exchange (R7).
- The last line is a complete thought; the meaning is complete without a reply.
- NEVER end on an open question whose answer was cut. NEVER stop one line before the punchline — the punchline is the ending.
- Cut 0.04–0.4s after the last word. No outro.

**Hooks**
- On-video hook = the sharp, specific form of the clip's ONE question (short, big; measured to ≤2 lines by the app's fit gate). The first spoken line must start proving it within seconds.
- Post hook may tease the outcome but must still name the topic. A hook that names nothing kills even a strong clip.

## Picture laws (jo's standing style laws, 2026-10-23)

- **Duo faces fully visible (jo, 2026-10-23):** in duo shots BOTH faces fully seen — the seam/feather sits in the gap between the speakers and never crosses or covers either face. If the source leaves no clean gap, use honest singles instead.
- **Face-only zooms (jo, 2026-10-23):** MindClash-style zooms in and out at chosen moments ONLY (a big line, the verdict) — on the FACE of the debater speaking at that moment (Kirk or the other debater), never on bystanders/non-debaters standing around. The zoom target is chosen by WHO IS SPEAKING — proven from the transcript + audio at that moment — never by face movement/tracking alone.
- **3-second pace (jo, 2026-10-23):** no single view held longer than ~3 seconds — duo→speaker, within-duo push toward the speaker, zoom punches — changes land on natural beats so sentences still end whole. The design record lists every framing change with its time.
- **Opening frame (standing since Clip 9 v2, 2026-10-19):** the speaking person is shown clearly and centred from frame 0; solo shots centre the subject (face centre ≈ canvas centre). Measured framing numbers alone do not settle either.

## Verification battery (every clip)

1. **Head check:** transcribe the first 5s of the final file (faster-whisper, CPU is fine for 5s) — confirm the first line and that the topic word lands in the first sentence.
2. **Tail check:** transcribe the last 9s — confirm the last heard line is the intended verdict line, complete, with 0.04–0.4s of tail after it, no trailing half-word.
3. **One-sentence test:** write one sentence saying what the clip argues. If it needs two clauses, the clip is not ready.
4. **Pause check:** silencedetect — no dead air ≥0.4s, but speaker-change beats must still exist (a final with zero gaps ≥0.25s has been over-tightened).
5. **Picture check:** montage at many moments (not one frame) — full-screen HD, no wide small picture left, blends clean at every shot angle, correct account brand. Watch every covered big-removal join IN MOTION: the insert must sit exactly on the cut and no pose jump may show before or after it.
6. **Pace check:** report the longest single-view stretch in the finished clip — a stretch over ~3s fails the gate.
7. **Zoom check:** every zoom verified against the person actually speaking those exact words — a zoom on the wrong face, or a missed zoom on the right one, fails the gate.
8. **Duo check:** in every duo frame both faces fully visible, the seam never crossing or covering a face.

## House rules that still bind

- Finished, delivered clips are never re-edited unless jo explicitly orders it (jo, 2026-10-14). The framework applies to new clips.
- Never use Mind Clash's own edited videos as material; his videos are a map to the original debate only. Music: his ACTUAL beds are the Lens choice by jo's 2026-10-23 override (the old clean-pool-only ban is dead for Lens); until jo's own solution for the files arrives, the standing Crypto bed carries the clip, synced to the picture.
- Report in simple words; verify in the real files, not from memory.
