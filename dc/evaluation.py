"""Transparent metrics and confidence intervals; never create human labels."""
from __future__ import annotations
import math
import random
from collections import Counter
from .core.io import atomic_write_json


def wilson(successes:int,total:int,z:float=1.959963984540054)->list[float]|None:
    if not total: return None
    proportion=successes/total
    denominator=1+z*z/total
    center=(proportion+z*z/(2*total))/denominator
    radius=z*math.sqrt(proportion*(1-proportion)/total+z*z/(4*total*total))/denominator
    return [max(0,center-radius),min(1,center+radius)]


def bootstrap_difference(baseline:list[float],alternative:list[float],samples:int=2000)->dict:
    if len(baseline)!=len(alternative) or not baseline:
        raise ValueError("Paired, nonempty measurements required")
    differences=[b-a for a,b in zip(baseline,alternative)]
    rng=random.Random(7)
    values=sorted(sum(differences[rng.randrange(len(differences))] for _ in differences)/len(differences) for _ in range(samples))
    return {"gain":sum(differences)/len(differences),"ci95":[values[int(samples*.025)],values[int(samples*.975)]],"pairs":len(differences),"samples":samples}


def kappa(rater_a:list,rater_b:list)->float|None:
    if len(rater_a)!=len(rater_b) or not rater_a: return None
    size=len(rater_a)
    observed=sum(a==b for a,b in zip(rater_a,rater_b))/size
    counts_a,counts_b=Counter(rater_a),Counter(rater_b)
    expected=sum(counts_a[key]*counts_b[key] for key in counts_a)/size**2
    return (observed-expected)/(1-expected) if expected<1 else 1.0


def candidate_metrics(candidates:list[dict],labels:list[dict])->dict:
    from .selection import _iou
    rated={row["candidate_id"]:row for row in labels if row.get("candidate_id") and row.get("rating")}
    high=[row for row in candidates if row.get("score",0)>=90 and row["id"] in rated]
    usable=sum(rated[row["id"]]["rating"] in {"as_is","trivial_trim"} for row in high)
    marks=[row for row in labels if row.get("rating")=="would_post"]
    top=sorted(candidates,key=lambda row:row["score"],reverse=True)[:10]
    recalled=sum(any(_iou(mark,candidate)>=.5 for candidate in top) for mark in marks)
    return {"schema_version":5,"precision_at_90":usable/len(high) if high else None,"precision_ci95":wilson(usable,len(high)),"high_score_rated_n":len(high),"precision_gate":"measured" if len(high)>=40 else "insufficient","recall_at_10":recalled/len(marks) if marks else None,"blind_marks_n":len(marks),"rated_candidates":len(rated),"required_raters":2,"gate_claimed":False}


def compare_bakeoff(rows:list[dict])->dict:
    # Dataset rows are already blind-rated and paired by source; no vendor
    # outputs, ratings, or scores are simulated by this harness.
    criteria=("clean_boundaries","context","framing","captions","brand","would_post","fix_minutes")
    sources=sorted({row["source_id"] for row in rows})
    raters={row["rater"] for row in rows}
    report={"schema_version":5,"sources":len(sources),"raters":len(raters),"status":"measured" if len(sources)>=10 and len(raters)>=3 else "insufficient","comparisons":{}}
    for vendor in ("opus","klap"):
        for criterion in criteria:
            paired=[]
            for source in sources:
                own=[float(row[criterion]) for row in rows if row["source_id"]==source and row["system"]=="political_lens" and criterion in row]
                other=[float(row[criterion]) for row in rows if row["source_id"]==source and row["system"]==vendor and criterion in row]
                if own and other:
                    paired.append((sum(other)/len(other),sum(own)/len(own)))
            if paired:
                report["comparisons"][vendor+":"+criterion]=bootstrap_difference([a for a,_ in paired],[b for _,b in paired])
    return report


def diarization_error(reference:list[dict],hypothesis:list[dict],duration:float,collar:float=.25)->dict:
    import itertools
    identities=sorted({row["speaker"] for row in reference})
    clusters=sorted({row["speaker"] for row in hypothesis})
    if len(clusters)>8: raise ValueError("Evaluation requires explicit mapping for more than eight clusters")
    mappings=list(itertools.permutations(identities+[f"unmatched_{i}" for i in range(max(0,len(clusters)-len(identities)))],len(clusters)))
    step=.01
    best=None
    for perm in mappings or [()]:
        mapping=dict(zip(clusters,perm))
        errors,spoken=0,0
        for index in range(math.ceil(duration/step)):
            t=index*step
            if any(abs(t-row[edge])<collar for row in reference for edge in ("start","end")): continue
            true={row["speaker"] for row in reference if row["start"]<=t<row["end"]}
            pred={mapping[row["speaker"]] for row in hypothesis if row["start"]<=t<row["end"]}
            spoken+=len(true)
            errors+=max(len(true),len(pred))-len(true&pred)
        score=errors/max(1,spoken)
        if best is None or score<best["der"]: best={"der":score,"mapping":mapping,"reference_speaker_seconds":spoken*step,"collar_s":collar,"time_resolution_s":step}
    return best
