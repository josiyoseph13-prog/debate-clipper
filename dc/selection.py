from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .captions import transcript_words
from .core.config import AppConfig, load_json_config
from .core.hashing import content_hash
from .signals import replay_feature, source_hygiene


def _normal(text: str) -> str:
    return re.sub(r"[^\w ]", " ", text.lower()).strip()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _has(text: str, phrases: list[str]) -> list[str]:
    normal = _normal(text)
    return [phrase for phrase in phrases if _normal(phrase) in normal]


def _iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    intersection = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return intersection / union if union else 0.0


def _similarity(a: str, b: str) -> float:
    aa, bb = Counter(_tokens(a)), Counter(_tokens(b))
    denominator = math.sqrt(sum(value * value for value in aa.values()) * sum(value * value for value in bb.values()))
    return sum(aa[key] * bb[key] for key in aa.keys() & bb.keys()) / denominator if denominator else 0.0


def integrity_flags(text: str, rights_class: str = "unknown", edited: bool = False, claim_checked: bool = False) -> list[dict[str, Any]]:
    flags = []
    normal = text.lower()
    if rights_class == "unknown":
        flags.append({"code": "I-8", "severity": "block_auto_approve", "reason": "Source rights are unknown"})
    if re.search(r"\b\d[\d,.]*\b|\b(studies show|the data|million|billion)\b", normal) and not claim_checked:
        flags.append({"code": "I-7", "severity": "review", "reason": "Checkable claim needs user verification"})
    if any(marker in normal for marker in ("they say", "my opponent claims", "some people argue")):
        flags.append({"code": "I-1", "severity": "review", "reason": "Quoted or reframed speech"})
    if any(marker in normal for marker in ("let's say", "imagine", "hypothetically")):
        flags.append({"code": "I-5", "severity": "review", "reason": "Hypothetical or sarcasm requires review"})
    if re.search(r"\b(voting|ballot|election|polling place|vote count)\b", normal):
        flags.append({"code": "I-10", "severity": "review", "reason": "Election-related content"})
    if edited:
        flags.append({"code": "I-3", "severity": "review", "reason": "Multi-segment or tightened edit"})
    return flags


def can_auto_approve(candidate: dict[str, Any], threshold: float = 90) -> bool:
    return float(candidate.get("score", 0)) >= threshold and not any(flag.get("severity") in {"review", "block_auto_approve"} for flag in candidate.get("integrity_flags", [])) and not any(not claim.get("claim_checked") for claim in candidate.get("claims", [])) and float(candidate.get("boundary", {}).get("confidence", 0)) >= 0.8 and float(candidate.get("layout_confidence", 0)) >= 0.8 and candidate.get("archetype") != "A2"


