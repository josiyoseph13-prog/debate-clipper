"""T-14 plant six faults in actual encoded synthetic clips and run real QA."""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.core.config import load_config
from dc.core.hashing import file_hash,content_hash
from dc.core.io import atomic_copy,atomic_write_json,read_json
from dc.core.process import run_process
from dc.core.tools import require_tool,filter_script_args
from dc.ingest import ingest
from dc.renderer import make_render_plan,render
from dc.qa import validate_output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reuse-encoded",action="store_true",help="Revalidate existing real fault encodes after verifying their recorded hashes")
    args=parser.parse_args()
    code_paths=("dc/qa.py","dc/renderer.py","tools/measure_qa_negatives.py")
    code_start={name:file_hash(ROOT/name) for name in code_paths}
    cfg=load_config(overrides={"output":{"preset":"ultrafast"}})
    work=ROOT/"work"/"job_qa_negative_acceptance"
    base=work/"baseline"
    base.mkdir(parents=True,exist_ok=True)
    ffmpeg=require_tool("ffmpeg")
    source_path=base/"source.mp4"
    destination=ROOT/"reports"/"current_checks"/"qa_negatives.json"
    prior=read_json(destination,{})
    if args.reuse_encoded:
        if prior.get("config_hash")!=cfg.hash() or file_hash(source_path)!=prior.get("source_sha256") or file_hash(base/"clip.mp4")!=prior.get("baseline_qa",{}).get("output_sha256"):
            raise ValueError("Recorded baseline/source/config hashes do not match")
        for row in prior.get("checks",[]):
            if file_hash(work/row["fault"]/"clip.mp4")!=row["output_sha256"]:raise ValueError("Fault encode has changed: "+row["fault"])
        if len(prior.get("checks",[]))!=6:raise ValueError("All six real fault encodes are required")
    else:
        run_process([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=640x360:r=25:d=8","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=8","-c:v","libx264","-c:a","aac","-shortest",source_path],timeout=60)
    if destination.is_file():atomic_copy(destination,destination.with_name("qa_negatives."+file_hash(destination)[:16]+".json"))
    source=ingest(source_path,base,rights_class="own",rights_note="Generated test pattern and sine; no real people or ASR accuracy claim")
    transcript={"schema_version":5,"words":[{"text":"RIGHT","start":round(.2+index*.3,3),"end":round(.45+index*.3,3)} for index in range(24)]}
    if args.reuse_encoded:
        plan=read_json(base/"render_plan.json")
        if content_hash({key:value for key,value in plan.items() if key!="plan_hash"})!=prior["baseline_qa"]["plan_hash"]:
            raise ValueError("Saved baseline RenderPlan no longer matches the actual encoded fixture")
    else:
        plan=make_render_plan(source,{"id":"c_qa_baseline","start":0,"end":8,"hook":{"headline_options":["RIGHT"]}},cfg,base)
        plan.update({"transcript":transcript,"captions_ass":str(base/"captions.ass"),"caption_plan":str(base/"captions_plan.json"),"chrome_png":str(base/"chrome.png")})
        plan["plan_hash"]=content_hash({key:value for key,value in plan.items() if key!="plan_hash"})
        atomic_write_json(base/"render_plan.json",plan)
    if not args.reuse_encoded:render(plan,cfg,base,base/"clip.mp4")
    if (base/"export_report.json").is_file():atomic_copy(base/"export_report.json",base/("export_report."+file_hash(base/"export_report.json")[:16]+".json"))
    baseline=validate_output(base/"clip.mp4",plan,cfg,base/"export_report.json")
    if baseline["status"]!="passed":raise RuntimeError("QA negative fixture has no passing positive control: "+str([row["name"] for row in baseline["checks"] if not row["passed"]]))
    rows=[]
    expected={"shifted_feed":"bottom_white_guard","caption_in_header":"chrome_integrity_12_frames","missing_glow":"glow_reach","wrong_colour_order":"caption_active_colour","missing_audio":"audio_stream","caption_overflow":"caption_lossless_ab"}
    for name,check in expected.items():
        folder=work/name
        folder.mkdir(exist_ok=True)
        if not args.reuse_encoded:
            for path in base.iterdir():
                if path.is_file() and (path.suffix==".ass" or path.name in {"source.mp4","chrome.png","craft.png","extras.png","evidence.png","captions_plan.json","render.graph","renderer_config.json"}):atomic_copy(path,folder/path.name)
        bad_plan=copy.deepcopy(plan)
        bad_plan.update({"captions_ass":str(folder/"captions.ass"),"caption_plan":str(folder/"captions_plan.json"),"chrome_png":str(folder/"chrome.png")})
        output=folder/"clip.mp4"
        if args.reuse_encoded:
            pass  # Actual encoded bytes were checked against the prior report above.
        elif name in {"missing_glow","wrong_colour_order","caption_overflow"}:
            ass=(folder/"captions.ass").read_text(encoding="utf-8")
            if name=="missing_glow":ass="\n".join(line for line in ass.splitlines() if not line.startswith(("Dialogue: 0,","Dialogue: 1,")))+"\n"
            elif name=="wrong_colour_order":ass=ass.replace("3DF8B4","B4F83D")
            else:
                import re
                ass=re.sub(r"\\pos\([^,]+,",rf"\\pos({cfg.canvas['w']-50},",ass)
            (folder/"captions.ass").write_text(ass,encoding="utf-8")
            run_process([ffmpeg,"-hide_banner","-loglevel","error","-y","-i","source.mp4","-loop","1","-i","chrome.png","-loop","1","-i","craft.png","-loop","1","-i","extras.png","-loop","1","-i","evidence.png",*filter_script_args("render.graph"),"-map","[outv]","-map","[outa]","-c:v","libx264","-preset","ultrafast","-crf","18","-c:a","aac","-b:a","160k","-pix_fmt","yuv420p","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv","-shortest",output.name],cwd=folder,timeout=180)
        elif name=="missing_audio":
            run_process([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",base/"clip.mp4","-map","0:v:0","-c:v","copy",output],timeout=60)
        else:
            feed=cfg.regions["feed"]
            if name=="shifted_feed":
                graph=f"[0:v]split[a][b];[a]crop={feed['w']}:{feed['h']}:{feed['x']}:{feed['y']}[feed];[b]drawbox=x={feed['x']}:y={feed['y']}:w={feed['w']}:h={feed['h']}:color=white:t=fill[clear];[clear][feed]overlay={feed['x']}:{feed['y']+24}[outv]"
            else:
                font=os.path.relpath(ROOT/cfg.get("captions","font_file"),folder).replace("\\","/")
                graph=f"[0:v]drawtext=fontfile='{font}':text=RIGHT:fontsize=160:x=240:y=180:fontcolor={cfg.get('captions','active')}:borderw=5:bordercolor=black[outv]"
            (folder/"fault.graph").write_text(graph,encoding="utf-8")
            run_process([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",base/"clip.mp4",*filter_script_args("fault.graph"),"-map","[outv]","-map","0:a?","-c:v","libx264","-preset","ultrafast","-crf","18","-c:a","copy","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",output],cwd=folder,timeout=180)
        if (folder/"export_report.json").is_file():atomic_copy(folder/"export_report.json",folder/("export_report."+file_hash(folder/"export_report.json")[:16]+".json"))
        bad_plan["plan_hash"]=content_hash({key:value for key,value in bad_plan.items() if key!="plan_hash"})
        atomic_write_json(folder/"render_plan.json",bad_plan)
        report=validate_output(output,bad_plan,cfg,folder/"export_report.json")
        flagged=[row["name"] for row in report["checks"] if not row["passed"]]
        rows.append({"fault":name,"expected_check":check,"flagged_checks":flagged,"status":report["status"],"detected":check in flagged and report["status"]!="passed","output_sha256":file_hash(output),"qa":str((folder/"export_report.json").relative_to(ROOT))})
        print(json.dumps(rows[-1]),flush=True)
    code_end={name:file_hash(ROOT/name) for name in code_paths}
    result={"schema_version":5,"test_id":"T-14 six planted QA faults","command":[sys.executable,*sys.argv],"level":"V2 actual generated/encoded synthetic video and real FFmpeg/QA, no mocked renderer","source_sha256":source["fingerprint"]["sha256"],"config_hash":cfg.hash(),"baseline_qa":baseline,"checks":rows,"reuse_encoded":args.reuse_encoded,"code_hashes_at_start":code_start,"code_hashes":code_end,"code_changed_during_checks":code_start!=code_end,"passed":code_start==code_end and all(row["detected"] for row in rows),"remaining_scope":"Colour and boundary-bleed are separate recorded checks; real labelled face-edge acceptance remains open"}
    atomic_write_json(destination,result)
    print({"passed":result["passed"]},flush=True)
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
