# Debate Clipper — Master Blueprint

> **Status:** DRAFT — Requires user approval before implementation
> **Date:** 2026-10-02
> **Author:** Senior Architecture Review

---

## 1. Executive Summary

Debate Clipper is a local-first Windows application that converts long-form YouTube debate videos into 9:16 short-form vertical clips. The application has been developed across multiple phases:

- **Phase 1:** Core pipeline (download → transcribe → candidate detection → speaker tracking → render)
- **Phase 2:** Multi-dimensional debate scoring and enhanced clip discovery
- **Phase 3:** Visual design overhaul (white canvas, Inter typography, viral captions)

This blueprint proposes architectural improvements to make the application more modular, reliable, and feature-complete — including an original-source finder and optional social-media publishing.

**Key principle:** Preserve all existing working functionality. Changes are incremental and evidence-based.

---

## 2. Existing Project Status

### 2.1 Feature Status Matrix

| Feature | Status | Notes |
|---|---|---|
| YouTube download (yt-dlp) | **WORKING** | 1080p preserved, metadata extracted |
| Local transcription (faster-whisper) | **WORKING** | Word-level timestamps, CPU int8 |
| Heuristic candidate detection | **WORKING** | Keyword-based scoring |
| AI candidate detection (Ollama) | **WORKING** | llama3.2:3b, JSON response parsing |
| Multi-dimensional scoring | **WORKING** | 8 dimensions (intensity, conflict, question, surprise, memorability, audience reaction, completeness, duration fit) |
| Manual speaker-box UI | **WORKING** | Drawable canvas, validation |
| OpenCV speaker tracking | **WORKING** | CSRT/KCF/MOSSE |
| Active-speaker detection | **PARTIALLY WORKING** | Motion + face detection heuristic; no audio signal |
| White canvas + header | **WORKING** | Configurable branding |
| Viral word-by-word captions | **WORKING** | ASS with green active word |
| 1080×1920 H.264/AAC output | **WORKING** | FFmpeg pipeline |
| Original-source finder | **NOT IMPLEMENTED** | — |
| Social-media publishing | **NOT IMPLEMENTED** | — |
| Job management / recovery | **NOT IMPLEMENTED** | — |
| Batch processing | **NOT IMPLEMENTED** | — |

### 2.2 Current Architecture

```
app.py                    ← Streamlit UI (8-step workflow)
├── config.py             ← Settings, paths, defaults
├── downloader.py         ← yt-dlp wrapper
├── transcribe.py         ← faster-whisper wrapper
├── clip_finder.py        ← Candidate detection (heuristic + AI)
│   └── debate_scorer.py  ← Multi-dimensional scoring
├── speaker_tracker.py    ← OpenCV tracking
├── speaker_detector.py   ← Active-speaker heuristic
├── renderer.py           ← Video rendering + FFmpeg composition
├── captions.py           ← ASS subtitle generation
├── header.py             ← Branding header rendering
└── utils.py              ← Shared helpers
```

### 2.3 Known Limitations

1. **Active-speaker detection** relies on visual motion + face detection only. No audio energy signal is used.
2. **No original-source finder** — user must paste the original long-form URL manually.
3. **No publishing** — clips are saved locally only.
4. **No job recovery** — if the PC shuts down mid-render, work is lost.
5. **Single-threaded rendering** — CPU-bound, ~1.5s per second of clip.
6. **No batch processing** — one video at a time.

---

## 3. Research Methodology

### 3.1 Research Areas

1. Speaker tracking and computer vision
2. Active-speaker detection
3. Transcription and VAD
4. Clip discovery and ranking
5. Video editing, cropping, and rendering
6. Original-source matching
7. Existing open-source projects
8. Publishing integrations
9. GUI alternatives
10. Job management and recovery

### 3.2 Sources

- Official GitHub repositories and documentation
- Google AI Edge MediaPipe documentation
- faster-whisper / WhisperX documentation
- YouTube Data API v3 official docs
- TikTok Content Posting API docs
- Instagram Graph API docs
- FFmpeg filter documentation

