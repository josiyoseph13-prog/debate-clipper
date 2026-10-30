from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .audio import energy_activity, extract_wav, probe_frame_rate, rms_windows
from .core.hashing import content_hash
from .core.checkpoints import StageCheckpoints
from .core.io import atomic_write_json, read_json
from .core.process import ProcessCancelled, run_process
from .core.tools import require_tool
from .craft import receipt_pair
from .signals import replay_feature, source_hygiene


def _stage_key(source: dict[str, Any], name: str, params: dict[str, Any]) -> str:
    return content_hash({"source": source.get("fingerprint", {}).get("sha256"), "stage": name, "params": params})


def _scene_shots(source: Path, duration: float) -> list[dict[str, Any]]:
    """Use FFmpeg's cheap scene detector; unknown remains a valid fallback."""
    try:
        # Downsample before scene analysis: this keeps long 4K/20-minute
        # sources bounded while retaining useful cut candidates. The original
        # source remains the render input and is never replaced by this proxy.
        output = run_process([require_tool("ffmpeg"), "-hide_banner", "-i", source, "-vf", "fps=2,scale=320:-2:flags=fast_bilinear,select=gt(scene\\,0.35),showinfo", "-an", "-f", "null", "-"], timeout=max(180, int(duration * 1.5)), output_limit=200_000)
        times = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", output)]
    except ProcessCancelled:
        raise
    except Exception:
        times = []
    boundaries = [0.0, *[value for value in times if 0 < value < duration], duration]
    boundaries = sorted(set(round(value, 3) for value in boundaries))
    shots = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        shots.append({"i": index, "start": start, "end": end, "layout": "unknown", "confidence": 0.0, "reason": "visual layout classification unavailable"})
    return shots or [{"i": 0, "start": 0.0, "end": duration, "layout": "unknown", "confidence": 0.0, "reason": "scene detector unavailable"}]


