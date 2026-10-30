import json
import re
import urllib.request

from debate_scorer import (
    multi_dimension_score,
    explain_score,
    score_intensity,
    score_conflict,
    score_question,
    score_surprise,
    score_memorability,
    score_audience_reaction,
    score_completeness,
    score_duration_fit,
)


QUESTION = re.compile(r'\?')

INTENSE = re.compile(
    r'\b('
    r'always|never|obviously|clearly|wrong|right|agree|disagree|'
    r'actually|really|why|how|cannot|can\'t|should|must|truth|'
    r'fact|prove|lie|false'
    r')\b',
    re.I
)

DEBATE_WORDS = re.compile(
    r'\b('
    r'but|however|because|you|your|no|not|incorrect|disagree|'
    r'question|challenge|claim|argument|believe|think|explain|prove'
    r')\b',
    re.I
)


def _score(text, duration):
    """Local fallback score when Ollama is unavailable."""

    words = text.split()

    if not words:
        return 0.0

    question = len(QUESTION.findall(text))
    intensity = len(INTENSE.findall(text))
    debate = len(DEBATE_WORDS.findall(text))

    density = min(len(words) / max(duration, 1), 3.0)

    score = (
        question * 6
        + intensity * 3
        + debate * 1.2
        + density * 10
    )

    return round(min(100, score), 1)


def _overlap_ratio(a, b):
    """Calculate temporal overlap between two candidates."""

    inter = max(
        0,
        min(a['end'], b['end']) -
        max(a['start'], b['start'])
    )

    union = max(a['end'], b['end']) - min(
        a['start'],
        b['start']
    )

    return inter / union if union else 0.0


def _segments_between(segments, start, end):
    """Return transcript segments that overlap a time range."""

    return [
        s for s in segments
        if float(s['end']) > start
        and float(s['start']) < end
    ]


def _text_from_segments(segments):
    """Combine transcript segment text."""

    return ' '.join(
        str(s.get('text', '')).strip()
        for s in segments
    ).strip()


def _snap_to_segments(segments, start, end):
    """
    Snap arbitrary timestamps to real transcript boundaries.

    This prevents the AI from creating timestamps that do not exist
    in the actual transcript.
    """

    if not segments:
        return None, None

    overlapping = _segments_between(
        segments,
        start,
        end
    )

    if not overlapping:
        return None, None

    return (
        float(overlapping[0]['start']),
        float(overlapping[-1]['end'])
    )


def _expand_candidate(candidate, segments):
    """
    Expand only very short AI-selected moments.

    Ollama is responsible for identifying the complete exchange.
    Python preserves Ollama's selected range unless it is extremely
    short, in which case additional surrounding context is inspected.

    Duration is flexible and is not forced to a fixed target.
    """

    try:
        start = float(candidate['start'])
        end = float(candidate['end'])
    except (KeyError, TypeError, ValueError):
        return None

    if end <= start or not segments:
        return None

    video_start = float(segments[0]['start'])
    video_end = float(segments[-1]['end'])

    start = max(video_start, start)
    end = min(video_end, end)

    original_duration = end - start

    # Only expand very short AI selections.
    # Longer selections are assumed to already represent the
    # complete exchange identified by Ollama.
    if original_duration < 12:
        before = 30
        after = 40

        expanded_start = max(
            video_start,
            start - before
        )

        expanded_end = min(
            video_end,
            end + after
        )

    elif original_duration < 20:
        before = 20
        after = 30

        expanded_start = max(
            video_start,
            start - before
        )

        expanded_end = min(
            video_end,
            end + after
        )

    else:
        expanded_start = start
        expanded_end = end

    selected = _segments_between(
        segments,
        expanded_start,
        expanded_end
    )

    if not selected:
        return None

    expanded_start = float(selected[0]['start'])
    expanded_end = float(selected[-1]['end'])

    text = _text_from_segments(selected)

    if len(text.split()) < 20:
        return None

    # Safety ceiling only.
    # This prevents malformed timestamps from creating enormous
    # candidates. It is NOT a target duration.
    if expanded_end - expanded_start > 180:
        expanded_end = expanded_start + 180

        selected = _segments_between(
            segments,
            expanded_start,
            expanded_end
        )

        if selected:
            expanded_end = float(selected[-1]['end'])
            text = _text_from_segments(selected)

    return {
        'start': expanded_start,
        'end': expanded_end,
        'duration': round(
            expanded_end - expanded_start,
            2
        ),
        'text': text,
        'score': float(candidate.get('score', 0)),
        'reason': str(
            candidate.get(
                'reason',
                'AI-identified debate moment.'
            )
        ),
        'topic': str(
            candidate.get(
                'topic',
                ''
            )
        ),
        'attention_factors': candidate.get(
            'attention_factors',
            []
        ),
    }
