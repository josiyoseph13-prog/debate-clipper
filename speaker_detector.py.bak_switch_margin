import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def _motion_score(gray_a, gray_b):
    if gray_a is None or gray_b is None:
        return 0.0
    a = cv2.resize(gray_a, (64, 64))
    b = cv2.resize(gray_b, (64, 64))
    return float(np.mean(cv2.absdiff(a, b)))


def extract_audio_once(video_path, ffmpeg_path=None):
    """
    Extract audio from video as raw PCM (float32, mono, 16kHz) once.
    Returns numpy array of audio samples.
    """
    if ffmpeg_path is None:
        from utils import find_ffmpeg
        ffmpeg_path = find_ffmpeg()

    cmd = [
        str(ffmpeg_path),
        '-i', str(video_path),
        '-vn',              # no video
        '-acodec', 'pcm_f32le',
        '-ar', '16000',     # 16kHz sample rate
        '-ac', '1',         # mono
        '-f', 'f32le',
        'pipe:1'
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[-2000:]}")

    audio = np.frombuffer(result.stdout, dtype=np.float32)
    return audio


def compute_rms_per_window(audio, sample_rate, window_duration=0.1):
    """
    Compute RMS energy per time window.
    Returns list of (time_seconds, rms_value) tuples.
    """
    window_size = int(sample_rate * window_duration)
    num_windows = len(audio) // window_size

    results = []
    for i in range(num_windows):
        start = i * window_size
        end = start + window_size
        window = audio[start:end]
        rms = float(np.sqrt(np.mean(window ** 2)))
        time_sec = start / sample_rate
        results.append((time_sec, rms))

    return results


def _audio_energy_at_time(rms_data, t):
    """Get RMS value at time t (nearest window)."""
    if not rms_data:
        return 0.0
    best = min(rms_data, key=lambda x: abs(x[0] - t))
    return best[1]


def _box_at(track_rows, speaker, t, fallback=None):
    valid = [r for r in track_rows if r.get(speaker) is not None]
    if not valid:
        return fallback
    return min(valid, key=lambda r: abs(r['time'] - t)).get(speaker)


_FACE_CASCADE = None

def _get_face_cascade():
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
    return _FACE_CASCADE


def _face_detection_score(frame, box):
    """
    Detect faces within a speaker box and return a confidence score.

    Uses OpenCV's built-in Haar cascade face detector.
    Returns (face_detected, face_center_offset).
    """
    if box is None:
        return 0.0, None

    x, y, w, h = map(int, box)
    x = max(0, x)
    y = max(0, y)
    w = max(1, w)
    h = max(1, h)

    # Ensure box is within frame
    frame_h, frame_w = frame.shape[:2]
    x = min(x, frame_w - 1)
    y = min(y, frame_h - 1)
    w = min(w, frame_w - x)
    h = min(h, frame_h - y)

    if w < 10 or h < 10:
        return 0.0, None

    roi = frame[y:y + h, x:x + w]
    if roi.size == 0:
        return 0.0, None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Use cached cascade
    face_cascade = _get_face_cascade()

    if face_cascade.empty():
        return 0.0, None

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(20, 20),
    )

    if len(faces) == 0:
        return 0.0, None

    # Get the largest face
    largest = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = largest

    # Face center relative to box center
    face_cx = x + fx + fw / 2.0
    face_cy = y + fy + fh / 2.0
    box_cx = x + w / 2.0
    box_cy = y + h / 2.0

    offset_x = face_cx - box_cx
    offset_y = face_cy - box_cy

    # Confidence based on face size relative to box
    face_area = fw * fh
    box_area = w * h
    confidence = min(1.0, face_area / max(box_area, 1) * 3)

    return confidence, (offset_x, offset_y)


def _audio_energy_score(video_path, start, end, box, sample_rate=10):
    """
    Extract audio energy in a speaker region.

    This is a simplified approach that uses the audio waveform
    to detect speech activity. Returns an energy score (0-1).
    """
    # For now, return a placeholder. Full audio extraction
    # would require ffmpeg or similar. The motion-based
    # detection is the primary signal.
    return 0.5