def claims_in_text(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims = []
    claim_terms = {"data", "study", "studies", "percent", "million", "billion", "trillion", "statute", "law", "record"}
    for word in words:
        token = str(word["text"]).strip(".,!?()[]").lower()
        if re.search(r"\d", token) or token in claim_terms:
            claims.append({"word_i": word["i"], "text": word["text"], "start": word["start"], "end": word["end"], "claim_checked": False, "source_url": None})
    return claims


def headline_fidelity(headline: str, text: str) -> bool:
    source_tokens = set(_tokens(text))
    headline_tokens = _tokens(headline)
    common = {"should", "is", "the", "a", "an", "be", "actually", "working", "case", "for", "why", "need", "to", "we", "and", "or", "answers", "question"}
    return all(token in source_tokens or token in common for token in headline_tokens)


def context_sufficiency(text: str, first_sentence: dict[str, Any] | None = None) -> dict[str, Any]:
    tokens = _tokens(text)
    leading_reference = bool(tokens and tokens[0] in {"that", "this", "it", "he", "she", "they", "those", "as", "said"})
    entities = [token for token in tokens if len(token) >= 5 and token not in {"because", "there", "which", "would", "could", "about"}]
    passed = not leading_reference and bool(entities)
    return {"passed": passed, "leading_anaphora": leading_reference, "entity": entities[0] if entities else None, "reason": "leading reference lacks an antecedent" if leading_reference else ("no topic entity in opening" if not entities else "context sufficient")}


def build_graph(transcript: dict[str, Any]) -> dict[str, Any]:
    english=str(transcript.get("language","en")).lower().split("-")[0]=="en"
    lexicon = load_json_config("lexicons/debate.json", {}) if english else {}
    sentences = []
    turns = []
    word_index = 0
    previous_speaker = None
    for index, segment in enumerate(transcript.get("segments", [])):
        words = transcript_words({"segments": [segment]})
        text = str(segment.get("text", "")).strip()
        speaker = segment.get("speaker") or (words[0].get("speaker") if words else None) or "unknown"
        terminal = text[-1] if text and text[-1] in ".?!" else "none"
        dangling = _tokens(text)[-1:] and _tokens(text)[-1] in {"and", "but", "because", "so", "that", "which", "if", "the", "a", "to", "of", "with"}
        next_segment=transcript.get("segments",[])[index+1] if index+1<len(transcript.get("segments",[])) else None
        pause=float(next_segment.get("start",0))-float(segment.get("end",0)) if next_segment else 1
        complete = (terminal != "none" or pause>=.45) and not dangling
        sentence = {"i": index, "w0": word_index, "w1": word_index + max(0, len(words) - 1), "terminal": terminal, "speaker": speaker, "complete": complete, "text": text, "start": float(segment.get("start", 0)), "end": float(segment.get("end", 0))}
        sentences.append(sentence)
        turns.append({"i": index, "speaker": speaker, "start": sentence["start"], "end": sentence["end"], "s0": index, "s1": index, "wps": len(words) / max(0.01, sentence["end"] - sentence["start"]), "gap_before": sentence["start"] - (sentences[index - 1]["end"] if index else 0), "text": text})
        word_index += len(words)
        previous_speaker = speaker
    edges = []
    for index, sentence in enumerate(sentences):
        if index == 0:
            continue
        previous = sentences[index - 1]
        for family, edge_type in (("challenge", "challenges"), ("evasion", "rebuts"), ("concession", "concedes"), ("contradiction", "contradicts")):
            hits = _has(sentence["text"], lexicon.get(family, []))
            if hits:
                edges.append({"type": edge_type, "from": index - 1, "to": index, "p": 0.65, "evidence": [{"cue": hit, "w": [sentence["w0"], sentence["w1"]]} for hit in hits]})
        if english and previous["terminal"] == "?" and sentence["start"] - previous["end"] <= 3.0:
            answer_index = index
            while answer_index < len(sentences) and (_normal(sentences[answer_index]["text"]) in {"well", "look", "so", "yeah", "um", "i mean", "okay", "great question", "applause", "laughter"} or re.fullmatch(r"thank you(?:\s+\w+){0,3}",_normal(sentences[answer_index]["text"])) or len(_tokens(sentences[answer_index]["text"])) < 3):
                answer_index += 1
            if answer_index < len(sentences) and sentences[answer_index]["start"] - previous["end"] <= 3.0 and (previous["speaker"]=="unknown" or sentences[answer_index]["speaker"]=="unknown" or previous["speaker"]!=sentences[answer_index]["speaker"]):
                answer = sentences[answer_index]
                edges.append({"type": "answers", "from": index - 1, "to": answer_index, "p": 0.6, "evidence": [{"cue": "question followed by substantive reply", "w": [previous["w0"], answer["w1"]]}]})
    return {"schema_version": 5, "sentences": sentences, "turns": turns, "edges": edges}


def refine_boundaries(words: list[dict[str, Any]], start: float, end: float, duration: float) -> dict[str, Any]:
    selected = [word for word in words if word["start"] >= start - 0.001 and word["end"] <= end + 0.001]
    if not selected:
        return {"start": start, "end": end, "confidence": 0.0, "flags": ["no_words"]}
    first, last = selected[0], selected[-1]
    refined_start = max(0.0, first["start"] - 0.12)
    previous = [word for word in words if word["end"] <= first["start"] and word["i"] != first["i"]]
    if previous:
        refined_start = max(refined_start, min(first["start"],previous[-1]["end"] + 0.01))
    refined_end = min(duration, last["end"] + 0.35)
    following = [word for word in words if word["start"] >= last["end"] and word["i"] != last["i"]]
    if following:
        refined_end = min(refined_end, following[0]["start"] - 0.08)
    flags = []
    if refined_end < last["end"]:
        refined_end = last["end"]
        flags.append("next_word_overlap")
    return {"start": round(refined_start, 3), "end": round(refined_end, 3), "confidence": 0.85 if not flags else 0.55, "flags": flags, "first_word_lead": round(first["start"] - refined_start, 3), "last_word_tail": round(refined_end - last["end"], 3)}


def score_candidate(text: str, duration: float, config: AppConfig, archetype: str, flags: list[dict[str, Any]], crowd: float | None = None) -> tuple[float, dict[str, float], list[dict[str, Any]]]:
    lexicon = load_json_config("lexicons/debate.json", {})
    tokens = _tokens(text)
    question = "?" in text or bool(tokens and tokens[0] in {"why", "what", "how", "should", "who", "when", "where"})
    challenges = len(_has(text, lexicon.get("challenge", [])))
    response = archetype in {"A1", "A3", "A4", "A6"}
    complete = text.rstrip().endswith((".", "?", "!"))
    unresolved = bool(tokens and tokens[0] in {"that", "this", "it", "he", "she", "they", "those"})
    rate = len(tokens) / max(duration, 1)
    components = {"narrative": 0.9 if response and complete else 0.65, "conflict": min(1.0, 0.25 + challenges * 0.18), "hook": 0.9 if question else 0.6, "clarity": max(0.2, min(1.0, 1.0 - abs(rate - 2.6) / 3)), "rebuttal": 0.85 if response else 0.5, "ending": 0.9 if complete else 0.35, "context": 0.45 if unresolved else 0.9, "acoustic": 0.0}
    if crowd is not None:
        components["crowd"] = crowd
    weights = config.get("selection", "weights", default={})
    available = {key: weight for key, weight in weights.items() if key in components and key != "acoustic"}
    score = 100 / sum(available.values()) * sum(float(weight) * components[key] for key, weight in available.items())
    penalties = []
    if unresolved:
        penalties.append({"name": "missing_context", "value": 12})
    if any(flag["severity"] == "review" for flag in flags):
        penalties.append({"name": "integrity_review", "value": 6})
    score -= min(40, sum(penalty["value"] for penalty in penalties))
    return round(max(0, min(100, score)), 1), components, penalties


def select_candidates(transcript: dict[str, Any], source: dict[str, Any], config: AppConfig, top: int = 8) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from .craft import evidence_card, question_chip
    graph = build_graph(transcript)
    words = transcript_words(transcript)
    sentences = graph["sentences"]
    if not sentences:
        return graph, []
    duration = float(source.get("duration", words[-1]["end"] + 0.35 if words else 0))
    english=str(transcript.get("language","en")).lower().split("-")[0]=="en"
    lexicon = load_json_config("lexicons/debate.json", {}) if english else {}
    candidates = []
    non_content = source_hygiene(transcript)
    for index, sentence in enumerate(sentences):
        text = sentence["text"]
        normal = text.lower()
        question = sentence["terminal"] == "?"
        challenge = bool(_has(text, lexicon.get("challenge", [])))
        concession = bool(_has(text, lexicon.get("concession", [])))
        evasion = bool(_has(text, lexicon.get("evasion", [])))
        heat=source.get("meta",{}).get("heatmap")
        crowd_anchor=replay_feature(heat,sentence["start"],sentence["end"])
        if not (question or challenge or concession or evasion or (crowd_anchor is not None and crowd_anchor>=.9) or index % 5 == 0):
            continue
        start_index = max(0, index - (1 if challenge or evasion else 0))
        while start_index > 0:
            previous_sentence = sentences[start_index - 1]
            current_text = str(sentences[start_index]["text"]).lstrip()
            if previous_sentence["terminal"] == "none" or (current_text and current_text[0].islower()):
                start_index -= 1
            else:
                break
        selected = []
        for row in sentences[start_index:]:
            if row["end"] - sentences[start_index]["start"] > config.get("selection", "hard_max_s", default=180):
                break
            selected.append(row)
            if row["end"] - sentences[start_index]["start"] >= 25 and row["complete"]:
                break
        if not selected:
            continue
        start, end = selected[0]["start"], selected[-1]["end"]
        boundary = refine_boundaries(words, start, end, duration)
        if not selected[-1]["complete"]:
            boundary["flags"] = [*boundary.get("flags", []), "truncated_ending"]
            boundary["confidence"] = min(float(boundary.get("confidence", 0.0)), 0.55)
        start, end = boundary["start"], boundary["end"]
        interval_words=[word for word in words if word["end"]>start and word["start"]<end]
        if end - start < config.get("selection", "hard_min_s", default=8) or end-start>config.get("selection","hard_max_s",default=180):
            continue
        if any(word["start"]+.04<start<word["end"]-.04 or word["start"]+.04<end<word["end"]-.04 for word in interval_words):
            continue
        confidence=sum(word["prob"] for word in interval_words)/max(1,len(interval_words))
        if confidence<.45: continue
        text = " ".join(row["text"] for row in selected)
        archetype = "A4" if concession else "A6" if evasion else "A1" if challenge else "A3" if question else "A7"
        flags = integrity_flags(text, source.get("rights_class", "unknown"))
        if transcript.get("review_flags"):
            flags.append({"code":"ASR_REVIEW","severity":"review","reason":"Transcript guard requires review","evidence":transcript["review_flags"]})
        if not english:
            flags.append({"code":"LANGUAGE_REVIEW","severity":"review","reason":"Source language has no measured selection/ASR gate"})
        claims = claims_in_text([word for word in words if start <= word["start"] <= end])
        if claims and not any(flag.get("code") == "I-7" for flag in flags):
            flags.append({"code": "I-7", "severity": "review", "reason": "Checkable claim needs user verification"})
        context = context_sufficiency(text, selected[0])
        if "truncated_ending" in boundary.get("flags", []):
            flags.append({"code": "I-2", "severity": "review", "reason": "Candidate ended on an incomplete sentence"})
        if not context["passed"]:
            flags.append({"code": "I-2", "severity": "review", "reason": context["reason"]})
        overlap = sum(max(0, min(end, span["end"]) - max(start, span["start"])) for span in non_content) / (end - start)
        if overlap > 0.1:
            continue
        if overlap > 0:
            flags.append({"code": "I-9", "severity": "review", "reason": "Partial source-hygiene overlap"})
        crowd = replay_feature(source.get("meta", {}).get("heatmap"), start, end)
        score, components, penalties = score_candidate(text, end - start, config, archetype, flags, crowd)
        if confidence<.6:
            penalties.append({"name":"low_asr_confidence","value":8})
            score=max(0,score-8)
        spoken=sum(max(0,min(end,word["end"])-max(start,word["start"])) for word in interval_words)
        if spoken/(end-start)<.85:
            penalties.append({"name":"dead_air","value":6})
            score=max(0,score-6)
        if boundary.get("flags"):
            boundary_penalty = 10
            penalties.append({"name": "boundary_uncertain", "value": boundary_penalty})
            score = max(0.0, score - boundary_penalty)
        candidate_id = "c_" + content_hash({"start": start, "end": end, "source": source.get("source_id")})[:12]
        headlines = generate_headlines(text, config) if english else [text[:78]]
        fairness=fairness_meter(selected,source_sentences=sentences,clip_end=end)
        if fairness["warning"]:
            flags.append({"code":"I-2","severity":"review","reason":"Nearby opposing response was cut" if fairness["cut_responses"] else "Unbalanced speaking-time share; review opposing response","evidence":fairness["cut_responses"]})
            if not any(penalty["name"]=="integrity_review" for penalty in penalties):
                penalties.append({"name":"integrity_review","value":6})
                score=max(0,score-6)
        candidate = {"schema_version": 5, "id": candidate_id, "source_id": source.get("source_id"), "start": start, "end": end, "duration": round(end - start, 3), "archetype": archetype, "score": score, "components": components, "penalties": penalties, "structure": [{"type": "setup", "s": selected[0]["i"]}, {"type": "payoff", "s": selected[-1]["i"]}], "boundary": {**boundary, "context": context}, "integrity_flags": flags, "text": text, "hook": {"spoken": selected[0]["text"], "headline_options": headlines}, "layout_hint": "wide", "layout_confidence":0.35,"alt_boundaries": [], "edited": False, "provenance": "local", "claims": claims, "fairness": fairness,"mean_asr_probability":confidence}
        if not context["passed"]:
            chip = question_chip(transcript, start, end, config)
            if chip:
                candidate["question_chip"] = chip
                candidate["augmented"] = True
                candidate["integrity_flags"] = [flag for flag in flags if flag.get("reason") != context["reason"]]
                candidate["score"]=max(0,candidate["score"]-2)
                candidate["penalties"].append({"name":"question_chip_context","value":2})
        card = evidence_card(transcript, start, end, config)
        if card:
            candidate["evidence_card"] = card
            candidate["augmented"] = True
        candidates.append(candidate)
    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
    chosen = []
    remaining=list(candidates)
    while remaining and len(chosen)<top:
        weight=float(config.get("selection","mmr_lambda",default=.7))
        candidate=max(remaining,key=lambda row:weight*row["score"]/100-(1-weight)*max((_similarity(row["text"],previous["text"]) for previous in chosen),default=0))
        remaining.remove(candidate)
        duplicate = next((old for old in chosen if _iou(candidate, old) > 0.3 or _similarity(candidate["text"], old["text"]) > 0.8), None)
        if duplicate:
            duplicate["alt_boundaries"].append({"start": candidate["start"], "end": candidate["end"], "score": candidate["score"]})
        else:
            chosen.append(candidate)
    return graph, chosen


def generate_headlines(text: str, config: AppConfig) -> list[str]:
    from .layout import fit_headline

    sentences = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text) if piece.strip()]
    question = next((sentence for sentence in sentences if sentence.endswith("?") and len(sentence) <= 78), None)
    options = []
    if question and headline_fidelity(question, text) and fit_headline(question, config)["fit"]:
        options.append(question)
    for sentence in sentences:
        short = sentence if len(sentence) <= 78 else " ".join(sentence.split()[:10]).rstrip(".,!") + "?"
        if short and headline_fidelity(short, text) and fit_headline(short, config)["fit"] and short not in options:
            options.append(short)
        if len(options) >= 3:
            break
    if re.search(r"\b(voting|ballot|election|polling place|vote count|results)\b", text.lower()):
        questions = [option for option in options if option.endswith("?")]
        if questions:
            return questions
        tokens = _tokens(text)
        for count in range(min(len(tokens), 8), 0, -1):
            option = f"The question: {' '.join(tokens[:count])}?"
            if headline_fidelity(option, text) and fit_headline(option, config)["fit"]:
                return [option]
    if options:
        return options
    first = next(iter(_tokens(text)), "exchange")
    return [f"The {first} question"]


