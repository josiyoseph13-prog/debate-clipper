from __future__ import annotations

from typing import Any


def diarize_offline(transcript: dict[str, Any]) -> dict[str, Any]:
    """Return transcript turns unchanged when no offline model is installed.

    Unknown is intentional: a heuristic must never invent speaker identity.
    """
    result = {"schema_version": 5, "engine": "heuristic-fallback", "verified": False, "turns": []}
    for index, segment in enumerate(transcript.get("segments", [])):
        result["turns"].append({"i": index, "speaker": segment.get("speaker") or "unknown", "start": segment.get("start", 0), "end": segment.get("end", 0), "confidence": 0.0})
    return result


def choose_engine(preferred: str = "auto", sherpa_available: bool = False, pyannote_available: bool = False) -> str:
    if preferred == "sherpa_onnx" and sherpa_available:
        return "sherpa_onnx"
    if preferred == "pyannote" and pyannote_available:
        return "pyannote"
    if preferred == "auto":
        if sherpa_available:
            return "sherpa_onnx"
        if pyannote_available:
            return "pyannote"
    return "heuristic-fallback"


def diarize_audio(wav_path, model_name: str, engine: str = "sherpa_onnx") -> dict:
    import wave
    import numpy as np
    from .models import model_spec
    spec = model_spec(model_name)
    if engine == "sherpa_onnx":
        import sherpa_onnx
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(spec["paths"]["segmentation"]))),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(spec["paths"]["embedding"]), num_threads=2),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=int(spec.get("num_clusters", -1)), threshold=float(spec.get("threshold", .5))))
        if not config.validate():
            raise ValueError("Invalid sherpa diarization configuration")
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        with wave.open(str(wav_path), "rb") as audio:
            if audio.getframerate() != diarizer.sample_rate or audio.getnchannels() != 1:
                raise ValueError("Diarization requires mono audio at model sample rate")
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768
        turns = [{"start": row.start, "end": row.end, "speaker": f"speaker_{row.speaker}", "confidence": None} for row in diarizer.process(samples).sort_by_start_time()]
    elif engine == "pyannote":
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained(str(spec["paths"]["config"]))
        result = pipeline(str(wav_path))
        annotation = getattr(result, "speaker_diarization", result)
        turns = [{"start": segment.start, "end": segment.end, "speaker": speaker, "confidence": None} for segment, _, speaker in annotation.itertracks(yield_label=True)]
    else:
        raise ValueError("Unknown diarization engine")
    return {"schema_version": 5, "engine": engine, "verified": False, "turns": turns, "model": model_name, "note": "Cluster labels are not person identities; DER gate is not measured"}


def attach_speakers(transcript: dict, turns: list[dict]) -> dict:
    import copy
    result = copy.deepcopy(transcript)
    for segment in result.get("segments", []):
        midpoint = (segment["start"] + segment["end"]) / 2
        active = [turn for turn in turns if turn["start"] <= midpoint <= turn["end"]]
        segment["speaker"] = active[0]["speaker"] if len(active) == 1 else "unknown"
        for word in segment.get("words", []):
            active_words = [turn for turn in turns if turn["start"] <= (word["start"]+word["end"])/2 <= turn["end"]]
            word["speaker"] = active_words[0]["speaker"] if len(active_words) == 1 else "unknown"
    return result
