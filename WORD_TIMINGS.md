# WORD TIMINGS — how the caption timings are made

The caption style in FRIEND_CLIPPER_RULES.md only works with true word
timings. In the original operation the builders' own timing maps failed
repeatedly (missing lines, drifting timings), so the rule became: timings are
generated from the AUDIO by one dedicated step, and audio wins over any
transcript.

Method:

1. For each kept piece of the clip, extract that piece's audio exactly as cut
   (the same audio that will be in the render — not the source's audio).
2. Run faster-whisper on the piece audio with word timestamps ON
   (`word_timestamps=True`). Use the project's own ASR setup where possible.
3. Build the chunkmap from the word timestamps: group the spoken words into
   chunks of 2–4 words, ALL-CAPS, each chunk carrying its start/end from the
   word times. The chunk being spoken is the one lit green in the render.
4. Check the chunkmap against the edge transcript: first and last words of the
   piece must match, no spoken line may be missing, and the last chunk must
   end with the complete final word of the piece.
5. If the transcript text and the audio disagree, the AUDIO wins — fix the
   text to what is actually said, or re-cut the piece.

The checker spot-checks green-word timing against the audio at random points
of the finished render (see the gates in FRIEND_CLIPPER_RULES.md, section 8).
