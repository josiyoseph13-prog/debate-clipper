"""
Debate Clipper — Phase 4 User Workflow UI.

A practical end-to-end workflow:
1. Enter YouTube URL → Download
2. Transcribe → Find candidates
3. Review candidates → Select
4. Generate hooks → Choose/Edit/Custom
5. Configure design → Preview
6. Render final → Download
"""
import json
import time
import urllib.request
from pathlib import Path

import streamlit as st
from PIL import Image

try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    st_canvas = None

from config import *
from downloader import download_youtube
from transcribe import transcribe, load_transcript
from clip_finder import heuristic_candidates, ai_candidates
from speaker_tracker import save_speaker_boxes, track_boxes
from speaker_detector import detect_active_speaker
from renderer import render_clip


# ---------------------------------------------------------
# Setup
# ---------------------------------------------------------

ensure_dirs()

st.set_page_config(
    page_title="Debate Clipper",
    layout="wide",
)

settings = load_settings()


# ---------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------

_session_defaults = {
    "video": None,
    "video_meta": {},
    "transcript": None,
    "candidates": [],
    "selected": None,
    "boxes": None,
    "tracking": None,
    "active": None,
    "rendered": None,
    "hooks": [],
    "selected_hook": None,
    "custom_hook": "",
    "hook_source": None,  # "ai", "custom", "edited"
    "render_start_time": None,
}

for key, default in _session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clear_clip_state():
    """Clear state that belongs to the previous video/clip."""
    st.session_state["candidates"] = []
    st.session_state["selected"] = None
    st.session_state["boxes"] = None
    st.session_state["tracking"] = None
    st.session_state["active"] = None
    st.session_state["rendered"] = None
    st.session_state["hooks"] = []
    st.session_state["selected_hook"] = None
    st.session_state["custom_hook"] = ""
    st.session_state["hook_source"] = None


def validate_speaker_boxes(boxes, img_width, img_height):
    """Validate speaker boxes before saving."""
    errors = []
    min_size = 40

    for name, box in boxes.items():
        x, y, w, h = box
        if w < min_size or h < min_size:
            errors.append(
                f"'{name}' box is too small ({w:.0f}x{h:.0f}px). "
                f"Minimum is {min_size}x{min_size}px."
            )
        if x < 0 or y < 0:
            errors.append(f"'{name}' box has negative coordinates ({x:.0f}, {y:.0f}).")
        if x + w > img_width or y + h > img_height:
            errors.append(
                f"'{name}' box extends outside the image "
                f"({x + w:.0f}, {y + h:.0f} vs {img_width}x{img_height})."
            )

    if boxes.get("charlie") == boxes.get("other") and boxes.get("charlie"):
        errors.append("Speaker boxes are identical.")

    return (len(errors) == 0, errors)


def generate_hooks_ollama(candidate, model="llama3.2:3b"):
    """Generate 3-5 hook suggestions using local Ollama."""
    text = candidate.get("text", "")[:500]
    reason = candidate.get("reason", "")
    factors = ", ".join(candidate.get("attention_factors", []))

    prompt = f"""You are a short-form video hook writer.

Generate 3-5 short, curiosity-driven hooks for this debate clip.

The clip contains:
{text}

Why it was selected: {reason}
Factors: {factors}

Rules:
- Each hook must be 1-2 sentences maximum
- Hooks must relate directly to the clip content
- Do NOT invent facts
- Do NOT use clickbait that misrepresents the content
- Make them natural and engaging
- Support emoji use where appropriate

Styles to include:
- Curiosity-driven
- Question format
- Direct/statement
- Controversial/attention-grabbing
- Neutral/informational

Return ONLY valid JSON:
[
  {{"hook": "hook text", "style": "curiosity|question|direct|controversial|neutral"}}
]"""

    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7},
        }
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw = body.get("response", "").strip()
        if not raw:
            return []
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "hooks" in parsed:
            return parsed["hooks"]
        return []
    except Exception as e:
        st.error(f"Hook generation error: {e}")
        return []


