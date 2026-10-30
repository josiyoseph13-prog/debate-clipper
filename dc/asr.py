from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

from .core.config import load_json_config
from .core.io import atomic_write_json


def asr_cache_key(source_sha256: str, model: str, params: dict[str, Any], glossary: dict[str, Any], version: int = 3) -> str:
    from .core.hashing import content_hash
    return content_hash({"source": source_sha256, "model": model, "params": params, "glossary": glossary, "version": version})


def _normal(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def correct_glossary(text: str, terms: list[str], threshold: float = 0.92) -> tuple[str, list[dict[str, Any]]]:
    corrections = []
    for term in terms:
        if not term.strip():
            continue
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.I)
        # Exact canonical terms are already safe; fuzzy correction happens only on word-like spans.
        if pattern.search(text):
            continue
        pieces = text.split()
        for index, piece in enumerate(pieces):
            clean = re.sub(r"[^A-Za-z0-9'-]", "", piece)
            ratio = difflib.SequenceMatcher(None, _normal(clean), _normal(term)).ratio()
            if ratio >= threshold and len(clean) >= max(4, len(term) - 2):
                pieces[index] = piece.replace(clean, term)
                corrections.append({"from": clean, "to": term, "score": round(ratio, 4)})
        text = " ".join(pieces)
    return text, corrections


def apply_glossary(transcript: dict[str, Any], glossary: dict[str, Any] | None = None, threshold: float = 0.92) -> dict[str, Any]:
    glossary = glossary or load_json_config("glossary.json", {"terms": [], "aliases": {}})
    terms = [*map(str, glossary.get("terms", [])), *map(str, glossary.get("aliases", {}).values())]
    corrections = []
    result = json.loads(json.dumps(transcript))
    aliases=glossary.get("aliases",{})
    for segment in result.get("segments", []):
        for alias,canonical in aliases.items():
            segment["text"]=re.sub(rf"\b{re.escape(str(alias))}\b",str(canonical),str(segment.get("text","")),flags=re.I)
        segment["text"], found = correct_glossary(str(segment.get("text", "")), terms, threshold)
        corrections.extend(found)
        for word in segment.get("words", []):
            original=str(word.get("text",word.get("word","")))
            for alias,canonical in aliases.items():
                original=re.sub(rf"\b{re.escape(str(alias))}\b",str(canonical),original,flags=re.I)
            word["text"]=original
            word["text"], found = correct_glossary(str(word.get("text", word.get("word", ""))), terms, threshold)
            word["word"] = word["text"]
            corrections.extend(found)
    result["glossary_corrections"] = corrections
    result["schema_version"] = 5
    return result


def hallucination_guard(transcript: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(transcript))
    flags = []
    previous = ""
    for segment in result.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if text and text == previous:
            flags.append({"type": "repetition", "start": segment.get("start"), "end": segment.get("end")})
        if text and len(set(text.lower().split())) <= 2 and len(text.split()) >= 8:
            flags.append({"type": "low_diversity", "start": segment.get("start"), "end": segment.get("end")})
        previous = text
    result["hallucination_flags"] = flags
    result["speech_coverage"] = result.get("speech_coverage")
    return result


_CUDA_OK: bool | None = None


