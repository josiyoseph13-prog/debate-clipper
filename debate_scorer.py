"""
Multi-dimensional debate clip scorer.

Scores candidate clips on multiple dimensions rather than a single
generic score. All scoring is local and $0.
"""
import re


# --- Pattern dictionaries ---

INTENSE_WORDS = re.compile(
    r'\b('
    r'absolutely|completely|totally|utterly|literally|'
    r'disgusting|terrible|horrible|awful|pathetic|'
    r'shocking|outrageous|unbelievable|incredible|'
    r'dangerous|destructive|disastrous|catastrophic|'
    r'liar|lying|lied|fraud|corrupt|corruption|'
    r'stupid|idiotic|moron|incompetent|unfit|'
    r'worst|never|always|everyone knows|no one|'
    r'destroy|destroying|destroyed|failure|failed|'
    r'crisis|emergency|threat|enemy|'
    r'rigged|stolen|cheat|cheating|fraud)\b',
    re.I
)

CONFLICT_WORDS = re.compile(
    r'\b('
    r'wrong|disagree|disagreeing|rebut|rebuttal|'
    r'challenge|challenging|accuse|accusing|accusation|'
    r'deny|denying|denial|refute|refuting|'
    r'but|however|although|despite|nevertheless|'
    r'you\'re wrong|that\'s wrong|that\'s not true|'
    r'not true|false|incorrect|inaccurate|'
    r'fact.?check|misleading|misrepresented|'
    r'interrupt|interrupting|interruption|'
    r'let me finish|hold on|wait a minute)\b',
    re.I
)

QUESTION_PATTERNS = re.compile(
    r'\b('
    r'why|how|what do you|what would|what will|'
    r'can you explain|could you explain|would you explain|'
    r'what is your|what are your|where do you|'
    r'when will|when did|who is|who are|'
    r'isn\'t it|aren\'t it|don\'t you|doesn\'t it|'
    r'will you|would you|can you|could you|'
    r'what about|how about|what happened)\b',
    re.I
)

SURPRISE_WORDS = re.compile(
    r'\b('
    r'surprisingly|shockingly|astonishingly|'
    r'never before|first time|unprecedented|'
    r'reveal|revealing|revelation|expose|exposing|'
    r'secret|hidden|cover.?up|coverup|'
    r'actually|in fact|the truth is|truth is|'
    r'believe it or not|you won\'t believe|'
    r'here\'s the thing|here\'s the problem|'
    r'let me be clear|let me be blunt|'
    r'wake up|open your eyes|)\b',
    re.I
)

MEMORABLE_PATTERNS = re.compile(
    r'\b('
    r'let me tell you|I\'ll tell you|'
    r'mark my words|remember this|'
    r'history will|history remembers|'
    r'the american people deserve|'
    r'we will never|we must|we have to|'
    r'this is not|this isn\'t|'
    r'make no mistake|make no mistake about it|'
    r'at the end of the day|when all is said and done|'
    r'the fact of the matter|the bottom line|'
    r'plain and simple|pure and simple|'
    r'I stand by|I stand by my|'
    r'my record speaks|my record|'
    r'look at the record|check the record)\b',
    re.I
)

AUDIENCE_REACTION = re.compile(
    r'\b('
    r'\[applause\]|\[laughter\]|\[cheering\]|\[booing\]|\[crowd\]|'
    r'audience|crowd|applaud|laugh|cheer|boo|'
    r'(applause)|(laughter)|(cheering))\b',
    re.I
)

# --- Scoring functions ---


def score_intensity(text):
    """Score emotional intensity (0-100)."""
    words = text.split()
    if not words:
        return 0.0

    matches = len(INTENSE_WORDS.findall(text))
    # Normalize: 3+ intense words in a short clip is very high
    score = min(100, matches * 18)
    return round(score, 1)


def score_conflict(text):
    """Score conflict/disagreement level (0-100)."""
    words = text.split()
    if not words:
        return 0.0

    matches = len(CONFLICT_WORDS.findall(text))
    score = min(100, matches * 15)
    return round(score, 1)


def score_question(text):
    """Score question strength and question-answer sequences (0-100)."""
    words = text.split()
    if not words:
        return 0.0

    matches = len(QUESTION_PATTERNS.findall(text))
    # Bonus for question marks
    q_marks = text.count('?')
    score = min(100, matches * 12 + q_marks * 8)
    return round(score, 1)


def score_surprise(text):
    """Score surprising/controversial content (0-100)."""
    words = text.split()
    if not words:
        return 0.0

    matches = len(SURPRISE_WORDS.findall(text))
    score = min(100, matches * 20)
    return round(score, 1)


def score_memorability(text):
    """Score quotable/memorable content (0-100)."""
    words = text.split()
    if not words:
        return 0.0

    matches = len(MEMORABLE_PATTERNS.findall(text))
    score = min(100, matches * 25)
    return round(score, 1)


def score_audience_reaction(text):
    """Score audience reaction indicators (0-100)."""
    matches = len(AUDIENCE_REACTION.findall(text))
    score = min(100, matches * 30)
    return round(score, 1)


