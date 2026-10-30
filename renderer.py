"""
Phase 3 renderer for Debate Clipper.

Renders a 1080x1920 vertical short with:
- White canvas background
- Configurable account header
- Large centered hook/headline
- Video with smart 9:16 reframing
- Viral word-by-word captions
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from header import render_header, render_hook
from captions import build_ass
from utils import run_cmd, find_ffmpeg, has_audio_stream


# Detector confidence below this value is treated as "genuinely unsure".
# Chosen well below the confident range so the fallback only engages during
# real ambiguity (near-tied motion scores, or almost no motion in either box),
# never during ordinary confident tracking.
UNCERTAIN_BELOW = 0.30

# Confidence must rise back above this value before normal tracking resumes.
# The gap between the two thresholds is hysteresis: it stops the camera
# flickering in and out of the fallback on small confidence wobbles.
CONFIDENT_ABOVE = 0.40

# Consecutive confident samples required to leave the fallback. Adds a short
# confirmation delay so a single lucky frame cannot yank the camera away.
CONFIRM_SAMPLES = 3

# Consecutive unconfident samples required to enter the fallback.
UNCERTAIN_SAMPLES = 2


def _box_center(box):
    if box is None:
        return None
    x, y, w, h = map(float, box)
    return x + w / 2.0, y + h / 2.0


def _velocity_smooth(previous, current, velocity, strength=0.12, velocity_factor=0.35):
    """Smooth camera center with velocity prediction."""
    if current is None:
        return previous, velocity
    if previous is None:
        return current, (0.0, 0.0)

    px, py = previous
    cx, cy = current
    vx, vy = velocity

    predicted_cx = cx + vx * velocity_factor
    predicted_cy = cy + vy * velocity_factor

    new_x = px + (predicted_cx - px) * strength
    new_y = py + (predicted_cy - py) * strength

    new_vx = (cx - px) * 0.5 + vx * 0.5
    new_vy = (cy - py) * 0.5 + vy * 0.5

    return (new_x, new_y), (new_vx, new_vy)


def _apply_dead_zone(previous, current, dead_zone=15.0):
    """Apply a dead zone to reduce camera movement."""
    if previous is None or current is None:
        return current

    px, py = previous
    cx, cy = current

    dx = cx - px
    dy = cy - py

    if abs(dx) < dead_zone and abs(dy) < dead_zone:
        return previous

    return current


def _enforce_safe_area(center, frame_w, frame_h, crop_w, crop_h, safe_margin=0.08):
    """Ensure the crop stays within the frame with a safe margin."""
    if center is None:
        return None

    cx, cy = center

    margin_x = crop_w * safe_margin
    margin_y = crop_h * safe_margin

    min_cx = crop_w / 2.0 + margin_x
    max_cx = frame_w - crop_w / 2.0 - margin_x
    min_cy = crop_h / 2.0 + margin_y
    max_cy = frame_h - crop_h / 2.0 - margin_y

    cx = max(min_cx, min(max_cx, cx))
    cy = max(min_cy, min(max_cy, cy))

    return (cx, cy)


def _detect_divider(frame, box_charlie=None, box_other=None, layout='vertical'):
    """Estimate divider from speaker box positions or visual midpoint.
    Supports vertical, horizontal, or single-frame layouts."""
    h, w = frame.shape[:2]
    if box_charlie and box_other:
        if layout == 'horizontal':
            # Top/bottom split: divider is horizontal (y middle of boxes)
            return (box_charlie[1] + box_charlie[3]/2 + box_other[1] + box_other[3]/2) / 2.0, True
        else:
            # Vertical split: divider is vertical (x middle of boxes)
            cx_c = box_charlie[0] + box_charlie[2]/2
            cx_o = box_other[0] + box_other[2]/2
            return (cx_c + cx_o) / 2.0, False
    # Fallback to midpoint; assume vertical unless boxes clearly stacked
    return w / 2.0, False


def _crop_for_box(frame, box, camera_center=None, out_w=1080, out_h=1620, safe_margin=0.08, divider=None, region='full'):
    """Crop a region of the frame centered on the speaker with divider-aware bounds.
    divider: (value, is_horizontal) or None.
    region: 'full', 'left', 'right', 'upper', 'lower'."""
    h, w = frame.shape[:2]

    target_ratio = out_w / out_h

    if camera_center is None:
        if box is not None:
            camera_center = _box_center(box)
        if camera_center is None:
            camera_center = (w / 2.0, h / 2.0)

    cx, cy = camera_center

    # Adaptive framing: when split-screen is likely (both speakers visible), keep wider view
    # Only apply minimum crop if tracking is active and speaker is clearly isolated
    split_screen_hint = False
    # If both speaker boxes are available and far apart, keep wider crop
    if camera_center is None and box is not None:
        split_screen_hint = False

    crop_w = min(w, max(h * target_ratio, w * 0.65))
    crop_h = crop_w / target_ratio

    if crop_h > h:
        crop_h = float(h)
        crop_w = crop_h * target_ratio

    safe_center = _enforce_safe_area(
        (cx, cy), w, h, crop_w, crop_h, safe_margin
    )
    if safe_center is not None:
        cx, cy = safe_center

    x0 = max(0.0, min(w - crop_w, cx - crop_w / 2.0))
    y0 = max(0.0, min(h - crop_h, cy - crop_h / 2.0))

    # Boundary-safe crop: enforce divider when split-screen detected
    if divider is not None and region != 'full':
        divider_val, is_horizontal = divider
        if not is_horizontal:
            # Vertical divider (left/right regions)
            if region == 'left':
                max_x = divider_val + crop_w * 0.15
                x0 = min(x0, max_x - crop_w)
                x0 = max(x0, 0)
            elif region == 'right':
                min_x = divider_val - crop_w * 0.15
                x0 = max(x0, min_x)
                x0 = min(x0, w - crop_w)
        else:
            # Horizontal divider (upper/lower regions)
            if region == 'upper':
                max_y = divider_val + crop_h * 0.15
                y0 = min(y0, max_y - crop_h)
                y0 = max(y0, 0)
            elif region == 'lower':
                min_y = divider_val - crop_h * 0.15
                y0 = max(y0, min_y)
                y0 = min(y0, h - crop_h)

    crop = frame[
        int(y0):int(y0 + crop_h),
        int(x0):int(x0 + crop_w)
    ]

    if crop.size == 0:
        return cv2.resize(frame, (out_w, out_h))

    return cv2.resize(
        crop,
        (out_w, out_h),
        interpolation=cv2.INTER_AREA
    )


def _active_at(active_rows, t):
    """Get the active speaker at time t."""
    if not active_rows:
        return 'charlie'
    return min(
        active_rows,
        key=lambda r: abs(r['time'] - t)
    ).get('active', 'charlie')


def _active_confidence_at(active_rows, t):
    """
    Get the detector confidence at time t.

    Returns 1.0 (fully confident) when the active_rows carry no confidence
    field at all -- that is the pre-fallback behaviour, so older tracking
    data renders exactly as it did before the fallback existed.
    """
    if not active_rows:
        return 1.0
    row = min(active_rows, key=lambda r: abs(r['time'] - t))
    conf = row.get('confidence')
    if conf is None or not isinstance(conf, (int, float)):
        return 1.0
    return float(conf)


def _compute_caption_y(frame_h, header_h, speaker_box, default_y,
                       caption_height=100, safe_margin=20):
    """
    Compute optimal caption Y position to avoid covering the speaker's face.

    Args:
        frame_h: Height of the video frame
        header_h: Height of the header area
        speaker_box: Bounding box [x, y, w, h] of the active speaker, or None
        default_y: Default Y position for captions
        caption_height: Estimated height of the caption text
        safe_margin: Minimum margin to keep from edges

    Returns:
        Integer Y position for the top of the caption text
    """
    # Ensure we're below the header
    min_y = header_h + safe_margin
    max_y = frame_h - caption_height - safe_margin

    if max_y < min_y:
        # Frame too small, use default
        return max(min_y, min(default_y, frame_h - caption_height))

    if speaker_box is None:
        # No speaker info, use default (clamped)
        return max(min_y, min(default_y, max_y))

    # Get speaker's face region (top portion of the box)
    sx, sy, sw, sh = speaker_box
    face_top = sy
    face_bottom = sy + sh * 0.6  # Face is roughly top 60% of body box

    # If default position would overlap with the face, shift it
    caption_bottom = default_y + caption_height

    # Check overlap: caption is below face top AND caption top is above face bottom
    if default_y < face_bottom and caption_bottom > face_top:
        # Overlap detected - try to place caption below the face
        new_y = int(face_bottom + safe_margin)

        # If that's too low, try above the face
        if new_y + caption_height > frame_h - safe_margin:
            new_y = int(face_top - caption_height - safe_margin)

        # Clamp to valid range
        return max(min_y, min(new_y, max_y))

    # No overlap, use default (clamped)
    return max(min_y, min(default_y, max_y))


def _box_at(track_rows, speaker, t):
    """Get the tracking box for a speaker at time t."""
    valid = [
        r for r in track_rows
        if r.get(speaker) is not None
    ]
    if not valid:
        return None
    return min(
        valid,
        key=lambda r: abs(r['time'] - t)
    ).get(speaker)


def _apply_rounded_corners(image, radius=40):
    """Apply rounded corners to the final canvas."""
    h, w = image.shape[:2]

    # Create a mask with rounded corners
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (radius, 0), (w - radius, h), 255, -1)
    cv2.rectangle(mask, (0, radius), (w, h - radius), 255, -1)
    cv2.circle(mask, (radius, radius), radius, 255, -1)
    cv2.circle(mask, (w - radius, radius), radius, 255, -1)
    cv2.circle(mask, (radius, h - radius), radius, 255, -1)
    cv2.circle(mask, (w - radius, h - radius), radius, 255, -1)

    # Apply mask
    result = image.copy()
    result[mask == 0] = 255  # White background for corners

    return result


def render_clip(
    source,
    start,
    end,
    track_rows,
    active_rows,
    transcript,
    settings,
    output_path
):
    """
    Render a complete 1080x1920 vertical short.

    Layout:
    1. White canvas
    2. Account header (logo, name, username, badge)
    3. Hook/headline
    4. Video with smart reframing
    5. Viral word-by-word captions
    """
    temp_video = Path(output_path).with_suffix('.visual.mp4')
    temp_header = Path(output_path).with_suffix('.header.png')
    temp_hook = Path(output_path).with_suffix('.hook.png')
    ass = Path(output_path).with_suffix('.ass')

    # Get settings
    canvas_w = int(settings.get('canvas_width', 1080))
    canvas_h = int(settings.get('canvas_height', 1920))
    header_h = int(settings.get('header_height', 280))
    hook_h = int(settings.get('hook_height', 200))
    video_h = canvas_h - header_h - hook_h

    # Uncertainty fallback from user settings (default prefer_charlie)
    fallback = settings.get('active_speaker_fallback', 'prefer_charlie') if settings else 'prefer_charlie'

    # Open source video
    cap = cv2.VideoCapture(str(source))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    if not cap.isOpened():
        raise RuntimeError('Could not open source video for rendering.')

    # Get frame dimensions early for divider detection
    ret, first_frame = cap.read()
    if ret:
        h, w = first_frame.shape[:2]
    else:
        h, w = 720, 1280  # fallback

    # Create video writer for the video portion only
    out = cv2.VideoWriter(
        str(temp_video),
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (canvas_w, video_h)
    )

    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    # Re-seek to start position after reading first frame
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    frame_i = 0
    last_speaker = 'charlie'
    camera_center = None
    previous_box = None
    velocity = (0.0, 0.0)

    # Hysteresis state for uncertainty fallback (prevents flicker)
    uncertain_streak = 0
    confident_streak = 0
    in_fallback = False

    transition_from = None
    transition_to = None
    transition_left = 0
    transition_total = max(1, int(fps * 0.20))

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        t = start + frame_i / fps
        if t > end:
            break

        speaker = _active_at(active_rows, t)
        if speaker not in ('charlie', 'other'):
            speaker = last_speaker

        # ---- Uncertainty fallback -------------------------------------
        # Applies ONLY while the detector is genuinely unsure. A confident
        # opponent or a confident Charlie is framed normally; this never
        # forces Charlie for the whole clip.
        confidence = _active_confidence_at(active_rows, t)
        if confidence is None or not isinstance(confidence, (int, float)):
            confidence = 1.0

        if confidence < UNCERTAIN_BELOW:
            uncertain_streak += 1
            confident_streak = 0
        else:
            confident_streak += 1
            uncertain_streak = 0

        in_fallback = (uncertain_streak >= UNCERTAIN_SAMPLES) or (
            in_fallback and confident_streak < CONFIRM_SAMPLES
        )
        wider_requested = False

        if in_fallback:
            if fallback == 'prefer_charlie':
                # Only if Charlie is drawn/tracked at all. Identity comes from
                # the user's own box labelling, so this is the only mapping
                # available -- see limitation note in the final report.
                if _box_at(track_rows, 'charlie', t) is not None:
                    speaker = 'charlie'
            elif fallback == 'keep_current':
                # Keep whatever framing we are already on.
                speaker = last_speaker
            elif fallback == 'wider_shot':
                # Handled below: force the full-frame crop.
                wider_requested = True

        box = _box_at(track_rows, speaker, t)
        if box is None:
            box = previous_box

        if box is not None:
            previous_box = box
            target_center = _box_center(box)

            if camera_center is not None:
                target_center = _apply_dead_zone(
                    camera_center, target_center, dead_zone=12.0
                )

            camera_center, velocity = _velocity_smooth(
                camera_center,
                target_center,
                velocity,
                strength=0.15,
                velocity_factor=0.40
            )

        # Detect layout and determine region from speaker track boxes
        divider = None
        region = 'full'
        charlie_box = _box_at(track_rows, 'charlie', t)
        other_box = _box_at(track_rows, 'other', t)
        if charlie_box and other_box:
            # Estimate divider from box centers
            divider = _detect_divider(frame, charlie_box, other_box, layout='vertical')
            # If boxes are clearly stacked vertically, treat as horizontal split
            cy_c = charlie_box[1] + charlie_box[3]/2
            cy_o = other_box[1] + other_box[3]/2
            if abs(cy_c - cy_o) > max(w, h) * 0.25:
                divider = _detect_divider(frame, charlie_box, other_box, layout='horizontal')
                # _detect_divider returns (value, is_horizontal)
                # Ensure divider is (y_value, True)
                if isinstance(divider, tuple):
                    divider_val, _ = divider
                    divider = (divider_val, True)
                else:
                    divider = (divider, True)
                # Determine region from active speaker position relative to divider
                cx = camera_center[0] if camera_center else (w/2)
                cy = camera_center[1] if camera_center else (h/2)
                # Use box center to determine upper/lower
                speaker_box = box
                if speaker_box:
                    speaker_cy = speaker_box[1] + speaker_box[3]/2
                    divider_y = divider[0]
                    region = 'upper' if speaker_cy < divider_y else 'lower'
            else:
                # Ensure divider is (value, is_horizontal) tuple
                if isinstance(divider, tuple):
                    divider_val, _ = divider
                    divider = (divider_val, False)
                else:
                    divider = (divider, False)
                cx = camera_center[0] if camera_center else (w/2)
                divider_x = divider[0]
                region = 'left' if cx < divider_x else 'right'

        current = _crop_for_box(
            frame,
            box,
            camera_center=camera_center,
            out_w=canvas_w,
            out_h=video_h,
            divider=divider,
            region=region
        )

        # Smooth transition when active speaker changes
        if speaker != last_speaker:
            old_box = _box_at(track_rows, last_speaker, t)
            old_center = (
                _box_center(old_box)
                if old_box is not None
                else camera_center
            )

            transition_from = _crop_for_box(
                frame,
                old_box,
                camera_center=old_center,
                out_w=canvas_w,
                out_h=video_h
            )

            transition_to = current.copy()
            # Cross-region cut: skip interpolation across divider
            transition_left = 0
            # Reset smoothing for new region (same-region stays smooth)
            if region != 'full' and (region == 'left' or region == 'right' or region == 'upper' or region == 'lower'):
                # If crossing divider (switching regions), reset camera
                prev_region = 'left' if (last_speaker == 'charlie' and divider and (divider[0] if isinstance(divider,tuple) else divider) > w/2) else 'right'
                # Simple: if speaker changed, reset smoothing
                camera_center = target_center
                velocity = (0.0, 0.0)
            last_speaker = speaker

        if (
            transition_left > 0
            and transition_from is not None
            and transition_to is not None
        ):
            progress = (
                transition_total - transition_left + 1
            ) / transition_total

            current = cv2.addWeighted(
                transition_from,
                1.0 - progress,
                transition_to,
                progress,
                0
            )
            transition_left -= 1

        out.write(current)
        frame_i += 1

    cap.release()
    out.release()

    if not temp_video.exists():
        raise RuntimeError('Visual render did not produce a video file.')

    # Render header
    header_img = render_header(
        width=canvas_w,
        height=header_h,
        display_name=settings.get('display_name', ''),
        username=settings.get('username', ''),
        verified=settings.get('verified', False),
        avatar_path=settings.get('avatar_path'),
        logo_size=int(settings.get('logo_size', 110)),
        bg_color=settings.get('header_bg_color', '#FFFFFF'),
        name_color=settings.get('account_name_color', '#000000'),
        username_color=settings.get('username_color', '#666666'),
        badge_color=settings.get('verified_badge_color', '#1DA1F2'),
    )
    header_img.save(temp_header)

    # Render hook
    hook_img = render_hook(
        width=canvas_w,
        height=hook_h,
        text=settings.get('headline', ''),
        font_name=settings.get('hook_font', 'Arial'),
        font_size=int(settings.get('hook_size', 72)),
        text_color=settings.get('hook_color', '#000000'),
        line_spacing=float(settings.get('hook_line_spacing', 1.3)),
        max_lines=int(settings.get('hook_max_lines', 4)),
        bg_color=settings.get('header_bg_color', '#FFFFFF'),
    )
    hook_img.save(temp_hook)

    # Compute optimal caption Y position based on speaker boxes
    # Use the first speaker box as reference (or None if no tracking)
    first_box = None
    if track_rows and len(track_rows) > 0:
        first_row = track_rows[0]
        if first_row.get('charlie') is not None:
            first_box = first_row['charlie']

    frame_h = video_h  # The video portion height
    optimal_y = _compute_caption_y(
        frame_h,
        header_h,
        first_box,
        int(settings.get('caption_y', 1000)),
        caption_height=int(settings.get('caption_size', 72)) * 2,
        safe_margin=20,
    )

    # Build captions with computed Y position
    build_ass(
        transcript,
        start,
        end,
        ass,
        font=settings.get('font', 'Arial'),
        size=int(settings.get('caption_size', 72)),
        active_color=settings.get('active_word_color', '#00FF00'),
        text_color=settings.get('caption_color', '#FFFFFF'),
        outline_color=settings.get('caption_outline_color', '#000000'),
        outline_width=int(settings.get('caption_outline_width', 4)),
        shadow_strength=int(settings.get('caption_shadow_strength', 3)),
        y=optimal_y,
        words_per_beat=int(settings.get('caption_words_per_beat', 3)),
        animation_timing=float(settings.get('caption_animation_timing', 0.05)),
    )

    # Compose final video with FFmpeg
    ass_path = (
        str(ass)
        .replace('\\', '/')
        .replace(':', '\\:')
    )

    # Font configuration for Inter font
    fonts_dir = str(Path(__file__).resolve().parent / 'assets' / 'fonts')
    fontconfig_path = fonts_dir

    # Set FONTCONFIG_PATH so FFmpeg's libass can find the Inter font
    import os
    os.environ['FONTCONFIG_PATH'] = fontconfig_path

    duration = max(0.1, end - start)
    ffmpeg_path = find_ffmpeg()
    has_audio = has_audio_stream(source, ffmpeg_path)

    # Build filter complex:
    # [0:v] = temp_video (video portion)
    # [1:v] = temp_header (header image)
    # [2:v] = temp_hook (hook image)
    # [3:a] = source audio
    #
    # Stack: header on top, hook below header, video below hook
    # Then overlay captions on the video portion

    header_h_str = str(header_h)
    hook_h_str = str(hook_h)
    video_h_str = str(video_h)

    if has_audio:
        vf = (
            f"[0:v]scale={canvas_w}:{video_h}[v];"
            f"[1:v]scale={canvas_w}:{header_h}[h];"
            f"[2:v]scale={canvas_w}:{hook_h}[k];"
            f"[v][h][k]vstack=inputs=3[stacked];"
            f"[stacked]subtitles='{ass_path}':force_style='Fontname=Inter'[vout];"
            f"[3:a]atrim=start={start}:end={end},"
            f"asetpts=PTS-STARTPTS[aout]"
        )
        audio_args = ['-map', '[aout]']
    else:
        vf = (
            f"[0:v]scale={canvas_w}:{video_h}[v];"
            f"[1:v]scale={canvas_w}:{header_h}[h];"
            f"[2:v]scale={canvas_w}:{hook_h}[k];"
            f"[v][h][k]vstack=inputs=3[stacked];"
            f"[stacked]subtitles='{ass_path}':force_style='Fontname=Inter'[vout]"
        )
        audio_args = []

    cmd = [
        str(ffmpeg_path),
        '-y',
        '-i', str(temp_video),
        '-i', str(temp_header),
        '-i', str(temp_hook),
        '-i', str(source),
        '-filter_complex', vf,
        '-map', '[vout]',
        *audio_args,
        '-c:v', settings.get('video_codec', 'libx264'),
        '-preset', settings.get('video_preset', 'veryfast'),
        '-crf', str(settings.get('video_crf', 20)),
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        str(output_path),
    ]

    run_cmd(cmd)

    # Clean up temp files
    for p in (temp_video, temp_header, temp_hook, ass):
        try:
            p.unlink()
        except OSError:
            pass

    return Path(output_path)

