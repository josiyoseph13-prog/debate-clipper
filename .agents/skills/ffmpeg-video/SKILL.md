---
name: ffmpeg-video
description: FFmpeg work for Debate Clipper on this machine — encoding, audio sync, captions, 9:16 vertical rendering, hardware acceleration checks, quality verification, and performance-safe video changes. Use whenever a task involves ffmpeg/ffprobe commands, render settings, media debugging, or export quality in this project.
---

# FFmpeg & video — Debate Clipper

Skill check code: **FFVID-7302**. When asked for the ffmpeg-video check
code, answer with that code exactly.

## Tools on this machine (verified)

- ffmpeg **9.0.2-full_build** (Gyan, via WinGet). Never hardcode the path —
  resolve it the way the app does: `require_tool("ffmpeg")` /
  `require_tool("ffprobe")` in `dc/core/tools.py`.
- The full build already ships the filters this project needs: `loudnorm`,
  `ebur128`, `silencedetect`, `scdet`, `libvmaf`, and a `whisper` filter.
  Check before adding dependencies — the answer is usually "already there".
- GPU: NVIDIA MX450, **2 GB**. NVENC encoders exist in this build
  (`h264_nvenc` listed), but existence is not proof: see the accel rule.

## Encoding rules for this project

- Final canvas is **1080×1920 (9:16)**; the review proxy is 540×960,
  libx264 `veryfast`, CRF 25, AAC, `+faststart` (see `command_render`).
- Prefer the project's own render path (`python -m dc render …`) over
  hand-rolled ffmpeg for anything user-facing. Hand-rolled commands are
  for probes and debugging.
- Keep timings honest: report measured seconds for the exact input length.

## Audio sync

- ASR word timings come from the 16 kHz mono extraction; if captions drift,
  check the extraction offset before touching caption code.
- When trimming, cut on word boundaries — the app refuses mid-word bounds
  ("Review boundary cuts through a word"). Use `silencedetect` and the
  transcript word list to find true boundaries.
- For A/V drift in probes, use `aresample=async=1` and verify with a
  frame+waveform spot check, not by ear alone.

## Captions

- Captions are generated `.ass` (plan-driven). Never hand-edit timings in a
  generated file; fix the plan/source and regenerate.
- Verify caption changes on a short slice first (see performance rules).

## Hardware acceleration — prove it or don't claim it

- Before using NVENC or CUDA anywhere: render a 5-second sample both ways,
  compare wall time and output (ffprobe streams + a frame grab). Claim
  acceleration only with those numbers attached.
- 2 GB VRAM is a hard ceiling: large models / high concurrency will OOM.
  int8-class settings only, and one job at a time.

## Quality checks (run before calling any render "done")

1. `ffprobe` the output: streams, dimensions 1080×1920, duration vs the
   plan's trim duration, audio present.
2. Loudness: measure with the `loudnorm` filter in analysis mode (print
   format) — do not guess levels.
3. Silence/scene sanity: `silencedetect` for dead air, `scdet` for
   unexpected cuts.
4. Visual: extract a frame at ~3 s (`-ss 3 -frames:v 1`) and LOOK at it —
   banner text, framing, captions. A green exit code is not a visual pass.
5. Quality compare when changing encoders: `libvmaf` is available.

## Performance-safe changes

- Probe on a 5–10 s slice (`-ss`/`-t`) before any full render. Full renders
  of a ~68 s clip take minutes on this CPU; slices take seconds.
- Reuse intermediates (chrome, moving feed, transcripts) — never re-run
  the whole pipeline to test a one-line change.
- One render at a time (the app enforces a render lock; respect it).
- Any speed claim needs before/after timings on the same input.