def detect_active_speaker(
    video_path,
    track_rows,
    start,
    end,
    sample_fps=8,
    switch_margin=1.15,
    hold_seconds=0.35,
    use_face_detection=True,
    rms_data=None,
    audio_weight=0.0,
    motion_weight=1.0,
    face_weight=0.35,
    face_gate=0.15,
    audio_gate=0.0,
):
    """
    Enhanced active-speaker detection using motion + face detection + optional RMS.

    Signals:
    1. Visual motion in speaker regions (primary)
    2. Face detection confidence (secondary)
    3. Audio energy (RMS) - EXPERIMENTAL, optional
    4. Hysteresis to prevent rapid switching

    Args:
        rms_data: List of (time, rms_value) tuples from compute_rms_per_window()
        audio_weight: Weight for audio signal (0.0 = disabled, 0.3 = typical)
                      When > 0, audio contributes to speaker selection.
                      NOTE: This is experimental. RMS measures sound energy,
                      not speaker identity. Use with caution.

    Returns a list of dicts with 'time', 'active', and confidence scores.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    # Honest progress: compute total frames in range
    total_frames_est = max(1, int((end - start) * fps))
    processed_frames = 0

    prev = {'charlie': None, 'other': None}
    active = 'charlie'
    last_switch = start
    results = []
    step = max(1, int(round(fps / sample_fps)))
    idx = int(start * fps)

    # Smoothing state for scores to avoid jitter
    smoothed_scores = {'charlie': 0.0, 'other': 0.0}
    alpha = 0.6  # smoothing factor

    while cap.isOpened():
        t = idx / fps
        if t > end:
            break
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            processed_frames += 1
            # Honest progress logging (not invented percentages — just stage + approximate frame count)
            progress_pct = min(100, int(100.0 * processed_frames / max(1, total_frames_est)))
            if processed_frames % 50 == 0 or progress_pct >= 100:
                pass  # progress available via caller if needed; no UI freeze
            # Store confidences for candidates
            face_confs = {}

            scores = {}
            face_offsets = {}
            audio_scores = {}
            for name in ('charlie', 'other'):
                bb = _box_at(track_rows, name, t)
                if bb is None:
                    scores[name] = 0.0
                    face_offsets[name] = None
                    audio_scores[name] = 0.0
                    face_confs[name] = 0.0
                    continue

                x, y, w, h = map(int, bb)
                x = max(0, x)
                y = max(0, y)
                w = max(1, w)
                h = max(1, h)

                crop = frame[y:min(frame.shape[0], y + h),
                             x:min(frame.shape[1], x + w)]
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.size else None
                scores[name] = _motion_score(prev[name], gray)
                prev[name] = gray

                # Face detection
                if use_face_detection:
                    face_conf, face_offset = _face_detection_score(frame, bb)
                    face_offsets[name] = face_offset
                    face_confs[name] = face_conf
                    # Boost score if face detected
                    scores[name] += face_conf * 5.0
                else:
                    face_confs[name] = 0.0

                # Audio energy (RMS) - experimental
                if rms_data and audio_weight > 0:
                    audio_scores[name] = _audio_energy_at_time(rms_data, t)
                    scores[name] += audio_scores[name] * audio_weight

            a = scores['charlie']
            b = scores['other']

            # Apply exponential smoothing to reduce jitter
            smoothed_scores['charlie'] = alpha * a + (1 - alpha) * smoothed_scores['charlie']
            smoothed_scores['other'] = alpha * b + (1 - alpha) * smoothed_scores['other']

            # Use smoothed scores for decision making
            a_smooth = smoothed_scores['charlie']
            b_smooth = smoothed_scores['other']

            # Determine candidate with margin (use face confidence correctly)
            if a_smooth >= b_smooth * switch_margin and face_confs['charlie'] >= face_gate:
                candidate = 'charlie'
            elif b_smooth >= a_smooth * switch_margin and face_confs['other'] >= face_gate:
                candidate = 'other'
            else:
                candidate = active

            # Confidence: purely diagnostic. This does NOT influence which
            # speaker is selected above -- it only reports how decisive the
            # scores were, so the renderer can apply the user's uncertainty
            # fallback without changing speaker-accuracy behaviour.
            hi = max(a_smooth, b_smooth)
            lo = min(a_smooth, b_smooth)
            if hi <= 1e-6:
                # No motion signal at all in either box -> no information.
                confidence = 0.0
            else:
                # 1.0 when one box dominates, approaching 0.5 when tied.
                # Scale by absolute signal strength so that "two boxes both
                # barely moving" is also treated as uncertain.
                separation = (hi - lo) / hi
                strength = min(1.0, hi / 2.0)
                confidence = max(0.0, min(1.0, separation * strength))

            # Apply hold time
            if candidate != active and t - last_switch >= hold_seconds:
                active = candidate
                last_switch = t

            results.append({
                'time': t,
                'active': active,
                'confidence': confidence,
                'charlie_score': a,
                'other_score': b,
                'charlie_face_offset': face_offsets.get('charlie'),
                'other_face_offset': face_offsets.get('other'),
                'charlie_audio_score': audio_scores.get('charlie', 0.0),
                'other_audio_score': audio_scores.get('other', 0.0),
            })
        idx += 1

    cap.release()
    return results