def _clean_candidate(candidate, segments):
    """
    Validate and expand an AI-selected candidate.
    """

    if not isinstance(candidate, dict):
        return None

    try:
        start = float(candidate['start'])
        end = float(candidate['end'])
    except (KeyError, TypeError, ValueError):
        return None

    if end <= start:
        return None

    # First make sure the AI timestamps actually overlap real
    # transcript material.
    snapped_start, snapped_end = _snap_to_segments(
        segments,
        start,
        end
    )

    if snapped_start is None:
        return None

    cleaned = dict(candidate)
    cleaned['start'] = snapped_start
    cleaned['end'] = snapped_end

    return _expand_candidate(
        cleaned,
        segments
    )


def _build_windows(segments):
    """
    Build broad transcript windows.

    These are context windows for the AI, NOT final clip lengths.

    A broad window lets the model see enough conversation to recognize
    the beginning and end of a complete exchange.
    """

    if not segments:
        return []

    windows = []

    context_seconds = 150.0

    for i, start_segment in enumerate(segments):

        start = float(start_segment['start'])

        collected = []

        for segment in segments[i:]:

            segment_end = float(segment['end'])

            if segment_end - start > context_seconds:
                break

            collected.append(segment)

        if len(collected) < 3:
            continue

        end = float(collected[-1]['end'])

        lines = []

        for segment in collected:

            lines.append(
                "[{:.2f}-{:.2f}] {}".format(
                    float(segment['start']),
                    float(segment['end']),
                    str(
                        segment.get(
                            'text',
                            ''
                        )
                    ).strip()
                )
            )

        windows.append({
            'start': start,
            'end': end,
            'text': '\n'.join(lines)
        })

    return windows


def _build_ai_instruction():
    """Return the main Ollama candidate-detection prompt."""

    return """
You are an attention-focused debate clip editor.

Your task is to identify potentially engaging, COMPLETE moments from
a political debate transcript.

You are NOT predicting virality.

Do NOT invent facts.
Do NOT invent timestamps.
Do NOT judge which political position is correct.
Do NOT favor a speaker because of their political position.

Look for moments such as:

- direct disagreement
- strong challenges
- rebuttals
- intense back-and-forth
- difficult or confrontational questions
- surprising claims
- disputed claims
- controversial subjects
- one speaker pressing another for an answer
- a strong response to a previous statement
- moments that create curiosity or tension
- exchanges that are understandable without the entire video

IMPORTANT:

The interesting sentence is not necessarily the complete clip.

If you find a strong 5-15 second moment, look around it and determine
whether there is a larger exchange containing:

1. The question or claim that started the exchange.
2. The response.
3. A challenge or disagreement.
4. A rebuttal or follow-up.
5. A natural ending.

Prefer the COMPLETE exchange.

Do not cut off:
- a question before its answer
- an argument before the rebuttal
- a rebuttal before the response
- a thought before the speaker finishes it

Do NOT force clips to 20, 30, 50, or 60 seconds.

A strong clip may naturally be:
- 15 seconds
- 30 seconds
- 45 seconds
- 1 minute
- 90 seconds
- 2 minutes
- or longer when the exchange genuinely requires it.

Duration is determined by completeness and relevance, not by a fixed
target.

At the same time, do not include unrelated conversation simply to make
the clip longer.

Use ONLY timestamps that appear in the supplied transcript.

Return ONLY valid JSON in this exact structure:

[
  {
    "start": 0.0,
    "end": 0.0,
    "score": 0,
    "reason": "brief factual explanation of why this exchange is engaging",
    "topic": "brief description of the topic",
    "attention_factors": [
      "direct disagreement",
      "strong rebuttal"
    ]
  }
]

Score means attention potential from 0-100.

It does NOT mean:
- political correctness
- truthfulness
- which speaker is right
- likelihood of winning an argument
- guaranteed virality
"""