def format_time(seconds):
    """Format seconds as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------
# Sidebar — Design Settings
# ---------------------------------------------------------

with st.sidebar:
    st.header("Design Settings")

    settings["display_name"] = st.text_input("Account name", settings["display_name"])
    settings["username"] = st.text_input("Username", settings["username"])
    settings["verified"] = st.checkbox("Verified badge", settings["verified"])

    avatar = st.file_uploader("Logo/avatar", type=["png", "jpg", "jpeg"])
    if avatar:
        avatar_path = ASSETS / "avatar.png"
        avatar_path.write_bytes(avatar.getvalue())
        settings["avatar_path"] = str(avatar_path)
    elif "avatar_path" not in settings:
        settings["avatar_path"] = (
            str(ASSETS / "avatar.png") if (ASSETS / "avatar.png").exists() else None
        )

    st.divider()

    # Hook settings
    settings["hook_size"] = st.slider("Hook size", 48, 120, int(settings.get("hook_size", 72)))
    settings["hook_color"] = st.color_picker("Hook color", settings.get("hook_color", "#000000"))

    st.divider()

    # Caption settings
    settings["caption_size"] = st.slider("Caption size", 48, 120, int(settings.get("caption_size", 72)))
    settings["active_word_color"] = st.color_picker(
        "Active word color", settings.get("active_word_color", "#00FF00")
    )
    settings["caption_y"] = st.slider(
        "Caption position", 800, 1600, int(settings.get("caption_y", 1000))
    )

    st.divider()

    # Advanced settings
    with st.expander("Advanced"):
        settings["header_height"] = st.slider(
            "Header height", 200, 400, int(settings.get("header_height", 280))
        )
        settings["hook_height"] = st.slider(
            "Hook height", 100, 400, int(settings.get("hook_height", 200))
        )
        settings["caption_outline_width"] = st.slider(
            "Caption outline", 2, 8, int(settings.get("caption_outline_width", 4))
        )
        settings["caption_shadow_strength"] = st.slider(
            "Caption shadow", 1, 6, int(settings.get("caption_shadow_strength", 3))
        )
        settings["caption_words_per_beat"] = st.slider(
            "Words per caption beat", 1, 6, int(settings.get("caption_words_per_beat", 3))
        )
        settings["model"] = st.selectbox(
            "Whisper model", ["tiny", "base", "small"],
            index=["tiny", "base", "small"].index(settings["model"]),
        )
        settings["ollama_enabled"] = st.checkbox(
            "Use AI candidate detection", settings["ollama_enabled"]
        )
        settings["ollama_model"] = st.text_input("Ollama model", settings["ollama_model"])

    # Uncertainty fallback: what to do when the active-speaker detector
    # cannot confidently tell who is speaking.
    st.divider()
    st.write("**When the speaker is uncertain**")
    st.caption(
        "The detector compares motion in the two speaker boxes you drew. "
        "In a few frames it may not be sure. This setting decides what to "
        "show while it is unsure."
    )
    _fallback_labels = {
        "prefer_charlie": "Prefer Charlie Kirk (recommended)",
        "keep_current": "Keep the current speaker",
        "wider_shot": "Use the wider shot",
    }
    _fallback_keys = list(_fallback_labels.keys())
    settings["active_speaker_fallback"] = st.radio(
        "If the detector is unsure, do this:",
        _fallback_keys,
        index=_fallback_keys.index(
            settings.get("active_speaker_fallback", "prefer_charlie")
        ),
        format_func=lambda k: _fallback_labels[k],
    )

    if st.button("Save Settings"):
        save_settings(settings)
        st.success("Settings saved.")


# ---------------------------------------------------------
# Main Header
# ---------------------------------------------------------

st.title("Debate Clipper")
st.caption("Local YouTube to 9:16 short-form debate clips. No paid APIs. No cloud.")


# ---------------------------------------------------------
# STEP 1 — Source
# ---------------------------------------------------------

st.header("Step 1 — Source")

url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Download", disabled=not url, type="primary"):
    with st.spinner("Downloading with yt-dlp..."):
        try:
            path, meta = download_youtube(url, INPUT)
            clear_clip_state()
            st.session_state["video"] = str(path)
            st.session_state["video_meta"] = meta
            st.success(f"Downloaded: {path.name}")
        except Exception as e:
            st.error(f"Download failed: {e}. Check the URL and try again.")

# Show existing videos
existing_videos = sorted(INPUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
if existing_videos:
    existing_video = st.selectbox(
        "Or use existing video", ["None"] + [p.name for p in existing_videos]
    )
    if existing_video != "None" and st.button("Load Existing Video"):
        clear_clip_state()
        selected_path = INPUT / existing_video
        st.session_state["video"] = str(selected_path)
        st.session_state["video_meta"] = {
            "id": selected_path.stem,
            "title": selected_path.stem,
            "duration": None,
            "channel": None,
            "uploader": None,
            "webpage_url": None,
        }
        st.success(f"Loaded: {selected_path.name}")
        st.rerun()

video = Path(st.session_state["video"]) if st.session_state.get("video") else None

if video and video.exists():
    st.video(str(video))
    meta = st.session_state.get("video_meta", {})
    if meta.get("duration"):
        st.write(f"Duration: {format_time(meta['duration'])} | Channel: {meta.get('channel', 'Unknown')}")
    elif meta.get("title"):
        st.write(f"Title: {meta['title']}")


# ---------------------------------------------------------
# STEP 2 — Analyze
# ---------------------------------------------------------

st.header("Step 2 — Analyze")

# Load transcript (defined before use in all sections)
transcript_path = (
    Path(st.session_state["transcript"])
    if st.session_state.get("transcript")
    else (TRANSCRIPTS / f"{video.stem}.json" if video else None)
)
transcript = load_transcript(transcript_path) if transcript_path and transcript_path.exists() else None

if video:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Transcribe", type="primary"):
            out = TRANSCRIPTS / f"{video.stem}.json"
            with st.spinner("Running faster-whisper locally..."):
                try:
                    transcribe(video, out, settings["model"])
                    st.session_state["transcript"] = str(out)
                    st.session_state["candidates"] = []
                    st.session_state["selected"] = None
                    st.success("Transcription complete.")
                except Exception as e:
                    st.error(f"Transcription failed: {e}")

    with col2:
        if transcript and st.button("Find Candidates", type="primary"):
            with st.spinner("Analyzing transcript for debate moments..."):
                try:
                    if settings.get("ollama_enabled", False):
                        candidates = ai_candidates(
                            transcript, model=settings.get("ollama_model", "llama3.2:3b")
                        )
                        mode = "AI-assisted"
                    else:
                        candidates = heuristic_candidates(transcript)
                        mode = "Local heuristic"

                    st.session_state["candidates"] = candidates
                    st.session_state["selected"] = None
                    st.success(f"Found {len(candidates)} candidates ({mode}).")
                except Exception as e:
                    st.error(f"Candidate detection failed: {e}")
                    st.session_state["candidates"] = []
else:
    st.info("Download a video first to begin analysis.")


# ---------------------------------------------------------
# STEP 3 — Candidates
# ---------------------------------------------------------

st.header("Step 3 — Candidates")

candidates = st.session_state.get("candidates", [])

if not candidates:
    if transcript:
        st.info("Click 'Find Candidates' to analyze the transcript.")
    else:
        st.info("Transcribe the video to find candidates.")
else:
    st.write(f"**{len(candidates)} candidates found**")

    for i, candidate in enumerate(candidates[:10]):
        start = float(candidate.get("start", 0))
        end = float(candidate.get("end", 0))
        duration = float(candidate.get("duration", end - start))
        score = candidate.get("score", 0)
        reason = candidate.get("reason", "")
        factors = candidate.get("attention_factors", [])
        text = candidate.get("text", "")

        with st.expander(f"**#{i+1}** — {format_time(start)} – {format_time(end)} | {duration:.0f}s | Score: {score}"):
            col1, col2 = st.columns([2, 1])

            with col1:
                if reason:
                    st.write(f"**Why:** {reason}")
                if factors:
                    st.write(f"**Factors:** {', '.join(factors)}")
                if text:
                    st.write(f"**Transcript:**")
                    st.text(text[:300] + ("..." if len(text) > 300 else ""))

            with col2:
                # Preview: seek to candidate in source video
                st.video(str(video), start_time=int(start))

                if st.button(f"Select #{i+1}", key=f"select_{i}", type="primary"):
                    st.session_state["selected"] = candidate
                    st.session_state["boxes"] = None
                    st.session_state["tracking"] = None
                    st.session_state["active"] = None
                    st.session_state["rendered"] = None
                    st.session_state["hooks"] = []
                    st.session_state["selected_hook"] = None
                    st.session_state["custom_hook"] = ""
                    st.session_state["hook_source"] = None
                    st.success(f"Selected candidate #{i+1}.")
                    st.rerun()


# ---------------------------------------------------------
# STEP 4 — Hook Generation
# ---------------------------------------------------------

st.header("Step 4 — Hook")

selected = st.session_state.get("selected")

if not selected:
    st.info("Select a candidate first.")
else:
    st.write(f"**Selected:** {format_time(selected['start'])} – {format_time(selected['end'])} ({selected['duration']:.0f}s)")

    col1, col2 = st.columns(2)
    with col1:
        new_start = st.number_input("Start time (s)", value=float(selected['start']), step=0.1, min_value=0.0)
    with col2:
        new_end = st.number_input("End time (s)", value=float(selected['end']), step=0.1, min_value=0.0)

    # Validate manual time inputs and block invalid updates / rendering
    invalid = False
    if new_start < 0:
        st.error("Start time must be non-negative.")
        invalid = True
    if new_end < 0:
        st.error("End time must be non-negative.")
        invalid = True
    if not invalid and new_start >= new_end:
        st.error("Invalid time range: start must be less than end.")
        invalid = True
    video_duration = st.session_state.get("video_meta", {}).get("duration")
    if not invalid and video_duration is not None and float(new_end) > float(video_duration):
        st.error(f"End time exceeds video duration ({video_duration:.0f}s).")
        invalid = True
    if not invalid and (new_start != selected['start'] or new_end != selected['end']):
        selected['start'] = new_start
        selected['end'] = new_end
        selected['duration'] = max(0.0, new_end - new_start)
        st.session_state["selected"] = selected
        st.rerun()
    elif invalid:
        # Prevent rendering with invalid times: force selected state to match inputs only when valid
        pass


    # Generate hooks
    if st.button("Generate Hooks", type="primary"):
        with st.spinner("Generating hook suggestions via local Ollama..."):
            hooks = generate_hooks_ollama(selected, model=settings.get("ollama_model", "llama3.2:3b"))
            st.session_state["hooks"] = hooks
            st.session_state["selected_hook"] = None
            st.session_state["hook_source"] = None
            if hooks:
                st.success(f"Generated {len(hooks)} hook suggestions.")
            else:
                st.warning("No hooks generated. You can write a custom hook below.")

    # Display hook suggestions
    hooks = st.session_state.get("hooks", [])
    if hooks:
        st.write("**AI Hook Suggestions:**")
        for i, hook in enumerate(hooks):
            hook_text = hook.get("hook", "") if isinstance(hook, dict) else str(hook)
            style = hook.get("style", "") if isinstance(hook, dict) else ""

            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**Hook {i+1}** ({style}): {hook_text}")
            with col2:
                if st.button(f"Select", key=f"hook_{i}"):
                    st.session_state["selected_hook"] = hook_text
                    st.session_state["hook_source"] = "ai"
                    st.success(f"Selected hook {i+1}.")
                    st.rerun()

    # Edit selected AI hook
    if st.session_state.get("hook_source") == "ai" and st.session_state.get("selected_hook"):
        edited = st.text_input("Edit hook", st.session_state["selected_hook"], key="edit_hook")
        if edited != st.session_state["selected_hook"]:
            st.session_state["selected_hook"] = edited
            st.session_state["hook_source"] = "edited"
            st.success("Hook updated.")

    # Custom hook
    st.divider()
    st.write("**Custom Hook**")
    custom = st.text_input(
        "Write your own hook",
        st.session_state.get("custom_hook", ""),
        placeholder="Enter your custom hook here...",
        key="custom_hook_input",
    )
    if custom:
        st.session_state["custom_hook"] = custom

    if st.button("Use Custom Hook", disabled=not st.session_state.get("custom_hook")):
        st.session_state["selected_hook"] = st.session_state["custom_hook"]
        st.session_state["hook_source"] = "custom"
        st.success("Custom hook selected.")
        st.rerun()

    # Show current hook
    if st.session_state.get("selected_hook"):
        st.divider()
        st.write("**Current Hook:**")
        st.write(f"*{st.session_state['selected_hook']}*")
        st.write(f"Source: {st.session_state.get('hook_source', 'unknown')}")


# ---------------------------------------------------------
# STEP 5 — Speaker Framing (Manual Fallback)
# ---------------------------------------------------------

st.header("Step 5 — Speaker Framing")

if video and selected:
    frame_path = WORK / "representative.jpg"

    if not frame_path.exists() or st.button("Refresh Frame"):
        try:
            import cv2
            cap = cv2.VideoCapture(str(video))
            cap.set(cv2.CAP_PROP_POS_MSEC, float(selected["start"]) * 1000)
            ok, frame = cap.read()
            cap.release()
            if ok:
                cv2.imwrite(str(frame_path), frame)
        except Exception as e:
            st.error(f"Could not extract frame: {e}")

    if frame_path.exists():
        img = Image.open(frame_path)
        st.image(
            img,
            caption=f"Frame at {format_time(selected['start'])}. "
                    "Automatic framing is applied below — adjust only if needed.",
        )

        # -----------------------------------------------------
        # 1. Automatic framing (default) — face detection when possible
        # -----------------------------------------------------
        def auto_detect_boxes(image):
            """Detect speaker regions automatically.

            Uses the OpenCV face cascade to place a box around each detected
            face, padded generously so the tracker has room to follow movement.
            Falls back to an even left/right split when no faces are found.
            """
            import cv2
            import numpy as np

            arr = np.array(image.convert("RGB"))
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            h, w = bgr.shape[:2]

            boxes_found = {}
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

            faces = []
            if not cascade.empty():
                faces = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(int(w * 0.04), int(h * 0.04)),
                )

            if len(faces) >= 2:
                # Pick the two largest faces, left-to-right.
                ordered = sorted(faces, key=lambda f: int(f[2] * f[3]), reverse=True)[:2]
                ordered = sorted(ordered, key=lambda f: f[0])
                for name, (fx, fy, fw, fh) in zip(("charlie", "other"), ordered):
                    pad_x = fw * 1.1
                    pad_y = fh * 1.4
                    x = max(0.0, fx - pad_x)
                    y = max(0.0, fy - pad_y)
                    bw = min(w - x, fw + 2 * pad_x)
                    bh = min(h - y, fh + 2 * pad_y)
                    boxes_found[name] = [x, y, bw, bh]
                return boxes_found, "face detection"

            # Fallback: even left/right split.
            mid = w / 2.0
            boxes_found["charlie"] = [0.0, 0.0, mid, float(h)]
            boxes_found["other"] = [mid, 0.0, w - mid, float(h)]
            return boxes_found, "even left/right split (no faces detected)"

        _seed_key = f"auto_seed_{video.stem}_{selected['start']}"
        _use_auto = st.button("Auto-detect Speakers", key=f"auto_btn_{_seed_key}")
        if _use_auto or st.session_state.get("boxes") is None:
            _auto_boxes, _auto_method = auto_detect_boxes(img)
            st.session_state["boxes"] = _auto_boxes
            st.session_state["framing_method"] = _auto_method
            if _use_auto:
                st.success(f"Automatic framing applied ({_auto_method}).")

        st.caption(
            "Automatic framing covers one layout only. If the video cuts to a "
            "different layout mid-clip, re-run auto-detection on a different "
            "frame or adjust the boxes below — a single setting is not "
            "tracked through later layout changes."
        )

        # -----------------------------------------------------
        # 2. Interactive adjustment (optional)
        # -----------------------------------------------------
        with st.expander("Adjust framing manually (optional)", expanded=False):
            framing_mode = st.radio(
                "Framing Mode",
                ["Rectangle Drawing", "Split Line"],
                horizontal=True,
                key=f"framing_mode_{video.stem}",
            )
            drawing_mode = "rect" if framing_mode == "Rectangle Drawing" else "line"

            canvas_boxes = None

            if st_canvas:
                canvas_w = min(img.width, 720)
                canvas_h = max(1, int(img.height * canvas_w / img.width))
                canvas = st_canvas(
                    background_image=img,
                    height=canvas_h,
                    width=canvas_w,
                    drawing_mode=drawing_mode,
                    key=f"speaker_canvas_{video.stem}_{selected['start']}_{framing_mode}",
                )

                # Canvas is rendered at canvas_w x canvas_h but the image is
                # img.width x img.height. Map every object back to image space.
                sx = img.width / canvas_w
                sy = img.height / canvas_h

                objects = []
                if canvas is not None and canvas.json_data:
                    objects = canvas.json_data.get("objects") or []

                def _to_image_space(obj):
                    left = obj.get("left", 0.0) * sx
                    top = obj.get("top", 0.0) * sy
                    width = obj.get("width", 0.0) * sx
                    height = obj.get("height", 0.0) * sy
                    return [
                        max(0.0, min(left, img.width)),
                        max(0.0, min(top, img.height)),
                        max(0.0, min(width, img.width)),
                        max(0.0, min(height, img.height)),
                    ]

                if framing_mode == "Rectangle Drawing" and len(objects) >= 2:
                    a = _to_image_space(objects[-2])
                    b = _to_image_space(objects[-1])
                    canvas_boxes = {"charlie": a, "other": b}

                elif framing_mode == "Split Line" and len(objects) >= 1:
                    line = objects[-1]
                    x1 = line.get("x1", 0.0) * sx
                    x2 = line.get("x2", 0.0) * sx
                    y1 = line.get("y1", 0.0) * sy
                    y2 = line.get("y2", 0.0) * sy

                    if abs(x2 - x1) >= abs(y2 - y1):
                        # Vertical line: left region / right region.
                        split_x = max(0.0, min((x1 + x2) / 2.0, img.width))
                        canvas_boxes = {
                            "charlie": [0.0, 0.0, split_x, float(img.height)],
                            "other": [split_x, 0.0, float(img.width - split_x), float(img.height)],
                        }
                    else:
                        # Horizontal line: top region / bottom region.
                        split_y = max(0.0, min((y1 + y2) / 2.0, img.height))
                        canvas_boxes = {
                            "charlie": [0.0, 0.0, float(img.width), split_y],
                            "other": [0.0, split_y, float(img.width), float(img.height - split_y)],
                        }
                    st.warning(
                        "A single split line describes one layout only. "
                        "It is not re-applied if the video changes layout later."
                    )

                if canvas_boxes is None:
                    st.caption(
                        f"Draw {'two rectangles (Charlie first, then the other speaker)' if framing_mode == 'Rectangle Drawing' else 'one line separating the two speakers'}."
                    )
                else:
                    _cprev, _oprev = canvas_boxes["charlie"], canvas_boxes["other"]
                    st.caption(
                        f"Preview — Charlie: {int(_cprev[0])},{int(_cprev[1])} "
                        f"{int(_cprev[2])}x{int(_cprev[3])} | "
                        f"Other: {int(_oprev[0])},{int(_oprev[1])} "
                        f"{int(_oprev[2])}x{int(_oprev[3])}"
                    )

            else:
                st.info(
                    "streamlit-drawable-canvas is not installed, so interactive "
                    "drawing is unavailable. Use the numeric controls below."
                )
                _cw, _ch = st.columns(2)
                with _cw:
                    st.write("**Charlie**")
                    cx = st.number_input("C x", value=100.0, key="c_x", step=10.0)
                    cy = st.number_input("C y", value=100.0, key="c_y", step=10.0)
                    cw_ = st.number_input("C w", value=300.0, key="c_w", step=10.0)
                    ch_ = st.number_input("C h", value=400.0, key="c_h", step=10.0)
                with _ch:
                    st.write("**Other**")
                    ox = st.number_input("O x", value=600.0, key="o_x", step=10.0)
                    oy = st.number_input("O y", value=100.0, key="o_y", step=10.0)
                    ow_ = st.number_input("O w", value=300.0, key="o_w", step=10.0)
                    oh_ = st.number_input("O h", value=400.0, key="o_h", step=10.0)
                canvas_boxes = {
                    "charlie": [cx, cy, cw_, ch_],
                    "other": [ox, oy, ow_, oh_],
                }

            if canvas_boxes is not None:
                if st.button("Use These Boxes", key=f"use_canvas_boxes_{video.stem}"):
                    st.session_state["boxes"] = canvas_boxes
                    st.success("Framing updated from your drawing.")
                    st.rerun()

        # -----------------------------------------------------
        # 3. Current framing + Save (always available when valid)
        # -----------------------------------------------------
        boxes = st.session_state.get("boxes")
        if boxes:
            _c = boxes["charlie"]
            _o = boxes["other"]
            st.write("**Current framing**")
            st.caption(
                f"Charlie: x={int(_c[0])} y={int(_c[1])} w={int(_c[2])} h={int(_c[3])}  |  "
                f"Other: x={int(_o[0])} y={int(_o[1])} w={int(_o[2])} h={int(_o[3])}"
            )

            valid, box_errors = validate_speaker_boxes(boxes, img.width, img.height)
            if not valid:
                st.error("Framing is not valid yet:")
                for err in box_errors:
                    st.error(f"• {err}")
            else:
                st.caption(f"Method: {st.session_state.get('framing_method', 'manual')}")

            if st.button("Save Framing", type="primary", disabled=not valid):
                bp = WORK / f"{video.stem}_speakers.json"
                save_speaker_boxes(
                    bp, boxes["charlie"], boxes["other"],
                    (img.width, img.height), selected["start"],
                )
                st.success("Speaker framing saved.")
        else:
            st.info("Run auto-detection or draw boxes to set framing.")

    if not st_canvas:
            st.info("streamlit-drawable-canvas is unavailable, so interactive drawing is off. Use the numeric entry below instead.")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Charlie**")
                cx = st.number_input("C x", value=100.0, key="c_x", step=10.0)
                cy = st.number_input("C y", value=100.0, key="c_y", step=10.0)
                cw = st.number_input("C w", value=300.0, key="c_w", step=10.0)
                ch = st.number_input("C h", value=400.0, key="c_h", step=10.0)
            with col2:
                st.write("**Other**")
                ox = st.number_input("O x", value=600.0, key="o_x", step=10.0)
                oy = st.number_input("O y", value=100.0, key="o_y", step=10.0)
                ow = st.number_input("O w", value=300.0, key="o_w", step=10.0)
                oh = st.number_input("O h", value=400.0, key="o_h", step=10.0)

            boxes = {
                "charlie": [cx, cy, cw, ch],
                "other": [ox, oy, ow, oh],
            }
            valid, box_errors = validate_speaker_boxes(boxes, img.width, img.height)
            if not valid:
                for err in box_errors:
                    st.error(err)
            if st.button("Save Speakers (Manual)", disabled=not valid):
                bp = WORK / f"{video.stem}_speakers.json"
                save_speaker_boxes(
                    bp, boxes["charlie"], boxes["other"],
                    (img.width, img.height), selected["start"],
                )
                st.session_state["boxes"] = boxes
                st.success("Speaker boxes saved.")
else:
    st.info("Select a candidate to configure speaker framing.")


# ---------------------------------------------------------
# STEP 6 — Tracking
# ---------------------------------------------------------

st.header("Step 6 — Track Speakers")

boxes = st.session_state.get("boxes")

if video and selected and boxes:
    if st.button("Track Speakers", type="primary"):
        try:
            progress_bar = st.progress(0, text="Starting speaker tracking...")

            def on_progress(idx, total_est, t):
                pct = min(100, int(100 * idx / max(1, total_est)))
                progress_bar.progress(pct, text=f"Tracking at {format_time(t)} (frame {idx})...")

            with st.spinner("Tracking speakers and detecting active speaker..."):
                tracking_path = WORK / f"{video.stem}_tracking.json"
                tracking = track_boxes(
                    video, boxes, tracking_path,
                    init_time=selected["start"], end_time=selected["end"],
                    progress_callback=on_progress,
                )
                progress_bar.progress(70, text="Detecting active speaker...")

                active = detect_active_speaker(
                    video, tracking, selected["start"], selected["end"]
                )
                progress_bar.progress(100, text="Tracking complete.")

                st.session_state["tracking"] = tracking
                st.session_state["active"] = active
                st.success("Tracking complete.")

        except Exception as e:
            # Clear stale tracking state on any failure so UI doesn't stay stuck
            st.session_state["tracking"] = None
            st.session_state["active"] = None
            progress_bar.empty() if 'progress_bar' in locals() else None
            st.error(f"Tracking failed: {e}")
else:
    if not boxes:
        st.info("Save speaker boxes first.")
    else:
        st.info("Select a candidate first.")


# ---------------------------------------------------------
# STEP 7 — Render
# ---------------------------------------------------------

st.header("Step 7 — Render Final")

tracking = st.session_state.get("tracking")
active = st.session_state.get("active")

if video and selected and boxes and tracking and active and transcript:
    # Final summary
    st.write("**Render Summary:**")
    st.write(f"- **Source:** {video.name}")
    st.write(f"- **Clip:** {format_time(selected['start'])} – {format_time(selected['end'])} ({selected['duration']:.0f}s)")
    st.write(f"- **Hook:** {st.session_state.get('selected_hook', 'None')}")
    st.write(f"- **Account:** {settings['display_name']} ({settings['username']})")
    st.write(f"- **Output:** 1080x1920, H.264 + AAC")

    if st.button("Render Final Clip", type="primary"):
        settings["headline"] = st.session_state.get("selected_hook", "")

        existing_outputs = list(OUTPUT.glob("clip_*.mp4"))
        out = OUTPUT / f"clip_{len(existing_outputs) + 1:03d}.mp4"

        st.session_state["render_start_time"] = time.time()

        with st.spinner("Rendering 1080x1920 H.264/AAC clip..."):
            try:
                render_clip(
                    video, selected["start"], selected["end"],
                    tracking, active, transcript, settings, out,
                )
                elapsed = time.time() - st.session_state["render_start_time"]
                st.session_state["rendered"] = str(out)
                st.success(f"Generated {out.name} in {elapsed:.1f}s")
            except Exception as e:
                st.error(f"Rendering failed: {e}")
else:
    missing = []
    if not selected:
        missing.append("select a candidate")
    if not boxes:
        missing.append("save speaker boxes")
    if not tracking:
        missing.append("track speakers")
    if missing:
        st.info(f"Complete these steps first: {', '.join(missing)}.")


# ---------------------------------------------------------
# STEP 8 — Output
# ---------------------------------------------------------

st.header("Step 8 — Output")

rendered = st.session_state.get("rendered")

if rendered and Path(rendered).exists():
    output_path = Path(rendered)

    st.video(str(output_path))

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Open Output Folder"):
            import subprocess
            subprocess.run(["explorer", str(output_path.parent)])

    with col2:
        with open(output_path, "rb") as f:
            st.download_button(
                "Download",
                data=f,
                file_name=output_path.name,
                mime="video/mp4",
            )

    with col3:
        st.write(f"Size: {output_path.stat().st_size / (1024*1024):.1f} MB")

    st.code(str(output_path))
else:
    st.info("Render a clip to see the output here.")