def fairness_meter(sentences: list[dict[str, Any]], source_sentences: list[dict[str, Any]] | None = None, clip_end: float | None = None) -> dict[str, Any]:
    times: dict[str, float] = {}
    for sentence in sentences:
        speaker = str(sentence.get("speaker", "unknown"))
        times[speaker] = times.get(speaker, 0) + max(0, sentence["end"] - sentence["start"])
    total = sum(times.values())
    shares = {speaker: value / total if total else 0 for speaker, value in times.items()}
    cut_responses=[]
    last_speaker=str(sentences[-1].get("speaker")) if sentences and sentences[-1].get("speaker") else "unknown"
    end=float(clip_end if clip_end is not None else max((row["end"] for row in sentences),default=0))
    if last_speaker!="unknown":
        for row in source_sentences or []:
            speaker=row.get("speaker")
            if not speaker or str(speaker)=="unknown" or str(speaker)==last_speaker:continue
            if end<=float(row["start"])<=end+15 and len(_tokens(row.get("text","")))>=4:
                cut_responses.append({"sentence_i":row.get("i"),"speaker":speaker,"start":row["start"],"end":row["end"],"text":row.get("text",""),"reason":"Identifiable other speaker speaks within15s outside this clip; review context, not a factual verdict"})
    return {"shares": shares, "cut_responses":cut_responses,"warning": bool(cut_responses) or (len(shares) > 1 and min(shares.values()) < 0.15), "note": "Speaking-time share and excluded response evidence, not a judgement of correctness"}


