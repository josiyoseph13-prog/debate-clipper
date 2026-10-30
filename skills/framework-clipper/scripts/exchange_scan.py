#!/usr/bin/env python3
"""exchange_scan.py — find complete debate EXCHANGES in a word-timestamped transcript.

Implements the Mind Clash framework rule: the unit of selection is an exchange
(question -> build -> verdict), never a bare time window.

Input: faster-whisper style transcript JSON ({"segments": [{start, end, text, words:[...]}]})
       — the exact shape Debate Clipper writes (work/<job>/transcript.json).

Output: ranked candidate exchanges with the checks that matter printed per candidate:
  - START: first line type (question / claim / other) and whether it is connective tissue
  - END:   last line type — a window ending on '?' (open question) is flagged BAD END,
           because the framework's endings are verdicts, never unanswered questions
  - length in the 24–52s hit band scores higher; more turns score higher

Usage: exchange_scan.py <transcript.json> [--min 18] [--max 65] [--top 15]
Pure stdlib. Read-only.
"""
import argparse, json, re, sys

CONNECTIVE_STARTS = (
    "which is", "this which", "and so", "so then", "but then", "and then",
    "because", "which", "that if", "is that", "this is that",
)

def seg_line(s):
    return (s.get("text") or "").strip()

def line_type(text):
    t = text.strip()
    if t.endswith("?"):
        return "question"
    if t.endswith("!"):
        return "exclaim"
    if t.endswith("."):
        return "statement"
    return "fragment"

def score_window(segs, i, j):
    dur = segs[j]["end"] - segs[i]["start"]
    first, last = seg_line(segs[i]), seg_line(segs[j])
    ft, lt = line_type(first), line_type(last)
    score, notes = 0, []
    # START rules
    if ft == "question":
        score += 3; notes.append("starts on a question")
    elif ft == "statement" and len(first.split()) <= 14:
        score += 2; notes.append("starts on a short claim")
    low = first.lower().lstrip(" \u201c\"'")
    if any(low.startswith(c) for c in CONNECTIVE_STARTS):
        score -= 3; notes.append("BAD START: connective tissue")
    if ft == "fragment":
        score -= 1; notes.append("start line is a fragment (ok only if the fragment IS the claim)")
    # END rules
    if lt == "question":
        score -= 4; notes.append("BAD END: open question, answer cut off")
    elif lt in ("statement", "exclaim"):
        score += 3; notes.append("ends on a full line (verdict candidate)")
    if lt == "fragment":
        score -= 2; notes.append("WEAK END: fragment, likely mid-thought")
    # shape rules
    turns = j - i + 1
    if turns >= 6:
        score += 2; notes.append(f"{turns} lines (real exchange)")
    elif turns <= 3:
        score -= 1; notes.append("few lines, may be one speech not an exchange")
    if 24 <= dur <= 52:
        score += 2; notes.append("length in the 24-52s hit band")
    return score, notes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--min", type=float, default=18.0)
    ap.add_argument("--max", type=float, default=65.0)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    t = json.load(open(a.transcript, encoding="utf-8-sig"))
    segs = [s for s in t.get("segments", []) if seg_line(s)]
    if not segs:
        print("no segments with text"); return 1
    cands = []
    for i in range(len(segs)):
        for j in range(i, len(segs)):
            dur = segs[j]["end"] - segs[i]["start"]
            if dur < a.min:
                continue
            if dur > a.max:
                break
            score, notes = score_window(segs, i, j)
            cands.append((score, i, j, dur, notes))
    cands.sort(key=lambda x: -x[0])
    # de-duplicate near-identical windows (same start segment, keep best end)
    seen, out = set(), []
    for c in cands:
        if c[1] in seen:
            continue
        seen.add(c[1]); out.append(c)
        if len(out) >= a.top:
            break
    for score, i, j, dur, notes in out:
        print(f"score {score:+d} | {segs[i]['start']:.2f}-{segs[j]['end']:.2f} | {dur:.1f}s")
        print(f"  FIRST: {seg_line(segs[i])[:130]}")
        print(f"  LAST : {seg_line(segs[j])[:130]}")
        print(f"  notes: {'; '.join(notes)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
