from pathlib import Path
import json
import cv2


TRACKER_TYPES = ["CSRT", "KCF", "MOSSE"]


def create_tracker(kind="CSRT"):
    if hasattr(cv2, "legacy"):
        ctor = getattr(
            cv2.legacy,
            f"Tracker{kind}_create",
            None
        )
    else:
        ctor = getattr(
            cv2,
            f"Tracker{kind}_create",
            None
        )

    if ctor is None:
        raise RuntimeError(
            f"OpenCV tracker {kind} is unavailable. "
            "Install opencv-contrib-python."
        )

    return ctor()


def clamp_box(box, frame_width, frame_height):
    if box is None:
        return None

    x, y, w, h = map(float, box)

    x = max(0.0, min(x, frame_width - 2))
    y = max(0.0, min(y, frame_height - 2))

    w = max(2.0, min(w, frame_width - x))
    h = max(2.0, min(h, frame_height - y))

    return [x, y, w, h]


def save_speaker_boxes(
    path: Path,
    charlie_box,
    other_box,
    frame_size,
    frame_time
):
    data = {
        "charlie": list(map(float, charlie_box)),
        "other": list(map(float, other_box)),
        "frame_size": list(frame_size),
        "frame_time": float(frame_time)
    }

    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def load_speaker_boxes(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def track_boxes(
    video_path: Path,
    boxes,
    output_json: Path,
    init_time=0.0,
    end_time=None,
    sample_fps=8,
    tracker_kind="CSRT",
    progress_callback=None,
):
    cap = cv2.VideoCapture(str(video_path))

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open source video for tracking."
        )

    cap.set(
        cv2.CAP_PROP_POS_MSEC,
        init_time * 1000
    )

    ok, frame = cap.read()

    if not ok:
        cap.release()
        raise RuntimeError(
            "Could not seek to the speaker setup frame."
        )

    frame_height, frame_width = frame.shape[:2]

    safe_boxes = {}

    for name, box in boxes.items():
        safe = clamp_box(
            box,
            frame_width,
            frame_height
        )

        if safe is not None:
            safe_boxes[name] = safe

    trackers = {}
    loss_counts = {name: 0 for name in safe_boxes}
    # Allow ~2s of consecutive loss (motion blur, occlusion) before giving up.
    max_loss_frames = max(10, int(fps * 2))

    for name, box in safe_boxes.items():
        tracker = create_tracker(tracker_kind)

        tracker.init(
            frame,
            tuple(map(int, box))
        )

        trackers[name] = tracker

    last_good = {
        name: list(box)
        for name, box in safe_boxes.items()
    }

    frames = [{
        "time": float(init_time),
        **{
            name: list(map(float, box))
            for name, box in safe_boxes.items()
        }
    }]

    step = max(
        1,
        int(round(fps / sample_fps))
    )

    idx = 1

    while True:
        ok, frame = cap.read()

        if not ok:
            break

        t = init_time + idx / fps

        if end_time is not None and t > end_time:
            break

        if idx % step == 0:
            row = {"time": float(t)}

            frame_h, frame_w = frame.shape[:2]

            for name, tracker in trackers.items():

                ok_box, box = tracker.update(frame)

                if ok_box:
                    box = clamp_box(
                        box,
                        frame_w,
                        frame_h
                    )

                if box is not None:
                    loss_counts[name] = 0
                    last_good[name] = box
                    row[name] = [
                        float(v)
                        for v in box
                    ]
                else:
                    # Brief temporary loss: keep the last valid position.
                    # Only abort if the tracker stays lost for too long.
                    loss_counts[name] += step
                    row[name] = (
                        list(last_good[name])
                        if name in last_good
                        else None
                    )

            frames.append(row)

            if loss_counts and max(loss_counts.values()) > max_loss_frames:
                cap.release()
                raise RuntimeError(
                    f"Tracker lost '{max(loss_counts, key=loss_counts.get)}' "
                    f"for more than {max_loss_frames/fps:.1f}s at t={t:.1f}s. "
                    "The frame layout likely changed mid-clip. "
                    "Try adjusting the speaker framing or splitting the clip."
                )

        if progress_callback and idx % (step * 10) == 0:
            total_est = int((end_time - init_time) * fps) if end_time else idx
            progress_callback(idx, total_est, t)

        idx += 1

    cap.release()

    output_json.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_json.write_text(
        json.dumps(
            {
                "fps": fps,
                "sample_fps": sample_fps,
                "frames": frames
            },
            indent=2
        ),
        encoding="utf-8"
    )

    return frames