def prompt_search(candidates: list[dict[str, Any]], query: str, top: int = 5) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    intent_map = {"dodges": "A6", "dodging":"A6","avoids":"A6","sidesteps":"A6","doesn't answer":"A6","deflects": "A6", "concedes": "A4", "admits": "A4", "gives in":"A4","contradiction": "A2", "receipts":"A2","changed his mind":"A2","gotcha": "A2", "heated": "A1", "argument":"A1","question": "A3"}
    desired = {archetype for word, archetype in intent_map.items() if word in query.lower()}
    ranked = []
    documents=[_tokens(row.get("text","")) for row in candidates]
    avg_len=sum(map(len,documents))/max(1,len(documents))
    frequency={token:sum(token in doc for doc in documents) for token in query_tokens}
    for candidate in candidates:
        tokens = _tokens(candidate.get("text", ""))
        matches=0.0
        for token in query_tokens:
            count=tokens.count(token)
            idf=math.log(1+(len(documents)-frequency[token]+.5)/(frequency[token]+.5))
            matches+=idf*count*2.2/(count+1.2*(.25+.75*len(tokens)/max(1,avg_len)))
        bonus = 8 if candidate.get("archetype") in desired else 0
        text = str(candidate.get("text", "")).lower()
        if "A6" in desired and "?" in text:
            # Paraphrased evasion requests need a semantic-ish cue even when
            # the speaker never says the literal lexicon phrase.
            answer = text.split("?", 1)[1]
            if any(marker in answer for marker in ("that's", "that is", "different", "the real", "again", "let's see", "what it is")):
                bonus += 10
            else:
                bonus += 3
        if "A2" in desired and any(marker in text for marker in ("earlier", "you said", "contradict")):
            bonus += 10
        ranked.append((matches + bonus + float(candidate.get("score", 0)) / 100, candidate))
    return [candidate for _, candidate in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:top]]