def _ollama_request(prompt, model):
    """Send a request to the local Ollama server."""

    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'options': {
            'temperature': 0.1
        }
    }

    request = urllib.request.Request(
        'http://127.0.0.1:11434/api/generate',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json'
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=180
    ) as response:

        body = json.loads(
            response.read().decode('utf-8')
        )

    raw = body.get(
        'response',
        ''
    ).strip()

    if not raw:
        return None

    return json.loads(raw)


def _normalize_ai_response(parsed):
    """Normalize different valid JSON response shapes."""

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):

        if isinstance(
            parsed.get('candidates'),
            list
        ):
            return parsed['candidates']

        if isinstance(
            parsed.get('results'),
            list
        ):
            return parsed['results']

        # Some models return one candidate as an object.
        if (
            'start' in parsed
            and 'end' in parsed
        ):
            return [parsed]

    return []


def _ollama_find_candidates(
    segments,
    model='llama3.2:3b'
):
    """
    Ask Ollama to identify candidate moments from broad transcript
    windows.
    """

    windows = _build_windows(segments)

    if not windows:
        return []

    # Keep processing reasonable on a local 3B model.
    max_windows = 8

    if len(windows) > max_windows:

        step = len(windows) / max_windows

        selected_windows = [
            windows[int(i * step)]
            for i in range(max_windows)
        ]

    else:
        selected_windows = windows

    instruction = _build_ai_instruction()

    all_candidates = []

    for window in selected_windows:

        prompt = (
            instruction
            + "\n\nTRANSCRIPT WINDOW:\n"
            + window['text']
        )

        try:

            parsed = _ollama_request(
                prompt,
                model
            )

            candidates = _normalize_ai_response(
                parsed
            )

            for candidate in candidates:

                cleaned = _clean_candidate(
                    candidate,
                    segments
                )

                if cleaned:
                    all_candidates.append(
                        cleaned
                    )

        except Exception:
            # If one window fails, continue with the remaining
            # windows.
            continue

    return all_candidates


def _detect_question_answer(segments, window_start, window_end):
    """
    Detect question-answer sequences within a time window.

    Returns a list of (question_start, answer_end) tuples.
    """
    qa_pairs = []
    window_segs = [
        s for s in segments
        if float(s['end']) > window_start
        and float(s['start']) < window_end
    ]

    for i, seg in enumerate(window_segs):
        text = str(seg.get('text', '')).strip()
        if '?' not in text:
            continue

        # Found a question — look for the answer
        q_start = float(seg['start'])
        q_end = float(seg['end'])

        # Collect the answer (next 1-3 segments)
        answer_end = q_end
        for j in range(i + 1, min(i + 4, len(window_segs))):
            answer_seg = window_segs[j]
            answer_text = str(answer_seg.get('text', '')).strip()
            if len(answer_text.split()) < 3:
                continue
            answer_end = float(answer_seg['end'])
            # Stop if we hit another question
            if '?' in answer_text:
                break

        if answer_end > q_end + 2:
            qa_pairs.append((q_start, answer_end))

    return qa_pairs


def _snap_to_sentence_boundaries(segments, start, end):
    """
    Snap timestamps to sentence/segment boundaries.

    Avoids cutting people off mid-sentence.
    """
    if not segments:
        return start, end

    # Snap start to nearest segment start
    best_start = start
    best_start_dist = float('inf')
    for s in segments:
        seg_start = float(s['start'])
        dist = abs(start - seg_start)
        if dist < best_start_dist and seg_start <= end:
            best_start_dist = dist
            best_start = seg_start

    # Snap end to nearest segment end
    best_end = end
    best_end_dist = float('inf')
    for s in segments:
        seg_end = float(s['end'])
        dist = abs(end - seg_end)
        if dist < best_end_dist and seg_end >= best_start:
            best_end_dist = dist
            best_end = seg_end

    return best_start, best_end


def _find_hot_moments(segments):
    """
    Find segments that contain debate-relevant signals.

    Returns a list of segment indices that are worth building
    candidates around.
    """
    hot_indices = []
    for i, seg in enumerate(segments):
        text = str(seg.get('text', '')).strip()
        # Check for debate signals
        if '?' in text:
            hot_indices.append(i)
        elif any(w in text.lower() for w in [
            'wrong', 'disagree', 'rebut', 'challenge', 'accuse',
            'deny', 'false', 'lie', 'liar', 'fraud', 'corrupt',
            'never', 'always', 'worst', 'terrible', 'horrible',
            'disgusting', 'shocking', 'outrageous', 'dangerous',
            'destroy', 'failure', 'crisis', 'threat', 'enemy',
            'fact', 'prove', 'truth', 'actually', 'really',
            'but', 'however', 'although', 'despite',
            'interrupt', 'let me finish', 'hold on',
            'applause', 'laughter', 'cheering', 'booing',
        ]):
            hot_indices.append(i)
    return hot_indices


