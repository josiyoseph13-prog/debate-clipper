from __future__ import annotations

import re
from typing import Any


def normalise_replay(heatmap: list[dict[str, Any]] | None, duration: float) -> list[dict[str, float]]:
    if not heatmap:
        return []
    return [{"start": max(0.0, float(row.get("start_time", row.get("start", 0)))), "end": min(duration, float(row.get("end_time", row.get("end", 0)))), "value": max(0.0, min(1.0, float(row.get("value", 0))))} for row in heatmap if float(row.get("end_time", row.get("end", 0))) > float(row.get("start_time", row.get("start", 0)))]


def replay_feature(heatmap: list[dict[str, Any]] | None, start: float, end: float) -> float | None:
    if not heatmap:
        return None
    duration=max(float(row.get("end_time",row.get("end",0))) for row in heatmap)
    rows = normalise_replay(heatmap, duration)
    overlaps = [(row["value"],max(0,min(end,row["end"])-max(start,row["start"]))) for row in rows if row["end"] > start and row["start"] < end]
    if not overlaps:
        return None
    mean=sum(value*seconds for value,seconds in overlaps)/sum(seconds for _,seconds in overlaps)
    return sum(row["value"]<=mean for row in rows)/len(rows)


def timestamp_mentions(comments: list[str], bin_s: int = 15) -> dict[str, int]:
    result: dict[str, int] = {}
    pattern = re.compile(r"(?<!\d)(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?!\d)")
    for comment in comments:
        for hour, minute, second in pattern.findall(comment):
            total = int(hour or 0) * 3600 + int(minute) * 60 + int(second)
            bucket = str((total // bin_s) * bin_s)
            result[bucket] = result.get(bucket, 0) + 1
    return result


def source_hygiene(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    spans = []
    for segment in transcript.get("segments", []):
        text = str(segment.get("text", "")).lower()
        if any(marker in text for marker in ("sponsored by", "use code", "brought to you by", "[music]")):
            spans.append({"start": float(segment["start"]), "end": float(segment["end"]), "kind": "non_content", "reason": "sponsor_or_music"})
    return spans


def reaction_events(wav_path,model_name:str,minimum_confidence:float=.5)->list[dict]:
    import wave
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks.python.components.containers import audio_data
    from .models import model_spec
    spec=model_spec(model_name)
    classifier=mp.tasks.audio.AudioClassifier.create_from_options(mp.tasks.audio.AudioClassifierOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(spec["paths"]["model"]))))
    events=[]
    with wave.open(str(wav_path),"rb") as audio:
        rate=audio.getframerate()
        for second in range(int(audio.getnframes()/rate)):
            samples=np.frombuffer(audio.readframes(rate),dtype="<i2").astype(np.float32)/32768
            result=classifier.classify(audio_data.AudioData.create_from_array(samples,sample_rate=rate))
            for window in result:
                for head in window.classifications:
                    for category in head.categories:
                        label=category.category_name.lower()
                        if category.score>=minimum_confidence and label in {"applause","laughter","cheering","jeering"}:
                            events.append({"start":second,"end":second+1,"kind":label,"confidence":float(category.score)})
    classifier.close()
    return events
