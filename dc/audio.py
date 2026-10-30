from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

from .core.process import check_cancelled, run_process
from .core.tools import require_tool


def extract_wav(source: Path, output: Path, sample_rate: int = 16000) -> Path:
    output.parent.mkdir(parents=True,exist_ok=True)
    partial=output.with_suffix(output.suffix+".part")
    run_process([require_tool("ffmpeg"), "-y", "-i", source, "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", "-f", "wav", partial], timeout=600)
    partial.replace(output)
    return output


def rms_windows(wav_path: Path, window_s: float = 0.1) -> list[tuple[float, float]]:
    import array
    import sys
    result = []
    with wave.open(str(wav_path), "rb") as audio:
        rate, width, channels = audio.getframerate(), audio.getsampwidth(), audio.getnchannels()
        if width != 2:
            raise ValueError("Only 16-bit PCM is supported")
        size = max(1, int(rate * window_s))
        frame = 0
        while raw := audio.readframes(size):
            check_cancelled()
            values = array.array("h", raw)
            if sys.byteorder != "little":
                values.byteswap()
            result.append((frame / rate, math.sqrt(sum(value * value for value in values) / len(values)) / 32768))
            frame += len(values) // channels
    return result


def energy_activity(windows: list[tuple[float, float]], window_s: float = .1) -> dict[str, Any]:
    """Conservative energy/silence fallback; activity is not speaker identity."""
    if not windows:
        return {"threshold": None, "active_spans": [], "activity_coverage": 0}
    values = sorted(value for _, value in windows)
    floor = values[int((len(values) - 1) * .1)]
    threshold = max(.003, floor * 3)
    spans = []
    for t, value in windows:
        if value < threshold:
            continue
        if spans and t - spans[-1]["end"] <= .2:
            spans[-1]["end"] = round(t + window_s, 3)
        else:
            spans.append({"start": round(t, 3), "end": round(t + window_s, 3)})
    covered = sum(span["end"] - span["start"] for span in spans)
    return {"threshold": threshold, "active_spans": spans, "activity_coverage": covered / max(window_s, windows[-1][0] + window_s), "speech_verified": False}


def acoustic_features(candidate:dict,words:list[dict],windows:list[dict])->dict:
    import statistics
    import bisect
    selected=[word for word in words if candidate["start"]<=word["start"] and word["end"]<=candidate["end"]]
    starts=[word["start"] for word in words]
    def inside_speech(t):
        index=bisect.bisect_right(starts,t)-1
        return index>=0 and t<=words[index]["end"] and words[index].get("prob",1)>=.5
    source_speech=[row["rms"] for row in windows if inside_speech(row["t"])]
    if not source_speech:
        return {"available":False,"reason":"No speech-correlated energy windows"}
    median=statistics.median(source_speech)
    mad=statistics.median(abs(value-median) for value in source_speech)
    if mad<=1e-9:
        return {"available":False,"reason":"Zero acoustic baseline dispersion"}
    events=[]
    active=[]
    for row in windows:
        t=row["t"]
        if t<candidate["start"] or t>candidate["end"]: continue
        speaking=inside_speech(t)
        z=(row["rms"]-median)/(1.4826*mad)
        if speaking and z>=1.5:
            if active and t-active[-1]["t"]>.15:
                if active[-1]["t"]-active[0]["t"]>=.5: events.append({"start":active[0]["t"],"end":active[-1]["t"]+.1,"z_peak":max(item["z"] for item in active)})
                active=[]
            active.append({"t":t,"z":z})
    if active and active[-1]["t"]-active[0]["t"]>=.5:
        events.append({"start":active[0]["t"],"end":active[-1]["t"]+.1,"z_peak":max(item["z"] for item in active)})
    corroborated=[]
    for event in events:
        prior=[word for word in words if word["end"]<=event["start"]]
        following=next((word for word in selected if word["start"]>=event["start"]-.2),None)
        pause=following["start"]-prior[-1]["end"] if prior and following else 0
        rate=sum(event["start"]<=word["start"]<=event["end"] for word in selected)/max(.1,event["end"]-event["start"])
        overall=len(words)/max(1,words[-1]["end"]-words[0]["start"]) if words else 0
        if pause>=.4 or rate>=overall*1.2:
            corroborated.append({**event,"preceding_pause_s":pause,"words_per_second":rate})
    return {"available":True,"engine":"speech-correlated-rms","vad_model_verified":False,"median_rms":median,"mad_rms":mad,"events":corroborated,"value":min(1,len(corroborated)/2)}


def probe_frame_rate(probe: dict[str, Any], fps_cap: float = 30) -> dict[str, Any]:
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
    def parse(value: str | None) -> float:
        if not value or value in {"0/0", "N/A"}:
            return 0.0
        try:
            left, right = str(value).split("/", 1) if "/" in str(value) else (str(value), "1")
            return float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            return 0.0
    nominal, average = parse(video.get("r_frame_rate")), parse(video.get("avg_frame_rate"))
    packet_times=sorted(float(row["pts_time"]) for row in probe.get("packets",[]) if row.get("pts_time") not in {None,"N/A"})
    deltas=[right-left for left,right in zip(packet_times,packet_times[1:]) if right>left]
    cadence_cv=None
    median_rate=None
    if len(deltas)>2:
        import statistics
        mean=statistics.mean(deltas)
        cadence_cv=statistics.pstdev(deltas)/mean
        median_rate=1/statistics.median(deltas)
    normalise = bool(nominal and average and abs(nominal - average) > 0.001)
    normalise=normalise or (cadence_cv is not None and cadence_cv>.01)
    rate = median_rate or average or nominal or fps_cap
    if normalise:
        rate = min((24, 25, 30, 50, 60), key=lambda candidate: abs(candidate - rate))
    target = min(float(fps_cap), rate)
    return {"nominal_fps": nominal, "average_fps": average, "target_cfr": target, "fps_cap": fps_cap, "normalise": normalise, "probe_method": "packet_pts" if deltas else "stream_rates", "packet_cadence_verified": bool(deltas),"pts_delta_cv":cadence_cv,"packet_median_fps":median_rate}