def heuristic_candidates(
    transcript,
    min_seconds=10,
    max_seconds=180
):
    """
    Local fallback candidate detector with multi-dimensional scoring.

    This is only used when Ollama is unavailable or returns no
    usable candidates.

    Uses a hot-moment-centered approach for performance.
    """

    segments = transcript.get(
        'segments',
        []
    )

    if not segments:
        return []

    n = len(segments)

    # Pre-compute segment boundaries for fast lookup
    seg_starts = [float(s['start']) for s in segments]
    seg_ends = [float(s['end']) for s in segments]
    seg_texts = [str(s.get('text', '')).strip() for s in segments]
    seg_word_counts = [len(t.split()) for t in seg_texts]

    # Pre-compute cumulative word counts for fast range queries
    cum_words = [0] * (n + 1)
    for i in range(n):
        cum_words[i + 1] = cum_words[i] + seg_word_counts[i]

    # Find hot moments to build candidates around
    hot_indices = _find_hot_moments(segments)

    # If no hot moments found, use all segments (fallback)
    if not hot_indices:
        hot_indices = list(range(0, n, max(1, n // 20)))

    results = []

    # Generate candidates centered on hot moments
    for hot_idx in hot_indices:
        hot_start = seg_starts[hot_idx]

        # Try different window sizes around the hot moment
        for window_size in [30, 45, 60, 90, 120]:
            # Find start: go back window_size/2 seconds
            target_start = max(0, hot_start - window_size / 2)
            start_idx = _find_nearest_segment_index(
                target_start, seg_starts
            )
            if start_idx is None:
                continue

            # Find end: go forward window_size/2 seconds
            target_end = hot_start + window_size / 2
            end_idx = _find_nearest_segment_index(
                target_end, seg_ends
            )
            if end_idx is None or end_idx < start_idx:
                continue

            start = seg_starts[start_idx]
            end = seg_ends[end_idx]

            # Snap to sentence boundaries
            start, end = _snap_to_sentence_boundaries(segments, start, end)

            duration = end - start

            if duration < min_seconds or duration > max_seconds:
                continue

            word_count = cum_words[end_idx + 1] - cum_words[start_idx]
            if word_count < 25:
                continue

            text = ' '.join(seg_texts[start_idx:end_idx + 1]).strip()

            # Multi-dimensional scoring
            candidate = {
                'start': start,
                'end': end,
                'duration': round(duration, 2),
                'text': text,
            }
            scores = multi_dimension_score(
                candidate, segments
            )

            # Generate explanation
            explanation = explain_score(
                candidate, segments
            )

            results.append({
                'start': start,
                'end': end,
                'duration': round(
                    duration,
                    2
                ),
                'text': text,
                'score': scores['total'],
                'reason': (
                    'Local transcript-based '
                    'candidate.'
                ),
                'topic': '',
                'attention_factors': explanation['reasons'],
                'scores': scores,
            })

    results.sort(
        key=lambda x: x['score'],
        reverse=True
    )

    chosen = []

    for candidate in results:

        if any(
            _overlap_ratio(
                candidate,
                existing
            ) > 0.5
            for existing in chosen
        ):
            continue

        chosen.append(
            candidate
        )

        if len(chosen) >= 20:
            break

    return sorted(
        chosen,
        key=lambda x: x['score'],
        reverse=True
    )


def _find_nearest_segment_index(t, sorted_times):
    """Binary search for the nearest segment index."""
    if not sorted_times:
        return None

    lo, hi = 0, len(sorted_times) - 1

    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_times[mid] < t:
            lo = mid + 1
        elif sorted_times[mid] > t:
            hi = mid - 1
        else:
            return mid

    # Return the closest
    if lo >= len(sorted_times):
        return len(sorted_times) - 1
    if hi < 0:
        return 0
    if abs(sorted_times[lo] - t) < abs(sorted_times[hi] - t):
        return lo
    return hi


def _selection_score(candidate):
    """
    Ranking score used after AI detection.

    Duration is only a small completeness factor.

    It does NOT force a particular clip length.
    """

    score = float(
        candidate.get(
            'score',
            0
        )
    )

    duration = float(
        candidate.get(
            'duration',
            0
        )
    )

    if duration < 10:
        completeness = -25

    elif duration < 15:
        completeness = -15

    elif duration < 30:
        completeness = -5

    elif duration < 45:
        completeness = 0

    elif duration <= 120:
        completeness = 8

    else:
        completeness = 4

    return score + completeness


def _remove_overlapping_candidates(
    candidates,
    maximum=20
):
    """
    Remove heavily overlapping candidates while preserving the
    strongest distinct moments.
    """

    candidates = sorted(
        candidates,
        key=_selection_score,
        reverse=True
    )

    chosen = []

    for candidate in candidates:

        if any(
            _overlap_ratio(
                candidate,
                existing
            ) > 0.55
            for existing in chosen
        ):
            continue

        chosen.append(
            candidate
        )

        if len(chosen) >= maximum:
            break

    return sorted(
        chosen,
        key=_selection_score,
        reverse=True
    )


def ollama_rank(
    candidates,
    model='llama3.2:3b'
):
    """
    Compatibility function for the existing app.py.

    It can rank candidates produced by the older workflow.
    """

    if not candidates:
        return []

    prompt = """
Rank these transcript excerpts for attention potential as short-form
debate clips.

Consider:

- direct disagreement
- strong questions
- rebuttals
- back-and-forth
- disputed subjects
- surprising claims
- completeness
- curiosity
- tension

Do not judge which political position is correct.
Do not invent facts.

Return ONLY valid JSON:

[
  {
    "id": 0,
    "score": 0,
    "reason": "brief factual explanation"
  }
]
"""

    payload = [
        {
            'id': i,
            'start': c.get('start'),
            'end': c.get('end'),
            'text': c.get('text', '')
        }
        for i, c in enumerate(
            candidates[:12]
        )
    ]

    full_prompt = (
        prompt
        + "\n\nCANDIDATES:\n"
        + json.dumps(
            payload,
            ensure_ascii=False
        )
    )

    try:

        parsed = _ollama_request(
            full_prompt,
            model
        )

        ranked = _normalize_ai_response(
            parsed
        )

        if not ranked:
            return candidates

        by_id = {}

        for item in ranked:

            try:
                by_id[
                    int(item['id'])
                ] = item

            except (
                KeyError,
                TypeError,
                ValueError
            ):
                continue

        for i, candidate in enumerate(
            candidates[:12]
        ):

            if i not in by_id:
                continue

            item = by_id[i]

            try:
                ai_score = float(
                    item.get(
                        'score',
                        candidate['score']
                    )
                )

            except (
                TypeError,
                ValueError
            ):
                ai_score = float(
                    candidate['score']
                )

            candidate[
                'ollama_score'
            ] = ai_score

            candidate[
                'reason'
            ] = str(
                item.get(
                    'reason',
                    candidate.get(
                        'reason',
                        ''
                    )
                )
            )

            candidate[
                'score'
            ] = round(
                (
                    float(
                        candidate['score']
                    )
                    + ai_score
                ) / 2,
                1
            )

        return sorted(
            candidates,
            key=lambda x: x['score'],
            reverse=True
        )

    except Exception:
        return candidates


def ai_candidates(
    transcript,
    model='llama3.2:3b'
):
    """
    Main AI-assisted candidate detector.

    Workflow:

    1. Build broad transcript context.
    2. Ask Ollama to identify potentially engaging exchanges.
    3. Validate AI timestamps against the transcript.
    4. Expand short moments into surrounding context.
    5. Score candidates on multiple dimensions.
    6. Remove overlapping candidates.
    7. Return the strongest 5-10 distinct moments with explanations.

    If Ollama fails completely, use the local fallback detector.
    """

    segments = transcript.get(
        'segments',
        []
    )

    if not segments:
        return []

    candidates = _ollama_find_candidates(
        segments,
        model=model
    )

    if not candidates:
        return heuristic_candidates(
            transcript
        )

    # Apply multi-dimensional scoring to each candidate
    for candidate in candidates:
        scores = multi_dimension_score(candidate, segments)
        explanation = explain_score(candidate, segments)
        candidate['scores'] = scores
        candidate['score'] = scores['total']
        candidate['attention_factors'] = explanation['reasons']

    return _remove_overlapping_candidates(
        candidates,
        maximum=10
    )
