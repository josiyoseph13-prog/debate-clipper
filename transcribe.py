from pathlib import Path
import json
from faster_whisper import WhisperModel


def transcribe(video_path: Path, output_json: Path, model_size='base'):
    device = 'cpu'
    compute_type = 'int8'
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(str(video_path), word_timestamps=True, vad_filter=True)
    data = {
        'language': info.language,
        'language_probability': info.language_probability,
        'model': model_size,
        'segments': [],
    }
    for seg in segments:
        words = []
        for w in (seg.words or []):
            words.append({'start': float(w.start), 'end': float(w.end), 'word': w.word})
        data['segments'].append({
            'start': float(seg.start), 'end': float(seg.end), 'text': seg.text.strip(), 'words': words
        })
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    return data


def load_transcript(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))