def _add_cuda_dll_dirs() -> None:
    """Make the pip-installed CUDA runtime DLLs loadable on Windows."""
    import os
    import sys as _sys

    base = Path(_sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for sub in ("cublas/bin", "cudnn/bin"):
        folder = base / sub
        if folder.is_dir():
            try:
                os.add_dll_directory(str(folder))
            except Exception:
                pass
            os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


def _cuda_usable() -> bool:
    """Probe once per process: GPU present and its libraries load."""
    global _CUDA_OK
    if _CUDA_OK is not None:
        return _CUDA_OK
    ok = False
    try:
        _add_cuda_dll_dirs()
        import ctypes

        ctypes.CDLL("cublas64_12.dll")
        ctypes.CDLL("cudnn64_9.dll")
        import ctranslate2

        ok = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        ok = False
    _CUDA_OK = ok
    return ok


def _whisper_params(config, *, local_files_only: bool) -> dict[str, Any]:
    """Effective faster-whisper params from config, with CPU fallback.

    asr.device=cuda is honoured only when the CUDA probe passes; the
    returned dict records fallback_from so transcripts stay honest
    about what actually ran.
    """
    device = str(config.get("asr", "device", default="cpu") or "cpu").lower()
    compute = str(config.get("asr", "compute_type", default="int8") or "int8")
    params: dict[str, Any] = {
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": int(config.get("asr", "cpu_threads", default=4)),
        "local_files_only": local_files_only,
    }
    if device == "cuda":
        if _cuda_usable():
            params["device"] = "cuda"
            params["compute_type"] = compute if compute != "int8" else "int8_float16"
        else:
            params["fallback_from"] = "cuda"
    return params


def transcribe_file(source: Path, output: Path, model: str = "small.en", glossary: dict[str, Any] | None = None, *, no_network: bool = False, config=None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed; install requirements or supply a transcript artifact") from exc
    from .core.config import load_config, ROOT
    from .core.hashing import content_hash, file_hash
    from .core.io import read_json
    from .core.process import check_cancelled
    config=config or load_config()
    glossary=glossary or read_json(ROOT/config.get("asr","glossary_file",default="config/glossary.json"),{"terms":[],"aliases":{}})
    glossary=json.loads(json.dumps(glossary))
    if config.get("asr","auto_glossary_from_metadata",default=True):
        hints=" ".join(str((metadata or {}).get(key,"")) for key in ("title","description"))
        suggested=re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}\b",hints)
        glossary["terms"]=list(dict.fromkeys([*glossary.get("terms",[]),*suggested]))
    requested_model=model
    model_hash=None
    registry=read_json(ROOT/"assets"/"models"/"registry.json",{}) or {}
    if model in registry.get("models",{}):
        from .models import model_spec
        spec=model_spec(model)
        model=str(spec["paths"]["model"].parent)
        model_hash=spec["files"]["model"]["sha256"]
    if no_network and not Path(model).is_dir():
        # faster-whisper supports cache-only identifiers. It must never fetch a
        # tokenizer/model implicitly while running in the offline mode.
        from faster_whisper.utils import download_model
        model=download_model(model,local_files_only=True)
    params=_whisper_params(config,local_files_only=no_network)
    atomic_write_json(output.parent/"asr_progress.json",{"schema_version":5,"stage":"loading_model","model":requested_model,"segments_processed":0})
    _load_params = {key: params[key] for key in ("device", "compute_type", "cpu_threads", "local_files_only")}
    try:
        whisper = WhisperModel(model, **_load_params)
    except Exception:
        if params["device"] == "cpu":
            raise
        # A GPU problem must never break transcription: use the CPU.
        params = {**params, "device": "cpu", "compute_type": "int8", "fallback_from": params.get("fallback_from", "cuda")}
        whisper = WhisperModel(model, **{**_load_params, "device": "cpu", "compute_type": "int8"})
    from faster_whisper.vad import get_speech_timestamps
    # Use the shared FFmpeg decoder. PyAV19 removed metadata_errors, still used
    # by faster-whisper1.2.1's file decoder; passing PCM also avoids duplicate
    # source decoding inside the model and works across Windows codecs.
    from .audio import extract_wav
    import wave
    import numpy as np
    wav_path=output.parent/"audio_16k.wav"
    extract_wav(source,wav_path,16000)
    with wave.open(str(wav_path),"rb") as wav:
        audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype="<i2").astype(np.float32)/32768
    speech=get_speech_timestamps(audio)
    vad_spans=[(row["start"]/16000,row["end"]/16000) for row in speech]
    prompt=", ".join(glossary.get("terms",[]))[:500] or None
    atomic_write_json(output.parent/"asr_progress.json",{"schema_version":5,"stage":"inference","model":requested_model,"segments_processed":0})
    segments, info = whisper.transcribe(audio, word_timestamps=True, vad_filter=True, condition_on_previous_text=False, initial_prompt=prompt)
    data: dict[str, Any] = {"schema_version": 5, "language": info.language, "language_probability": info.language_probability, "model": requested_model, "model_sha256":model_hash,"compute":params,"segments": [],"vad_spans":vad_spans,"source_sha256":file_hash(source),"accuracy_verified":False}
    for segment in segments:
        check_cancelled()
        words = [{"i": index, "start": float(word.start), "end": float(word.end), "text": str(word.word), "word": str(word.word), "prob": float(getattr(word, "probability", 1.0) or 1.0), "speaker": None} for index, word in enumerate(segment.words or [])]
        data["segments"].append({"start": float(segment.start), "end": float(segment.end), "text": str(segment.text).strip(), "words": words,"no_speech_prob":float(segment.no_speech_prob)})
        atomic_write_json(output.parent/"asr_progress.json",{"schema_version":5,"stage":"inference","model":requested_model,"segments_processed":len(data["segments"]),"last_segment_end":segment.end})
    # Coverage is overlap with the measured VAD speech spans, not a guessed
    # percentage based on output length. Join word intervals before counting.
    covered=[]
    for word in sorted((word for row in data["segments"] for word in row["words"]),key=lambda row:row["start"]):
        a,b=max(0,word["start"]-.15),word["end"]+.15
        if covered and a<=covered[-1][1]:covered[-1]=(covered[-1][0],max(b,covered[-1][1]))
        else:covered.append((a,b))
    speech_s=sum(b-a for a,b in vad_spans)
    covered_s=sum(max(0,min(b,d)-max(a,c)) for a,b in vad_spans for c,d in covered)
    data["speech_coverage"]=min(1,covered_s/speech_s) if speech_s else None
    data["coverage_method"]="Silero VAD spans overlapped with union of native word intervals ±150ms; not a word-accuracy score"
    data = hallucination_guard(apply_glossary(data, glossary,float(config.get("asr","correction_min_score",default=.92))))
    data["review_flags"]=[]
    if data["speech_coverage"] is None or data["speech_coverage"]<.9:data["review_flags"].append("ASR_COVERAGE_REVIEW")
    if data["hallucination_flags"]:data["review_flags"].append("ASR_HALLUCINATION_REVIEW")
    if data.get("glossary_corrections"):data["review_flags"].append("ASR_GLOSSARY_REVIEW")
    if data["language"]!="en" or data["language_probability"]<.8:data["review_flags"].append("ASR_LANGUAGE_REVIEW")
    data["cache_key"]=asr_cache_key(data["source_sha256"],requested_model,{**params,"model_hash":model_hash,"vad_filter":True,"condition_on_previous_text":False},glossary)
    atomic_write_json(output, data)
    atomic_write_json(output.parent/"asr_progress.json",{"schema_version":5,"stage":"complete","model":requested_model,"segments_processed":len(data["segments"]),"cache_key":data["cache_key"]})
    return data


def main():
    import argparse
    from .core.config import AppConfig,load_config
    from .core.io import read_json
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--config")
    parser.add_argument("--metadata")
    parser.add_argument("--no-network",action="store_true")
    args=parser.parse_args()
    config_artifact=read_json(Path(args.config),{}) if args.config else {}
    config=AppConfig(config_artifact["config"]) if config_artifact.get("config") else load_config()
    metadata=(read_json(Path(args.metadata),{}) or {}).get("meta",{}) if args.metadata else {}
    transcribe_file(Path(args.source),Path(args.output),config.get("asr","model",default="small.en") or "small.en",no_network=args.no_network,config=config,metadata=metadata)


if __name__=="__main__":
    main()
