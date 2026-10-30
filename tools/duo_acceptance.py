"""Real-source Duo exports for the optional layout; unknown voices stay Duo."""
from __future__ import annotations
import copy
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from argparse import Namespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.io import read_json,atomic_copy,atomic_write_json
from dc.core.decisions import record_decision
from dc.core.hashing import file_hash
from dc.cli import command_render
from tools.capture_fix3_frames import capture


def make_job(name,source_job,source_path,candidate_id,start,end):
    job=ROOT/"work"/name;job.mkdir(parents=True,exist_ok=True)
    source=read_json(ROOT/"work"/source_job/"source.json")
    source["path"]=str(ROOT/source_path)
    source["duration"]=max(float(source.get("duration",end)),end)
    atomic_write_json(job/"source.json",source)
    for artifact in ("transcript.json","turns.json","shots.json"):
        atomic_copy(ROOT/"work"/source_job/artifact,job/artifact)
    original=read_json(ROOT/"work"/source_job/"candidates.json")
    base=next(row for row in original["candidates"] if row["start"]<=start and row["end"]>=end)
    candidate=copy.deepcopy(base);candidate.update({"id":candidate_id,"start":start,"end":end,"duration":end-start})
    atomic_write_json(job/"candidates.json",{"schema_version":5,"candidates":[candidate]})
    atomic_write_json(job/"job_config.json",{"preset":"political_lens","config":load_config().json()})
    return job,source,candidate


def render(job,source,candidate,stage,spec):
    record_decision(ROOT,{"schema_version":5,"time":datetime.now(timezone.utc).isoformat(),"job_id":job.name,"candidate_id":candidate["id"],"action":"save","speaker_frame":spec})
    code=command_render(Namespace(job=job.name,candidate=candidate["id"],headline=None,layout="auto",variants=1,preset="political_lens",crop=None,debug_overlay=False,accept_review=True))
    report=read_json(job/"export_report.json");plan=read_json(job/"render_plan.json")
    stage.mkdir(parents=True,exist_ok=True)
    output=stage/"duo.mp4";atomic_copy(job/f"{candidate['id']}.mp4",output)
    before=capture(Path(source["path"]),stage/"before","source",start=candidate["start"],clip_duration=candidate["duration"])
    after=capture(output,stage/"after","duo")
    return {"returncode":code,"status":report["status"],"output":str(output.relative_to(ROOT)),"sha256":file_hash(output),"export":report.get("export"),"speaker_frame":next((r for r in report["checks"] if r["name"]=="speaker_frame"),None),"plan":str((job/"render_plan.json").relative_to(ROOT)),"frames_before":len(before),"frames_after":len(after),"voice_evidence":"Unknown turns in the real job; Smart stayed Duo. Speaker identity and diarization accuracy: Not measured."}


def main():
    boxes=[{"id":"A","name":"Speaker A","x":80,"y":60,"w":850,"h":960},{"id":"B","name":"Speaker B","x":990,"y":60,"w":850,"h":960}]
    common={"enabled":True,"layout":"duo","selected":"A","boxes":boxes,"blend":{"width":.14,"position":.5,"direction":"horizontal","swap":False},"voice_map":{},"overrides":[],"shots":[],"both_blended":False}
    entries=[]
    if "--other" not in sys.argv:
        job,source,candidate=make_job("job_duo_acceptance","job_863e97df620d","input/yFFPgN_u6aY.mp4","c_duo_real",452.42,478.31)
        for name,duo in (("real_smart_unknown",{"style":"smart","full_after":3,"duo_after":.6}),("real_always_duo",{"style":"always_duo","full_after":3,"duo_after":.6}),("real_always_full_fallback",{"style":"always_full","full_after":3,"duo_after":.6})):
            spec={**copy.deepcopy(common),"duo":duo}
            entries.append({"name":name,"source":"input/yFFPgN_u6aY.mp4","range":[candidate["start"],candidate["end"]],**render(job,source,candidate,ROOT/"reports/duo_style/exports"/name,spec)})
    if "--first" not in sys.argv:
        other_job,other_source,other_candidate=make_job("job_duo_different_clip","job_final_xmp4","input/xmp4EdJvPfo.mp4","c_duo_other",1.22,34.67)
        entries.append({"name":"different_clip_smart_unknown","source":"input/xmp4EdJvPfo.mp4","range":[other_candidate["start"],other_candidate["end"]],**render(other_job,other_source,other_candidate,ROOT/"reports/duo_style/exports/different_clip",{**copy.deepcopy(common),"duo":{"style":"smart","full_after":3,"duo_after":.6}})})
    atomic_write_json(ROOT/"reports/duo_style/acceptance.json",{"schema_version":5,"distinct_reference_edits":8,"results":entries,"real_voice_turns":"unknown; no fabricated mapping","note":"Real raw-source exports. The supplied references are already edited output, so an exact raw-source recreation comparison is Not measured."})
    print(json.dumps({"results":[{k:r[k] for k in ("name","status","output","speaker_frame")} for r in entries]},indent=2))
    return 0 if all(r["returncode"]==0 for r in entries) else 1

if __name__=="__main__":raise SystemExit(main())