def _audio_artifact(source: Path, job_dir: Path, source_artifact: dict[str, Any]) -> dict[str, Any]:
    if not source_artifact.get("has_audio"):
        return {"schema_version": 5, "engine": "none", "sample_rate": 16000, "windows": [], "vad_coverage": None, "duration_delta": None}
    wav_path = job_dir / "audio_16k.wav"
    try:
        extract_wav(source, wav_path, 16000)
        windows = rms_windows(wav_path)
        import wave
        with wave.open(str(wav_path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
        return {"schema_version": 5, "engine": "rms-fallback", "sample_rate": 16000, "windows": [{"t": t, "rms": rms} for t, rms in windows], "vad_coverage": None, "energy_activity": energy_activity(windows), "duration": duration, "duration_delta": duration - float(source_artifact["duration"])}
    except ProcessCancelled:
        raise
    except Exception as exc:
        return {"schema_version": 5, "engine": "unavailable", "sample_rate": 16000, "windows": [], "vad_coverage": None, "error": str(exc)}


def write_analysis_artifacts(job_dir, source: dict[str, Any], transcript: dict[str, Any], graph: dict[str, Any], config) -> dict[str, Any]:
    """Run the cheap offline analysis stages and persist cache-keyed artifacts."""
    from .core.telemetry import stage_timer
    duration = float(source.get("duration", 0))
    source_path = Path(source["path"])
    checkpoints=StageCheckpoints(job_dir)
    def save(name,artifact,key,files=None):
        artifact.update({"schema_version":5,"cache_key":key})
        atomic_write_json(job_dir/f"{name}.json",artifact)
        files=files or [f"{name}.json"]
        if all((job_dir/file).is_file() for file in files):checkpoints.commit(name,key,files)
    shots_key = _stage_key(source, "shots", {"scene_threshold": 0.35, "fps": 2, "width": 320, "version": 3})
    shots = read_json(job_dir / "shots.json", {}) or {}
    if not checkpoints.valid("shots",shots_key,["shots.json"]):
        with stage_timer(job_dir,"shots",extra={"cache_key":shots_key}):
            shots = {"schema_version": 5, "cache_key": shots_key, "analysis_fps": 2, "shots": _scene_shots(source_path, duration)}
            from .vision import classify_shots
            shots["shots"] = classify_shots(source_path, shots["shots"])
            save("shots",shots,shots_key)
    acoustics_key = _stage_key(source, "acoustics", {"rate": 16000, "window": 0.1, "version": 2})
    acoustics = read_json(job_dir / "acoustics.json", {}) or {}
    acoustic_files=["acoustics.json",*(["audio_16k.wav"] if source.get("has_audio") else [])]
    if not checkpoints.valid("acoustics",acoustics_key,acoustic_files):
        with stage_timer(job_dir,"acoustics",extra={"cache_key":acoustics_key}):
            acoustics = _audio_artifact(source_path, job_dir, source)
            save("acoustics",acoustics,acoustics_key,acoustic_files)
    from .core.config import ROOT
    registry=(read_json(ROOT/"assets"/"models"/"registry.json",{}) or {}).get("models",{})
    diarization_model=config.get("diarization","model")
    turns_key=_stage_key(source,"turns",{"graph":content_hash(graph),"diarization":config.get("diarization"),"model":registry.get(diarization_model),"version":2})
    turns=read_json(job_dir/"turns.json",{}) or {}
    if not checkpoints.valid("turns",turns_key,["turns.json"]):
        with stage_timer(job_dir,"turns",extra={"cache_key":turns_key}):
            turns={"turns":graph.get("turns",[]),"engine":"transcript-tags-or-unknown"}
            if diarization_model and (job_dir/"audio_16k.wav").exists():
                from .diarization import diarize_audio
                try:
                    turns.update(diarize_audio(job_dir/"audio_16k.wav",diarization_model,config.get("diarization","engine",default="sherpa_onnx")))
                except (ImportError,RuntimeError,ValueError) as exc:
                    turns["fallback_reason"]=str(exc)
            save("turns",turns,turns_key)
    source_meta = source.get("meta", {}) or {}
    heatmap = source_meta.get("heatmap")
    reaction_model=config.get("signals","reaction_events","model")
    signals_key=_stage_key(source,"signals",{"heatmap":heatmap,"mentions":source_meta.get("crowd_mentions"),"transcript":content_hash(transcript),"settings":config.get("signals"),"model":registry.get(reaction_model),"fps_cap":config.get("output","fps_cap",default=30),"version":2})
    signals=read_json(job_dir/"signals.json",{}) or {}
    if not checkpoints.valid("signals",signals_key,["signals.json"]):
        with stage_timer(job_dir,"signals",extra={"cache_key":signals_key}):
            signals={"reaction_events":[],"crowd_replay":heatmap or None,"crowd_mentions":source_meta.get("crowd_mentions"),"non_content":source_hygiene(transcript),"available_weights":["crowd"] if heatmap else []}
            if reaction_model and config.get("signals","reaction_events","enabled",default=True):
                from .signals import reaction_events
                try:
                    signals["reaction_events"]=reaction_events(job_dir/"audio_16k.wav",reaction_model,config.get("signals","reaction_events","min_conf",default=.5))
                except (ImportError,RuntimeError,ValueError) as exc:
                    signals["reaction_fallback_reason"]=str(exc)
            signals["frame_rate"]=probe_frame_rate(source.get("probe",{}),float(config.get("output","fps_cap",default=30)))
            save("signals",signals,signals_key)
    artifacts: dict[str, Any] = {"shots": shots, "acoustics": acoustics, "turns": turns, "signals": signals}
    receipt = receipt_pair(transcript, config)
    if receipt:
        artifacts["receipt"] = receipt
    if receipt:
        save("receipt",receipt,_stage_key(source,"receipt",{"transcript":content_hash(transcript),"settings":config.get("semantic","receipts")}))
    return artifacts
