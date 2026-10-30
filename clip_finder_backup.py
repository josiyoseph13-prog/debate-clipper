import json
import re
import urllib.request
import urllib.error

QUESTION = re.compile(r'\?')
INTENSE = re.compile(r'\b(always|never|obviously|clearly|wrong|right|agree|disagree|actually|really|why|how|cannot|can\'t|should|must|truth|fact|prove|lie|false)\b', re.I)


def _score(text, duration):
    words = text.split()
    if not words:
        return 0.0
    question = len(QUESTION.findall(text))
    intensity = len(INTENSE.findall(text))
    turns = len(re.findall(r'\b(you|your|but|however|because)\b', text, re.I))
    density = min(len(words) / max(duration, 1), 3.0)
    return round(min(100, question * 7 + intensity * 4 + turns * 1.5 + density * 12), 1)


def heuristic_candidates(transcript, min_seconds=20, max_seconds=60):
    segs = transcript.get('segments', [])
    if not segs:
        return []
    results = []
    for i, start_seg in enumerate(segs):
        start = start_seg['start']
        end = start
        texts = []
        for seg in segs[i:]:
            if seg['end'] - start > max_seconds:
                break
            end = seg['end']
            texts.append(seg['text'])
            if end - start >= min_seconds:
                text = ' '.join(texts).strip()
                if len(text.split()) >= 35:
                    score = _score(text, end-start)
                    results.append({'start': start, 'end': end, 'duration': end-start, 'text': text, 'score': score})
                break
    # Non-maximal suppression by overlap, keep stronger candidates.
    results.sort(key=lambda x: x['score'], reverse=True)
    chosen = []
    for r in results:
        overlap = False
        for c in chosen:
            inter = max(0, min(r['end'], c['end']) - max(r['start'], c['start']))
            union = max(r['end'], c['end']) - min(r['start'], c['start'])
            if union and inter / union > 0.5:
                overlap = True
                break
        if not overlap:
            chosen.append(r)
        if len(chosen) >= 20:
            break
    return sorted(chosen, key=lambda x: x['score'], reverse=True)


def ollama_rank(candidates, model='llama3.2:3b'):
    prompt = ('Rank these transcript excerpts for short-form debate clipping. Return JSON array with '
              'scores 0-100 and brief reasons. Do not invent facts.\n\n' +
              json.dumps([{'id':i, 'text':c['text']} for i,c in enumerate(candidates[:12])], ensure_ascii=False))
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate',
                                 data=json.dumps({'model': model, 'prompt': prompt, 'stream': False}).encode(),
                                 headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read().decode())
        text = body.get('response','')
        match = re.search(r'\[.*\]', text, re.S)
        if not match:
            return candidates
        ranked = json.loads(match.group(0))
        by_id = {int(x['id']): x for x in ranked}
        for i,c in enumerate(candidates[:12]):
            if i in by_id:
                c['ollama_score'] = float(by_id[i].get('score', c['score']))
                c['reason'] = str(by_id[i].get('reason',''))
                c['score'] = round((c['score'] + c['ollama_score']) / 2, 1)
        return sorted(candidates, key=lambda x:x['score'], reverse=True)
    except Exception:
        return candidates