---

## 4. Component-by-Component Research

### 4.1 Speaker Tracking

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| OpenCV CSRT | Already in use | Good accuracy, slow | CPU-heavy | **Keep** |
| OpenCV KCF | Already in use | Fast | Less accurate than CSRT | **Keep as fallback** |
| OpenCV MOSSE | Already in use | Very fast | Low accuracy | **Keep as last resort** |
| MediaPipe ObjectDetector | [mediapipe-samples](https://github.com/google-ai-edge/mediapipe-samples) | Optimized for mobile/edge, TFLite | Additional dependency, less flexible | **Not recommended** — no clear advantage for this use case |
| Optical flow | Standard CV technique | Good for small motions | Fails with large displacements | **Not recommended** as primary |

**Verdict:** Existing OpenCV tracker stack (CSRT → KCF → MOSSE) is appropriate. No replacement needed.

### 4.2 Active-Speaker Detection

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| Visual motion (current) | Already in use | Simple, no audio extraction | Fails with static speakers | **Keep as primary** |
| Face detection confidence | Already in use | Helps identify speaking face | Doesn't detect speech | **Keep as secondary** |
| Audio energy (RMS) | Standard DSP technique | Direct speech signal | Requires audio extraction | **RECOMMENDED ADD** — extract audio once, compute RMS per window |
| Silero VAD | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | Lightweight (~2MB), accurate | Additional ONNX dependency | **Consider for Phase 2** |
| WhisperX diarization | [m-bain/whisperX](https://github.com/m-bain/whisperX) | Word-level timestamps + speaker labels | Heavy, requires pyannote | **Not recommended** — overkill for 2-speaker debate |

**Verdict:** Add audio energy (RMS) as a third signal. Extract audio from source video once, compute per-window energy for each speaker's tracked region. Combine: `score = motion * 0.4 + face * 0.3 + audio * 0.3`.

### 4.3 Transcription

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| faster-whisper | Already in use | Fast, CTranslate2, word timestamps | CPU-only is slow | **Keep** |
| WhisperX | [m-bain/whisperX](https://github.com/m-bain/whisperX) | Faster, VAD, diarization | Heavy dependencies | **Not recommended** |
| Silero VAD | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | Lightweight, accurate | Separate model | **Consider for VAD preprocessing** |

**Verdict:** Keep faster-whisper. Consider Silero VAD for preprocessing to reduce hallucination.

### 4.4 Clip Discovery

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| Heuristic keyword scoring | Already in use | Fast, free, no AI | Misses context | **Keep** |
| Ollama LLM | Already in use | Understands context | Slow, requires local server | **Keep** |
| Semantic embeddings | sentence-transformers | Finds similar moments | Requires model download | **Not recommended** — overkill |

**Verdict:** Existing heuristic + Ollama approach is appropriate.

### 4.5 Rendering

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| FFmpeg + OpenCV | Already in use | Flexible, powerful | Complex filter graphs | **Keep** |
| MoviePy | Python video lib | Easy API | Slow, less control | **Not recommended** |
| FFmpeg only | CLI tools | Fast | Hard to do dynamic cropping | **Not recommended** |

**Verdict:** Keep FFmpeg + OpenCV pipeline.

### 4.6 Original-Source Finder

| Approach | Evidence | Pros | Cons | Recommendation |
|---|---|---|---|---|
| YouTube search + transcript match | YouTube Data API v3 | Finds potential sources | Requires API key, quota limits | **RECOMMENDED** |
| Audio fingerprinting | Chromaprint/Dejavu | Robust to re-encoding | Requires fingerprint DB | **Not recommended** — no DB available |
| Video frame similarity | pHash/OpenCV | Works with re-encoding | Computationally expensive | **Consider as secondary** |
| Metadata/title matching | Simple string matching | Fast | Unreliable | **Keep as pre-filter** |

**Verdict:** Use YouTube Data API v3 search + transcript similarity matching. Classify results as EXACT, HIGH-CONFIDENCE, PARTIAL, RELATED, or NO MATCH.

### 4.7 Publishing Integrations

| Platform | API | Requirements | Limitations |
|---|---|---|---|
| YouTube Shorts | YouTube Data API v3 | Google Cloud project, OAuth 2.0, quota | 10,000 units/day free |
| TikTok | Content Posting API | Registered app, `video.publish` scope | App audit required for public posting |
| Instagram Reels | Instagram Graph API | Professional account, Facebook Login | Business verification required |

**Verdict:** Design publishing module with platform adapters. YouTube is most feasible. TikTok/Instagram require app approval.

---

## 5. Proposed Architecture

### 5.1 Module Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                    UI Layer (Streamlit)                  │
├─────────────────────────────────────────────────────────┤
│  Dashboard │ Source Finder │ Clip Review │ Publishing    │
├─────────────────────────────────────────────────────────┤
│                  Application Layer                       │
│  JobManager │ ConfigManager │ SessionState              │
├─────────────────────────────────────────────────────────┤
│                   Domain Layer                           │
│  Downloader │ Transcriber │ ClipFinder │ SpeakerTracker│
│  ActiveSpeakerDetector │ Renderer │ Publisher           │
├─────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                   │
│  YouTubeAPI │ OllamaClient │ FFmpeg │ OpenCV │ SQLite   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Proposed Directory Structure

```
debate_clipper/
├── app.py                    # Main Streamlit entry point
├── config.py                 # Settings, paths, defaults
├── requirements.txt          # Dependencies
├── setup.ps1                 # Windows setup script
├── run.ps1                   # Windows run script
├── settings.json             # User settings
│
├── domain/                   # Business logic
│   ├── __init__.py
│   ├── downloader.py         # YouTube download
│   ├── transcriber.py        # faster-whisper wrapper
│   ├── clip_finder.py        # Candidate detection
│   ├── debate_scorer.py      # Multi-dimensional scoring
│   ├── speaker_tracker.py    # OpenCV tracking
│   ├── speaker_detector.py   # Active-speaker detection
│   ├── renderer.py           # Video rendering
│   ├── captions.py           # ASS subtitle generation
│   ├── header.py             # Branding header
│   └── source_finder.py      # Original-source finder
│
├── infrastructure/           # External integrations
│   ├── __init__.py
│   ├── youtube_api.py        # YouTube Data API v3
│   ├── ollama_client.py      # Ollama LLM client
│   ├── ffmpeg_wrapper.py     # FFmpeg command builder
│   └── database.py           # SQLite job storage
│
├── application/              # Use cases
│   ├── __init__.py
│   ├── job_manager.py        # Job lifecycle
│   ├── config_manager.py     # Settings management
│   └── publisher.py          # Social-media publishing
│
├── ui/                       # Streamlit components
│   ├── __init__.py
│   ├── dashboard.py          # Main dashboard
│   ├── source_finder_ui.py   # Source finder page
│   ├── clip_review_ui.py     # Candidate review page
│   ├── speaker_setup_ui.py   # Speaker box drawing
│   ├── branding_ui.py        # Header/caption editor
│   ├── render_ui.py          # Render progress/preview
│   └── publishing_ui.py      # Publishing page
│
├── assets/                   # Static resources
│   ├── avatar.png
│   └── fonts/
│       ├── Inter-Regular.ttf
│       ├── Inter-Medium.ttf
│       ├── Inter-SemiBold.ttf
│       └── Inter-Bold.ttf
│
├── input/                    # Downloaded videos
├── transcripts/              # Transcription JSON
├── output/                   # Rendered clips
├── work/                     # Temporary/intermediate files
│   ├── downloads/
│   ├── candidates/
│   └── previews/
│
└── docs/                     # Documentation
    ├── MASTER_BLUEPRINT.md
    ├── PROJECT_AUDIT.md
    ├── OPEN_SOURCE_RESEARCH.md
    ├── COMPONENT_COMPARISON.md
    ├── SOURCE_FINDER_DESIGN.md
    ├── PUBLISHING_ARCHITECTURE.md
    ├── IMPLEMENTATION_ROADMAP.md
    └── RISKS_AND_LIMITATIONS.md
```

---

## 6. Key Design Decisions

### 6.1 Keep Existing Components

The following are working and should be preserved:
- `downloader.py` — yt-dlp integration
- `transcribe.py` — faster-whisper wrapper
- `clip_finder.py` — Heuristic + AI candidate detection
- `debate_scorer.py` — Multi-dimensional scoring
- `speaker_tracker.py` — OpenCV tracking
- `speaker_detector.py` — Active-speaker heuristic
- `renderer.py` — FFmpeg rendering pipeline
- `captions.py` — ASS subtitle generation
- `header.py` — Branding header

### 6.2 New Components to Add

1. **`source_finder.py`** — Accepts short-clip URLs, searches YouTube for original long-form sources, matches via transcript similarity
2. **`speaker_detector.py` enhancement** — Add audio energy (RMS) as third signal alongside motion and face detection
3. **`publisher.py`** — Platform adapters for YouTube Shorts, TikTok, Instagram Reels
4. **`job_manager.py`** — SQLite-backed job queue with resume capability
5. **`database.py`** — Local SQLite storage for jobs, candidates, and publishing history

### 6.3 Configuration

All visual elements configurable via `settings.json`:
- Canvas size, background color, corner radius
- Header height, logo size, fonts, colors
- Caption size, position, active-word color, outline width
- Video codec, CRF, preset
- Whisper model, Ollama model

---

## 7. Implementation Roadmap

### Phase 1: Recovery & Audit ✅
- Inspect existing code
- Document current state
- Create backup

### Phase 2: Research & Blueprint ✅
- Research open-source alternatives
- Compare components
- Design architecture
- Produce blueprint

### Phase 3: Approval
- User reviews blueprint
- Approves or requests changes

### Phase 4: Core Infrastructure
- Implement `database.py` (SQLite)
- Implement `job_manager.py`
- Add audio energy to `speaker_detector.py`

### Phase 5: Source Finder
- Implement `source_finder.py`
- YouTube Data API v3 integration
- Transcript similarity matching

### Phase 6: UI Refinement
- Modularize `app.py` into `ui/` components
- Add candidate preview (lightweight)
- Add render summary before final render

### Phase 7: Publishing
- Implement `publisher.py`
- YouTube Shorts adapter
- TikTok/Instagram adapters (with approval flow)

### Phase 8: Testing & Regression
- End-to-end tests
- Verify all previously working features
- Performance optimization

---

## 8. Open Questions for User

1. **YouTube Data API quota** — Do you have a Google Cloud project with YouTube Data API v3 enabled? (Required for source finder)
2. **Social-media accounts** — Do you have developer accounts for TikTok and Instagram publishing?
3. **Priority** — Which is more important: source finder or publishing?
4. **Audio energy** — Should we add audio-based speaker detection now or later?
5. **Job recovery** — Is resume-after-shutdown a critical feature?

---

## 9. Risks & Limitations

| Risk | Impact | Mitigation |
|---|---|---|
| YouTube API quota exhaustion | Source finder fails | Cache results, fallback to manual |
| TikTok/Instagram app approval | Publishing unavailable | Design for manual fallback |
| Speaker detection errors | Wrong speaker framed | Keep manual override, add audio signal |
| Render speed | Long wait times | Progress bar, background processing |
| Large video files | Disk space issues | Cleanup temp files, warn user |

---

## 10. Next Step

**Awaiting user approval of this blueprint before implementation.**

Once approved, begin with Phase 4 (Core Infrastructure) or the phase the user prioritizes.