def score_completeness(start, end, segments):
    """
    Score whether a clip makes sense as a standalone unit.

    Checks:
    - Starts near a sentence/segment boundary
    - Ends near a sentence/segment boundary
    - Has enough content (not just a few words)
    - Doesn't start or end mid-sentence
    """
    if not segments:
        return 0.0

    score = 50.0  # base score

    # Check start boundary
    start_seg = _find_nearest_segment(start, segments)
    if start_seg:
        seg_start = float(start_seg['start'])
        seg_end = float(start_seg['end'])
        # Good if start is near segment start
        if abs(start - seg_start) < 2.0:
            score += 15
        # Bad if start is near segment end (mid-sentence cut)
        elif abs(start - seg_end) < 1.0:
            score -= 20

    # Check end boundary
    end_seg = _find_nearest_segment(end, segments)
    if end_seg:
        seg_start = float(end_seg['start'])
        seg_end = float(end_seg['end'])
        # Good if end is near segment end
        if abs(end - seg_end) < 2.0:
            score += 15
        # Bad if end is near segment start (cut off beginning)
        elif abs(end - seg_start) < 1.0:
            score -= 20

    # Check content density
    clip_segments = [
        s for s in segments
        if float(s['end']) > start and float(s['start']) < end
    ]
    total_words = sum(
        len(str(s.get('text', '')).split())
        for s in clip_segments
    )
    if total_words < 15:
        score -= 30
    elif total_words < 30:
        score -= 10
    elif total_words > 80:
        score += 10

    return max(0, min(100, round(score, 1)))


def score_duration_fit(duration):
    """
    Score how well the duration fits the ideal range.

    30-180 seconds allowed, 50-60 preferred.
    """
    if duration < 15:
        return -30
    elif duration < 30:
        return -10
    elif duration <= 120:
        return 10  # good range
    elif duration <= 180:
        return 5   # acceptable
    else:
        return -10  # too long


def _find_nearest_segment(t, segments):
    """Find the segment nearest to time t using binary search."""
    if not segments:
        return None

    lo, hi = 0, len(segments) - 1
    best = None
    best_dist = float('inf')

    while lo <= hi:
        mid = (lo + hi) // 2
        seg = segments[mid]
        seg_start = float(seg['start'])
        seg_end = float(seg['end'])
        seg_mid = (seg_start + seg_end) / 2.0
        dist = abs(t - seg_mid)

        if dist < best_dist:
            best_dist = dist
            best = seg

        if t < seg_start:
            hi = mid - 1
        elif t > seg_end:
            lo = mid + 1
        else:
            # t is within this segment
            return seg

    return best


def multi_dimension_score(candidate, segments=None):
    """
    Score a candidate clip on multiple dimensions.

    Returns a dict with individual scores and a weighted total.
    """
    text = candidate.get('text', '')
    duration = float(candidate.get('duration', 0))
    start = float(candidate.get('start', 0))
    end = float(candidate.get('end', 0))

    scores = {
        'intensity': score_intensity(text),
        'conflict': score_conflict(text),
        'question': score_question(text),
        'surprise': score_surprise(text),
        'memorability': score_memorability(text),
        'audience_reaction': score_audience_reaction(text),
        'duration_fit': score_duration_fit(duration),
    }

    if segments:
        scores['completeness'] = score_completeness(
            start, end, segments
        )
    else:
        scores['completeness'] = 50.0

    # Weighted total
    # Conflict and intensity are most important for debate clips
    weights = {
        'intensity': 0.20,
        'conflict': 0.25,
        'question': 0.15,
        'surprise': 0.10,
        'memorability': 0.10,
        'audience_reaction': 0.05,
        'completeness': 0.10,
        'duration_fit': 0.05,
    }

    total = sum(
        scores[k] * weights[k]
        for k in weights
    )
    scores['total'] = round(total, 1)

    return scores


def explain_score(candidate, segments=None):
    """
    Generate a human-readable explanation of why a candidate
    was scored the way it was.
    """
    scores = multi_dimension_score(candidate, segments)
    text = candidate.get('text', '')

    reasons = []

    if scores['conflict'] >= 40:
        reasons.append("Strong conflict/disagreement detected")
    if scores['intensity'] >= 40:
        reasons.append("High emotional intensity")
    if scores['question'] >= 30:
        reasons.append("Contains strong questions")
    if scores['surprise'] >= 30:
        reasons.append("Surprising or controversial claims")
    if scores['memorability'] >= 30:
        reasons.append("Memorable/quotable language")
    if scores['audience_reaction'] >= 30:
        reasons.append("Audience reaction detected")
    if scores['completeness'] >= 70:
        reasons.append("Complete, self-contained exchange")
    elif scores['completeness'] <= 30:
        reasons.append("May lack context (check boundaries)")

    if not reasons:
        reasons.append("Moderate debate content")

    return {
        'scores': scores,
        'reasons': reasons,
    }
