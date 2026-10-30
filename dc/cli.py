from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from contextvars import ContextVar
from pathlib import Path

from . import __version__
from .core.config import ROOT, load_config, load_preset
from .core.decisions import latest_decision
from .core.hashing import content_hash
from .core.checkpoints import StageCheckpoints
from .core.io import atomic_write_json, read_json
from .core.logging import log_event
from .core.process import ProcessCancelled, check_cancelled, job_processes, run_process
from .core.jobs import JobStore
from .core.locking import ResourceBusy
from .core.security import validate_id
from .doctor import print_doctor, run_doctor
from .exports import export_bundle
from .export_catalog import export_names, refresh_export_catalog
from .ingest import ingest
from .integrity import verify_claims
from .ops import bench, diag, disk_guard
from .pipeline import write_analysis_artifacts
from .qa import validate_output
from .renderer import make_render_plan, render
from .selection import can_auto_approve, prompt_search, select_candidates

_active_execution = ContextVar("active_execution", default=False)


def _dirs() -> None:
    for name in ("work", "exports", "reports", "inbox", "input"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)


def _job_id(source: Path) -> str:
    with source.open("rb") as handle:
        first=handle.read(1024*1024)
    return f"job_{content_hash(first + str(source.stat().st_size).encode())[:12]}"


def _selection_key(source,transcript,config,top,rejected,gate):
    # Caption palette/style and output settings do not affect discovery. Review
    # boundary/headline edits go directly to framing/render for that clip.
    from .core.hashing import file_hash
    settings={name:config.get(name) for name in ("selection","semantic","signals","hook")}
    settings["craft"]={name:config.get("craft",name) for name in ("question_chip","evidence_cards","claim_gate")}
    settings["hook_band"]=config.regions["hook"]
    settings["canvas"]=config.canvas
    files=[ROOT/"config"/"lexicons"/"debate.json",ROOT/config.get("hook","font"),ROOT/config.get("hook","emoji_font")]
    return content_hash({"source":source["fingerprint"]["sha256"],"transcript":transcript,"settings":settings,"assets":{str(path.relative_to(ROOT)):file_hash(path) for path in files if path.is_file()},"meta":source.get("meta"),"rights":source.get("rights_class","unknown"),"top":top,"rejected":rejected,"semantic_gate":gate,"selection_version":5})


def _asr_request_key(source: dict, config) -> str:
    from .asr import asr_cache_key, _whisper_params
    glossary_path=ROOT/config.get("asr","glossary_file",default="config/glossary.json")
    glossary=read_json(glossary_path,{}) or {}
    model=str(config.get("asr","model",default="small.en") or "small.en")
    model_hash=None
    registry=read_json(ROOT/"assets"/"models"/"registry.json",{}) or {}
    registered=registry.get("models",{}).get(model)
    if registered:
        model_hash=(registered.get("files",{}).get("model",{}) or {}).get("sha256")
    params={**_whisper_params(config,local_files_only=True),"vad_filter":bool(config.get("asr","vad_filter",default=True)),"condition_on_previous_text":bool(config.get("asr","condition_on_previous_text",default=False)),"model_hash":model_hash}
    return asr_cache_key(source["fingerprint"]["sha256"],model,params,glossary)


def _load_job(job_id: str) -> tuple[Path, dict, dict, dict]:
    validate_id(job_id)
    job_dir = ROOT / "work" / job_id
    if job_dir.is_symlink() or job_dir.resolve().parent != (ROOT/"work").resolve():
        raise ValueError("Job path escapes work root")
    source = read_json(job_dir / "source.json")
    transcript = read_json(job_dir / "transcript.json")
    if not isinstance(transcript, dict) or not transcript.get("segments"):
        raise SystemExit(f"Transcript artifact is missing or has no segments: {job_dir / 'transcript.json'}")
    candidate_artifact = read_json(job_dir / "candidates.json", {}) or {}
    if not source or not transcript:
        raise SystemExit(f"Job {job_id} is missing source.json or transcript.json")
    return job_dir, source, transcript, candidate_artifact


def command_run(args: argparse.Namespace) -> int:
    source_url = str(args.source).lower().startswith(("http://", "https://"))
    if not getattr(args, "job", None):
        args.job = f"job_{content_hash(args.source)[:12]}" if source_url else _job_id(Path(args.source).expanduser())
    return _execute_job(args.job, lambda: _command_run(args))


def _execute_job(job_id: str, operation) -> int:
    validate_id(job_id)
    folder = ROOT / "work" / job_id
    if folder.is_symlink() or folder.resolve().parent != (ROOT / "work").resolve():
        raise ValueError("Job path escapes work root")
    folder.mkdir(parents=True, exist_ok=True)
    store = JobStore(ROOT / "work" / "jobs.sqlite")
    if not store.get(job_id):
        store.upsert(job_id,"queued","{}","queued")
    if not _active_execution.get():
        from .core.locking import exclusive_file
        with exclusive_file(ROOT / "work" / "execution.lock"):
            token = _active_execution.set(True)
            try:
                return _execute_job(job_id, operation)
            finally:
                _active_execution.reset(token)
    try:
        from .core.recovery import recover_children
        recovered=recover_children(folder)
        if recovered:
            log_event(ROOT/"work"/"events.jsonl",job_id,"recovery","stale_children_terminated",pids=recovered)
        with job_processes(folder, store, job_id):
            from .core.bundles import recover_export_bundles
            bundles=recover_export_bundles(folder,ROOT/"exports")
            if bundles:log_event(ROOT/"work"/"events.jsonl",job_id,"recovery","export_bundle_recovery",bundles=bundles)
            return operation()
    except (ProcessCancelled, KeyboardInterrupt):
        store.upsert(job_id, "cancelled", "{}", "cancel")
        return 130
    except (Exception, SystemExit) as exc:
        from .core.logging import redact
        store.upsert(job_id, "failed", json.dumps({"error": redact(str(exc))}), "failed")
        raise


def _command_run(args: argparse.Namespace) -> int:
    _dirs()
    config = load_preset(args.preset)
    source_url = args.source if str(args.source).lower().startswith(("http://", "https://")) else None
    if source_url:
        if args.no_network:
            raise SystemExit("--no-network refuses URL downloads")
        from .download import download_source
        source, downloaded_meta = download_source(source_url, ROOT / "input", no_network=args.no_network, comments=getattr(args,"comments",0))
    else:
        source = Path(args.source).expanduser()
        downloaded_meta = {}
        if not source.exists():
            raise SystemExit(f"Source does not exist: {source}")
    job_id = args.job or _job_id(source)
    validate_id(job_id)
    job_dir = ROOT / "work" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(job_dir/"job_request.json",{"schema_version":5,"request":vars(args)})
    store = JobStore(ROOT / "work" / "jobs.sqlite")
    disk_guard(source, ROOT, float(config.get("ops", "min_free_disk_x_source", default=3)))
    log_event(ROOT / "work" / "events.jsonl", job_id, "ingest", "job_started", source=str(source), mode=args.mode)
    existing_source = read_json(job_dir / "source.json", {}) or {}
    store.upsert(job_id, "running", json.dumps({"source": str(source)}), "ingest")
    source_artifact = ingest(source, job_dir, url=source_url or downloaded_meta.get("webpage_url"), rights_class=args.rights_class, rights_note=args.rights_note)
    if not args.transcript and existing_source and existing_source.get("fingerprint", {}).get("sha256") != source_artifact["fingerprint"]["sha256"]:
        old_transcript = job_dir / "transcript.json"
        if old_transcript.exists():
            old_transcript.replace(job_dir / f"transcript_previous_{time.time_ns()}.json")
    atomic_write_json(job_dir / "job_config.json", {"schema_version": 5, "preset": args.preset, "config": config.json(), "config_hash": config.hash(), "asr_request_key": _asr_request_key(source_artifact, config)})
    transcript_path = Path(args.transcript) if args.transcript else job_dir / "transcript.json"
    prior_transcript = read_json(job_dir / "transcript.json", {}) or {}
    same_source = existing_source.get("fingerprint", {}).get("sha256") == source_artifact.get("fingerprint", {}).get("sha256")
    prior_cache_ok = not prior_transcript.get("cache_key") or prior_transcript.get("cache_key") == _asr_request_key(source_artifact, config)
    if args.transcript:
        transcript_path = transcript_path.resolve()
        if transcript_path != (job_dir / "transcript.json").resolve():
            shutil.copy2(transcript_path, job_dir / "transcript.json")
    elif not (not args.force and same_source and transcript_path.exists() and prior_cache_ok):
        bundled_transcript = ROOT / "transcripts" / f"{source.stem}.json"
        if bundled_transcript.exists():
            shutil.copy2(bundled_transcript, transcript_path)
            log_event(ROOT / "work" / "events.jsonl", job_id, "transcribe", "reused_existing_transcript", source_path=str(bundled_transcript))
        else:
            from .asr import transcribe_file

            store.upsert(job_id, "running", json.dumps(source_artifact), "transcribe")
            arguments=[sys.executable,"-m","dc.asr","--source",str(source.resolve()),"--output",str(transcript_path.resolve()),"--config",str((job_dir/"job_config.json").resolve()),"--metadata",str((job_dir/"source.json").resolve())]
            if args.no_network: arguments.append("--no-network")
            with job_processes(job_dir,store,job_id):
                run_process(arguments,cwd=ROOT,timeout=max(600,float(source_artifact["duration"])*20))
    transcript = read_json(job_dir / "transcript.json")
    if not isinstance(transcript, dict) or not transcript.get("segments"):
        raise SystemExit("Transcript must contain non-empty segments")
    atomic_write_json(job_dir / "job_config.json", {"schema_version": 5, "preset": args.preset, "config": config.json(), "config_hash": config.hash()})
    existing_candidates = read_json(job_dir / "candidates.json", {}) or {}
    gate=read_json(ROOT/"reports"/"semantic_gate.json",{}) or {}
    with store.connect() as db:
        rejected=[json.loads(row["payload"]).get("text","") for row in db.execute("SELECT payload FROM labels WHERE action='reject' ORDER BY id")]
    cache_key=_selection_key(source_artifact,transcript,config,args.top,rejected,gate)
    checkpoints=StageCheckpoints(job_dir)
    reuse_candidates=not args.force and checkpoints.valid("selection",cache_key,["debate_graph.json","candidates.json"]) and bool(existing_candidates.get("candidates"))
    if reuse_candidates:
        graph = read_json(job_dir / "debate_graph.json", {}) or {}
        candidates = existing_candidates.get("candidates", [])[:args.top]
        write_analysis_artifacts(job_dir,source_artifact,transcript,graph,config)
        log_event(ROOT / "work" / "events.jsonl", job_id, "select", "cache_hit", artifact="candidates.json")
    else:
        store.upsert(job_id, "running", json.dumps(source_artifact), "select")
        graph, candidates = select_candidates(transcript, source_artifact, config, top=args.top)
        atomic_write_json(job_dir / "debate_graph.json", graph)
        with job_processes(job_dir, store, job_id):
            analysis_artifacts=write_analysis_artifacts(job_dir, source_artifact, transcript, graph, config)
        if config.get("diarization","model") and analysis_artifacts["turns"].get("engine") in {"sherpa_onnx","pyannote"}:
            from .diarization import attach_speakers
            transcript=attach_speakers(transcript,analysis_artifacts["turns"]["turns"])
            atomic_write_json(job_dir/"transcript.json",transcript)
            graph,candidates=select_candidates(transcript,source_artifact,config,top=args.top)
            atomic_write_json(job_dir/"debate_graph.json",graph)
        from .semantic import rerank_local,llm_rerank
        candidates=rerank_local(candidates,config,gate)
        from .selection import _similarity
        for candidate in candidates:
            similarity=max((_similarity(candidate["text"],text) for text in rejected if text),default=0)
            if similarity>.8:
                candidate["penalties"].append({"name":"negative_memory","value":10,"similarity":similarity})
                candidate["score"]=max(0,candidate["score"]-10)
        candidates.sort(key=lambda row:row["score"],reverse=True)
        if config.get("semantic","llm","enabled",default=False):
            from .captions import transcript_words
            try:
                proposals=llm_rerank(transcript_words(transcript),candidates,config,job_dir/"candidates_llm.json",args.no_network)
                for candidate in candidates:
                    candidate["llm_proposals"]=[proposal for proposal in proposals if proposal.get("candidate_id")==candidate["id"]]
            except (ValueError,RuntimeError) as exc:
                log_event(ROOT/"work"/"events.jsonl",job_id,"semantic","llm_discarded",reason=str(exc))
        cache_key=_selection_key(source_artifact,transcript,config,args.top,rejected,gate)
        graph["cache_key"]=cache_key
        atomic_write_json(job_dir/"debate_graph.json",graph)
        atomic_write_json(job_dir / "candidates.json", {"schema_version": 5, "source_id": source_artifact["source_id"], "config_hash": config.hash(), "cache_key": cache_key, "candidates": candidates})
        checkpoints.commit("selection",cache_key,["debate_graph.json","candidates.json"])
    state = "awaiting_review"
    check_cancelled()
    store.upsert(job_id, state, json.dumps({"candidate_count": len(candidates)}), "review")
    log_event(ROOT / "work" / "events.jsonl", job_id, "review", "candidates_ready", count=len(candidates))
    print(json.dumps({"job_id": job_id, "state": state, "candidate_count": len(candidates), "work_dir": str(job_dir)}, indent=2))
    if args.mode == "auto":
        eligible = next((candidate for candidate in candidates if can_auto_approve(candidate, args.auto_threshold)), None)
        if eligible:
            print(f"Auto rendering eligible candidate {eligible['id']}.")
            command_render(argparse.Namespace(job=job_id, candidate=eligible["id"], headline=None, layout="auto", variants=1))
        else:
            print("Auto mode is review-safe: candidates with rights, claim, or integrity flags remain awaiting review.")
    return 0


def command_render(args: argparse.Namespace) -> int:
    return _execute_job(args.job, lambda: _command_render(args))


def _command_render(args: argparse.Namespace) -> int:
    _dirs()
    job_dir, source, transcript, candidate_artifact = _load_job(args.job)
    saved_config = read_json(job_dir / "job_config.json", {}) or {}
    from .core.config import AppConfig, validate_config
    config = load_preset(saved_config.get("preset", "political_lens"))
    if getattr(args, "preset", None):
        config = load_preset(args.preset)
    elif saved_config.get("config"):
        validate_config(saved_config["config"])
        config = AppConfig(saved_config["config"], config.path)
    candidates = candidate_artifact.get("candidates", [])
    candidate = next((row for row in candidates if row.get("id") == args.candidate), None)
    if not candidate:
        raise SystemExit(f"Candidate not found: {args.candidate}")
    decision = getattr(args, "decision_snapshot", None)
    if decision is None:
        decision = latest_decision(ROOT, args.job, args.candidate)
    if decision.get("speaker_frame",{}).get("enabled"):
        config=load_preset(getattr(args,"preset",None) or saved_config.get("preset","political_lens"))
    if decision.get("action") == "reject":
        raise SystemExit("Candidate is rejected in the Review Studio")
    candidate = json.loads(json.dumps(candidate))
    edits = decision.get("edits", {}) if isinstance(decision.get("edits", {}), dict) else {}
    if "start" in edits:
        candidate["start"] = max(0.0, float(edits["start"]))
    if "end" in edits:
        candidate["end"] = min(float(source.get("duration", edits["end"])), float(edits["end"]))
    if candidate["end"] <= candidate["start"]:
        raise SystemExit("Review edit has an invalid time range")
    candidate["duration"] = candidate["end"] - candidate["start"]
    from .captions import transcript_words
    from .selection import claims_in_text, headline_fidelity, integrity_flags
    from .layout import fit_headline
    from .core.config import _deep_merge
    words = transcript_words(transcript)
    if any(word["start"] + .04 < candidate["start"] < word["end"] - .04 or word["start"] + .04 < candidate["end"] < word["end"] - .04 for word in words):
        raise SystemExit("Review boundary cuts through a word; choose a word boundary")
    selected_words = [word for word in words if word["end"] > candidate["start"] and word["start"] < candidate["end"]]
    if candidate.get("receipt"):
        spans=[candidate["receipt"]["first"],candidate["receipt"]["second"]]
        selected_words=[word for word in selected_words if any(span["start"]<=word["start"] and word["end"]<=span["end"] for span in spans)]
    candidate["text"] = " ".join(word["text"] for word in selected_words)
    candidate["claims"] = claims_in_text(selected_words)
    candidate["integrity_flags"] = [flag for flag in candidate.get("integrity_flags", []) if flag.get("code") not in {"I-1", "I-3", "I-5", "I-7", "I-8", "I-10"}] + integrity_flags(candidate["text"], source.get("rights_class", "unknown"), candidate.get("edited", False))
    candidate = verify_claims(candidate, decision.get("claim_checks", {}))
    overrides = {}
    if decision.get("palette"):
        overrides["captions"] = {"active": decision["palette"]}
    if decision.get("caption_mode"):
        overrides["craft"] = {"caption_mode": decision["caption_mode"]}
    caption_controls = decision.get("caption_controls", {}) or {}
    if caption_controls:
        overrides.setdefault("captions", {}).update({"font_size_override": 110 + float(caption_controls.get("size_delta", 0)), "dy_override": float(caption_controls.get("vertical_delta", 0))})
        overrides["captions"]["active"] = caption_controls.get("highlight_color", overrides["captions"].get("active", "#B4F83D"))
        overrides["craft"] = {"caption_mode": caption_controls.get("style", overrides.get("craft", {}).get("caption_mode", "hormozi_glow"))}
        if caption_controls.get("enabled") is False:
            overrides.setdefault("captions", {})["user_disabled"] = True
    if overrides:
        config = AppConfig(_deep_merge(config.json(), overrides), config.path)
    headline_from_decision = args.headline is None and "headline" in decision
    headline = args.headline if args.headline is not None else decision["headline"] if "headline" in decision else next(iter(candidate.get("hook", {}).get("headline_options", [])), "The full exchange")
    headline_warning = None
    if not headline_fidelity(headline, candidate["text"]):
        if headline_from_decision:
            headline_warning = "Manual headline contains words or claims absent from this clip; kept because the user typed and saved it."
        else:
            raise SystemExit("Headline contains words or claims absent from this clip")
    if not fit_headline(headline, config)["fit"]:
        raise SystemExit("Headline does not fit the configured hook band")
    crop = getattr(args, "crop", None) or decision.get("crop")
    if isinstance(crop, str):
        try:
            crop = dict(zip(("x", "y", "w", "h"), [float(value) for value in crop.split(",")], strict=True))
        except ValueError as exc:
            raise SystemExit("--crop requires x,y,w,h source coordinates") from exc
    framing_controls = decision.get("framing_controls", {}) or {}
    framing_pins = decision.get("framing_pins", []) or []
    render_config = config
    if framing_pins and (decision.get("framing_shape") or "9:16") != "9:16":
        from .framing_pins import shape_feed_config as _shape_feed_config
        render_config = _shape_feed_config(config, decision.get("framing_shape"))
    if not framing_pins and framing_controls.get("layout") == "two":
        layout = "dual"
    elif not framing_pins and framing_controls.get("layout") == "wide":
        layout = "wide"
    else:
        layout = decision.get("layout", args.layout)
    if not framing_pins and framing_controls and not crop and (abs(float(framing_controls.get("zoom", 1.0)) - 1.0) > 1e-6 or abs(float(framing_controls.get("move_x", 0.0))) > 1e-6 or abs(float(framing_controls.get("move_y", 0.0))) > 1e-6):
        from .layout import crop_rect
        zoom = float(framing_controls.get("zoom", 1.0))
        center_x = float(source.get("width", 1920)) / 2 + float(framing_controls.get("move_x", 0.0)) * float(source.get("width", 1920)) * .25
        center_y = float(source.get("height", 1080)) / 2 + float(framing_controls.get("move_y", 0.0)) * float(source.get("height", 1080)) * .25
        crop = crop_rect(int(source.get("width", 1920)), int(source.get("height", 1080)), config, center_x=center_x, center_y=center_y, zoom=zoom)
    layout = "manual" if crop else layout
    plan = make_render_plan(source, candidate, render_config, job_dir, headline=headline, mode=layout, manual_regions=[crop] if crop else None)
    if headline_warning:
        plan["headline_warning"] = headline_warning
        print(f"Warning: {headline_warning}")
    plan["framing_controls"] = framing_controls
    plan["speaker_labels"] = decision.get("speaker_labels", {})
    plan["edited"] = bool(candidate.get("edited",False))
    plan["edits"] = candidate.get("edits",[])
    if candidate.get("receipt"):
        plan["receipt"] = candidate["receipt"]
    try:
        from .vision import analyze_window, caption_exclusions
        with job_processes(job_dir,JobStore(ROOT/"work"/"jobs.sqlite"),args.job):
            analysis = analyze_window(plan["source"], candidate["start"], candidate["end"], transcript, config, job_dir / "tracking.json")
        if layout=="auto":
            from .vision import directed_framing
            directed=directed_framing(analysis,plan["source"],plan["trim"]["duration"],config,read_json(ROOT/"reports"/"framing_gate.json",{}) or {})
            if directed:
                plan["framing"]=directed
                atomic_write_json(job_dir/"framing.json",directed)
        plan["caption_exclusions"] = caption_exclusions(analysis, plan["source"], config, plan["framing"])
        plan["face_observations"] = [{"t":row["t"],"track":row["track"],"source_box":row["source_box"]} for row in analysis.get("observations",[])]
    except (ImportError, RuntimeError) as exc:
        plan["tracking_fallback"] = str(exc)
    if framing_pins:
        from .framing_pins import normalize_pins as _normalize_pins, pins_to_framing as _pins_to_framing
        clean_pins = _normalize_pins(framing_pins, float(plan["trim"]["duration"]))
        if clean_pins:
            plan["framing"] = _pins_to_framing(clean_pins, int(source.get("width", 1920)), int(source.get("height", 1080)), float(plan["trim"]["duration"]), render_config, decision.get("framing_shape") or "9:16")
            plan["framing_pins"] = clean_pins
            plan["framing_shape"] = decision.get("framing_shape") or "9:16"
    if decision.get("speaker_frame",{}).get("enabled"):
        from .speaker_frame import build_framing,exclusions,validate_speaker_frame
        spec=validate_speaker_frame(decision["speaker_frame"],source["width"],source["height"],plan["trim"]["duration"])
        if "clip_start" in spec and (abs(spec["clip_start"]-candidate["start"])>.05 or abs(spec["clip_end"]-candidate["end"])>.05):
            raise SystemExit("Clip times changed. Open Speaker Frame and check the boxes again.")
        plan["auto_framing"]=plan["framing"]
        plan["speaker_frame"]=spec
        local_analysis=analysis if "analysis" in locals() else {}
        cuts=local_analysis.get("scene_cuts",[])
        plan["framing"]=build_framing(spec,{**plan["source"],"clip_start":candidate["start"]},plan["trim"]["duration"],config,read_json(job_dir/"turns.json",{}),cuts,local_analysis.get("observations",[]))
        plan["caption_exclusions"]=exclusions(plan["framing"],config.regions["feed"],local_analysis.get("observations",[]))
    from .vision import source_text_exclusions
    text_exclusions=source_text_exclusions(read_json(job_dir/"shots.json",{}) or {},plan["source"],config,plan["framing"],candidate["start"],candidate["end"])
    if text_exclusions:
        plan.setdefault("caption_exclusions",[]).extend(text_exclusions)
        plan["source_text_policy"]={"source_has_captions":True,"action":"avoid_detected_band","detector":"edge_density_heuristic","trust_source_captions":config.get("source_text","trust_source_captions",default=False)}
    from .polish import apply_polish
    polish = apply_polish(plan, transcript, config)
    atomic_write_json(job_dir / "polish.json", polish)
    candidate["edited"] = plan.get("edited", False)
    candidate["edits"] = plan.get("edits", [])
    candidate["augmented"] = bool(candidate.get("augmented") or polish.get("nameplates") or config.get("audio","music_file") or config.get("audio","sfx_file"))
    plan["augmented"] = candidate["augmented"]
    if polish.get("punch_ins"):
        plan["caption_exclusions"] = caption_exclusions(analysis,plan["source"],config,plan["framing"])+text_exclusions if "analysis" in locals() else plan.get("caption_exclusions",[])
    if not plan.get("source_spans") and not candidate.get("receipt"):
        from .craft import prepare_emoji_pops
        pops=prepare_emoji_pops(plan,transcript,config,job_dir)
        candidate["augmented"]=candidate["augmented"] or bool(pops["items"])
        plan["augmented"]=candidate["augmented"]
    if plan.get("edited") and not any(flag.get("code")=="I-3" for flag in candidate["integrity_flags"]):
        candidate["integrity_flags"].append({"code":"I-3","severity":"review","reason":"Disclosed edited clip"})
    plan["cache_variants"] = args.variants > 1
    plan["debug_overlay"]=getattr(args,"debug_overlay",False)
    plan["transcript"] = transcript
    if candidate.get("receipt"):
        from .timeline import kept_spans
        plan["receipt"]=candidate["receipt"]
        plan["source_spans"]=kept_spans(candidate["start"],candidate["end"],candidate["edits"])
        plan["original_trim"]=dict(plan["trim"])
        plan["trim"]["duration"]=sum(span["end"]-span["start"] for span in plan["source_spans"])
        plan["edits"]=candidate["edits"]
        plan["edited"]=True
    plan["captions_ass"] = str(job_dir / "captions.ass")
    plan["caption_plan"] = str(job_dir / "captions_plan.json")
    plan["chrome_png"] = str(job_dir / "chrome.png")
    plan["craft_png"] = str(job_dir / "craft.png")
    plan["extras_png"] = str(job_dir / "extras.png")
    plan["decision"] = decision
    if getattr(args, "export_id", None):
        plan["export_id"] = validate_id(args.export_id)
    plan["plan_hash"] = content_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    atomic_write_json(job_dir / "render_plan.json", plan)
    output = job_dir / f"{candidate['id']}.mp4"
    store = JobStore(ROOT / "work" / "jobs.sqlite")
    try:
        store.transition(args.job, "rendering", json.dumps({"candidate_id": candidate["id"]}), "render")
    except ValueError:
        store.upsert(args.job, "rendering", json.dumps({"candidate_id": candidate["id"]}), "render")
    try:
        with job_processes(job_dir, store, args.job):
            render_result = render(plan, render_config, job_dir, output)
    except (ProcessCancelled, KeyboardInterrupt):
        store.upsert(args.job, "cancelled", json.dumps({"candidate_id": candidate["id"]}), "render")
        return 130
    except Exception as exc:
        store.upsert(args.job, "failed", json.dumps({"candidate_id": candidate["id"], "error": str(exc)}), "render")
        raise
    log_event(ROOT / "work" / "events.jsonl", args.job, "render", "rendered", output=str(output))
    proxy=job_dir/f"{candidate['id']}_proxy.mp4"
    proxy_partial=proxy.with_suffix(".mp4.part")
    from .core.tools import require_tool
    run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-i",output,"-vf","scale=540:960","-c:v","libx264","-preset","veryfast","-crf","25","-c:a","aac","-movflags","+faststart","-f","mp4",proxy_partial],timeout=max(120,plan["trim"]["duration"]*5))
    proxy_partial.replace(proxy)
    if getattr(args,"preview",False):
        print(json.dumps({"preview":str(proxy),"same_render_plan":plan["plan_hash"]}))
        store.upsert(args.job,"awaiting_review",json.dumps({"proxy":str(proxy)}),"preview")
        return 0
    qa_plan = read_json(job_dir / "runtime_plan.json", plan) if plan.get("source_spans") else plan
    report = validate_output(output, qa_plan, render_config, job_dir / "export_report.json")
    ordered_candidates = sorted(candidates, key=lambda row: float(row.get("score", 0)), reverse=True)
    rank = next((index + 1 for index, row in enumerate(ordered_candidates) if row.get("id") == candidate.get("id")), 1)
    export_dir, export_filename = export_names(ROOT / "exports", args.job, source, candidate, plan.get("headline", ""), rank, plan.get("plan_hash", ""))
    if plan.get("export_id"):
        export_dir = export_dir.with_name(export_dir.name + "_" + plan["export_id"])
    plan["export_filename"] = export_filename
    plan["export_folder"] = str(export_dir)
    accepted_review=bool(getattr(args,"accept_review",False) or decision.get("accept_review",False))
    if report["status"] == "passed" or (report["status"]=="needs_review" and accepted_review):
        report["review_accepted"]=report["status"]=="needs_review" and accepted_review
        bundle = export_bundle(export_dir, output, plan, qa_plan.get("transcript", transcript), source, candidate, report, config=config)
        report["export"] = bundle
    if args.variants > 1 and report["status"] != "failed":
        from .variants import render_variants
        report["variants"] = render_variants(plan, qa_plan, candidate, config, job_dir, min(3, args.variants))
    atomic_write_json(job_dir / "export_report.json", report)
    if report.get("export"):
        refresh_export_catalog(ROOT / "exports")
    check_cancelled()
    store.upsert(args.job, report["status"], json.dumps(report), "qa")
    log_event(ROOT / "work" / "events.jsonl", args.job, "qa", "completed", status=report["status"])
    print(json.dumps({"render": render_result, "qa": report}, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "failed" else 1


def command_find(args: argparse.Namespace) -> int:
    _, _, _, artifact = _load_job(args.job)
    print(json.dumps({"query": args.q, "results": prompt_search(artifact.get("candidates", []), args.q, args.top)}, indent=2, ensure_ascii=False))
    return 0


def command_resume(args: argparse.Namespace) -> int:
    validate_id(args.job)
    folder=ROOT/"work"/args.job
    if not (folder/"transcript.json").is_file():
        request=(read_json(folder/"job_request.json",{}) or {}).get("request")
        if not request:
            raise SystemExit("No saved job request")
        (folder/"cancel.request").unlink(missing_ok=True)
        return command_run(argparse.Namespace(**request))
    job_dir, source, transcript, artifact = _load_job(args.job)
    (job_dir / "cancel.request").unlink(missing_ok=True)
    candidates = artifact.get("candidates", [])
    candidate_id = args.candidate or (candidates[0].get("id") if candidates else None)
    if candidate_id:
        return command_render(argparse.Namespace(job=args.job, candidate=candidate_id, headline=None, layout="auto", variants=1))
    request=(read_json(job_dir/"job_request.json",{}) or {}).get("request",{})
    saved=(read_json(job_dir/"job_config.json",{}) or {}).get("preset","political_lens")
    return command_run(argparse.Namespace(source=source["path"], transcript=str(job_dir / "transcript.json"), job=args.job, preset=request.get("preset",saved), top=request.get("top",8), mode=request.get("mode","review"), auto_threshold=request.get("auto_threshold",90), rights_class=source.get("rights_class", "unknown"), rights_note=source.get("rights_note", ""), no_network=request.get("no_network",True), force=False, comments=request.get("comments",0)))


def command_cancel(args: argparse.Namespace) -> int:
    validate_id(args.job)
    job_dir = ROOT / "work" / args.job
    store = JobStore(ROOT / "work" / "jobs.sqlite")
    if not job_dir.is_dir() or not store.get(args.job):
        raise SystemExit("Job not found")
    from .core.io import atomic_write_bytes
    atomic_write_bytes(job_dir / "cancel.request", b"cancel")
    store.upsert(args.job, "cancelled", json.dumps({"cancel_requested": True}), "cancel")
    print(json.dumps({"job_id": args.job, "state": "cancelled"}))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    from .core.config import AppConfig
    saved_config = read_json(Path(args.plan).parent / "renderer_config.json", {}) or read_json(Path(args.plan).parent / "job_config.json", {}) or {}
    config = AppConfig(saved_config["config"]) if saved_config.get("config") else load_config()
    report = validate_output(Path(args.output), plan, config)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "failed" else 1


def command_watch(args: argparse.Namespace) -> int:
    inbox = Path(args.inbox).expanduser()
    if not inbox.exists():
        raise SystemExit(f"Inbox does not exist: {inbox}")
    seen: dict[str, tuple[int, int]] = {}
    observed: dict[str, tuple[int,int]] = {}
    processed = 0
    try:
        while True:
            files = sorted(path for path in inbox.iterdir() if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"})
            for path in files:
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                if seen.get(str(path)) == signature:
                    continue
                if not args.once and observed.get(str(path))!=signature:
                    observed[str(path)]=signature
                    continue
                from .queue import enqueue,worker
                enqueue(path,mode=args.mode)
                worker()
                seen[str(path)] = signature
                processed += 1
            if args.once:
                break
            time.sleep(max(0.5, float(args.interval)))
    except KeyboardInterrupt:
        pass
    print(json.dumps({"inbox": str(inbox), "processed": processed, "mode": args.mode, "once": args.once}, indent=2))
    return 0


def command_studio(args: argparse.Namespace) -> int:
    from .studio.server import create_app

    app, token = create_app(lan=args.lan)
    print(f"Review Studio token: {token}" if token else "Review Studio bound to 127.0.0.1")
    if args.lan:
        import ipaddress
        import socket
        import qrcode
        from urllib.parse import quote
        addresses=[]
        try:
            import psutil
            addresses=[entry.address for interface in psutil.net_if_addrs().values() for entry in interface if entry.family==socket.AF_INET and ipaddress.ip_address(entry.address).is_private and not ipaddress.ip_address(entry.address).is_loopback]
        except ImportError:
            pass
        for address in sorted(set(addresses)):
            url=f"http://{address}:{args.port}/?token={quote(token)}"
            print(f"LAN review: {url}")
            code=qrcode.QRCode(border=1)
            code.add_data(url)
            code.make(fit=True)
            code.print_ascii(out=sys.stdout,invert=True)
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install uvicorn to run Studio") from exc
    uvicorn.run(app, host="0.0.0.0" if args.lan else "127.0.0.1", port=args.port, log_level="info")
    return 0


def command_update_ytdlp() -> int:
    output = run_process([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], timeout=600)
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dc", description="Political Lens local debate-shorts factory", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    run = sub.add_parser("run")
    run.add_argument("--source", required=True)
    run.add_argument("--transcript")
    run.add_argument("--job")
    run.add_argument("--preset", default="political_lens")
    run.add_argument("--top", type=int, default=8)
    run.add_argument("--mode", choices=("review", "auto", "batch"), default="review")
    run.add_argument("--auto-threshold", type=float, default=90)
    run.add_argument("--rights-class", choices=("own", "permission", "public_domain_verified", "licensed", "unknown"), default="unknown")
    run.add_argument("--rights-note", default="")
    run.add_argument("--no-network", action="store_true")
    run.add_argument("--force", action="store_true")
    run.add_argument("--comments",type=int,default=0,help="explicit opt-in; store timestamp-bin counts only")
    find = sub.add_parser("find")
    find.add_argument("--job", required=True)
    find.add_argument("--q", required=True)
    find.add_argument("--top", type=int, default=5)
    resume = sub.add_parser("resume")
    resume.add_argument("--job", required=True)
    resume.add_argument("--candidate")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--job", required=True)
    render_parser = sub.add_parser("render")
    render_parser.add_argument("--job", required=True)
    render_parser.add_argument("--candidate", required=True)
    render_parser.add_argument("--headline")
    render_parser.add_argument("--layout", choices=("auto", "dual", "manual"), default="auto")
    render_parser.add_argument("--crop", help="manual source rectangle x,y,w,h; preserves feed aspect ratio")
    render_parser.add_argument("--preset", help="override the saved job brand preset")
    render_parser.add_argument("--variants", type=int, default=1)
    render_parser.add_argument("--debug-overlay",action="store_true",help="show analysis/exclusion/caption guides inside feed only")
    render_parser.add_argument("--accept-review",action="store_true",help="explicitly accept a needs_review export; unresolved publish gates still apply")
    preview=sub.add_parser("preview",help="render a 540x960 proxy from the same saved RenderPlan")
    preview.add_argument("--job",required=True)
    preview.add_argument("--candidate",required=True)
    receipts=sub.add_parser("receipts",help="prepare a disclosed same-speaker A2 proposal for manual review")
    receipts.add_argument("--job",required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--output", required=True)
    validate.add_argument("--plan", required=True)
    watch = sub.add_parser("watch")
    watch.add_argument("--inbox", required=True)
    watch.add_argument("--mode", choices=("review", "auto"), default="review")
    watch.add_argument("--interval", type=float, default=2.0)
    watch.add_argument("--once", action="store_true", help="scan once instead of waiting for new files")
    batch=sub.add_parser("batch")
    batch.add_argument("--sources",required=True,help="folder containing media")
    batch.add_argument("--mode",choices=("review","auto"),default="review")
    batch.add_argument("--preset",default="political_lens")
    sub.add_parser("worker")
    cleanup=sub.add_parser("cleanup")
    cleanup.add_argument("--retention-days",type=int,default=14)
    studio = sub.add_parser("studio")
    studio.add_argument("--lan", action="store_true")
    studio.add_argument("--port", type=int, default=8765)
    analytics = sub.add_parser("analytics", help="fit a proposal-only ridge model from labeled clip statistics")
    analytics.add_argument("--csv", required=True)
    analytics.add_argument("--target", default="avg_percent_watched")
    sub.add_parser("learn", help="cross-validate a proposal-only taste model from Studio decisions")
    translate=sub.add_parser("translate")
    translate.add_argument("--job",required=True)
    translate.add_argument("--lang",required=True)
    translate.add_argument("--model",required=True)
    series=sub.add_parser("series")
    series.add_argument("--job",required=True)
    series.add_argument("--candidate",required=True)
    benchmark=sub.add_parser("bench")
    benchmark.add_argument("--job")
    benchmark.add_argument("--candidate")
    bakeoff=sub.add_parser("bakeoff")
    bakeoff.add_argument("--ratings")
    evaluate=sub.add_parser("evaluate")
    evaluate.add_argument("--job",required=True)
    evaluate.add_argument("--labels",required=True,help="JSON array of actual human labels")
    sub.add_parser("diag")
    sub.add_parser("update-ytdlp")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        report=run_doctor()
        print_doctor(report)
        return 1 if report["status"]=="fail" else 0
    if args.command == "run":
        if Path(args.source).is_dir():
            from .queue import enqueue,worker
            for source in sorted(Path(args.source).iterdir()):
                if source.is_file() and source.suffix.lower() in {".mp4",".mkv",".mov",".webm"}:
                    enqueue(source,"review" if args.mode=="batch" else args.mode,args.preset,args.rights_class,args.rights_note)
            print(json.dumps(worker(),indent=2))
            return 0
        try:
            return command_run(args)
        except (ProcessCancelled,KeyboardInterrupt):
            if args.job:
                JobStore(ROOT/"work"/"jobs.sqlite").upsert(args.job,"cancelled","{}","cancel")
            return 130
        except ResourceBusy as exc:
            print(str(exc),file=sys.stderr)
            return 75
        except Exception as exc:
            if args.job:
                from .core.logging import redact
                JobStore(ROOT/"work"/"jobs.sqlite").upsert(args.job,"failed",json.dumps({"error":redact(str(exc))}),"run")
            raise
    if args.command == "render":
        return command_render(args)
    if args.command == "preview":
        return command_render(argparse.Namespace(job=args.job,candidate=args.candidate,headline=None,layout="auto",variants=1,preview=True))
    if args.command == "receipts":
        from .craft import receipt_pair
        from .selection import generate_headlines,integrity_flags
        folder,source,transcript,artifact=_load_job(args.job)
        saved=read_json(folder/"job_config.json",{}) or {}
        config=load_preset(saved.get("preset","political_lens"))
        receipt=receipt_pair(transcript,config)
        if not receipt:
            print(json.dumps({"status":"no_safe_receipt_proposal","reason":"Requires a verified same speaker, complete claims, and no nearby qualifier"}))
            return 0
        start=max(0,receipt["first"]["start"]-.12)
        end=min(source["duration"],receipt["second"]["end"]+.35)
        cut={"start":receipt["first"]["end"]+.15,"end":receipt["second"]["start"]-.12,"kind":"receipt_gap"}
        text=receipt["first"]["text"]+" "+receipt["second"]["text"]
        candidate_id="c_"+content_hash({"source":source["source_id"],"receipt":receipt})[:12]
        candidate={"schema_version":5,"id":candidate_id,"source_id":source["source_id"],"start":start,"end":end,"duration":end-start-(cut["end"]-cut["start"]),"archetype":"A2","score":0,"components":{},"penalties":[],"text":text,"hook":{"spoken":receipt["first"]["text"],"headline_options":generate_headlines(text,config)},"integrity_flags":integrity_flags(text,source.get("rights_class","unknown"),edited=True),"boundary":{"confidence":.8},"layout_confidence":.35,"edited":True,"edits":[cut],"receipt":receipt,"provenance":"local","claims":[]}
        artifact["candidates"]=[row for row in artifact.get("candidates",[]) if row["id"]!=candidate_id]+[candidate]
        atomic_write_json(folder/"receipt.json",receipt)
        atomic_write_json(folder/"candidates.json",artifact)
        print(json.dumps({"status":"awaiting_manual_review","candidate":candidate},indent=2))
        return 0
    if args.command == "find":
        return command_find(args)
    if args.command == "resume":
        return command_resume(args)
    if args.command == "cancel":
        return command_cancel(args)
    if args.command == "validate":
        return command_validate(args)
    if args.command == "watch":
        return command_watch(args)
    if args.command=="batch":
        from .queue import enqueue,worker
        folder=Path(args.sources)
        if not folder.is_dir(): raise SystemExit("Sources folder absent")
        for source in sorted(folder.iterdir()):
            if source.is_file() and source.suffix.lower() in {".mp4",".mov",".mkv",".webm"}:
                enqueue(source,args.mode,args.preset)
        print(json.dumps(worker(),indent=2))
        return 0
    if args.command=="worker":
        from .queue import worker
        print(json.dumps(worker(),indent=2))
        return 0
    if args.command=="cleanup":
        from .ops import cleanup_work
        from .core.locking import exclusive_file
        with exclusive_file(ROOT/"work"/"execution.lock"):
            print(json.dumps({"removed":cleanup_work(ROOT,args.retention_days)}))
        return 0
    if args.command == "studio":
        return command_studio(args)
    if args.command == "analytics":
        from .learn import import_analytics
        print(json.dumps(import_analytics(Path(args.csv), ROOT / "reports" / "proposals", args.target), indent=2))
        return 0
    if args.command == "learn":
        from .learn import propose_taste_update,propose_boundary_bias
        with JobStore(ROOT / "work" / "jobs.sqlite").connect() as db:
            labels = [json.loads(row["payload"]) for row in db.execute("SELECT payload FROM labels ORDER BY id")]
        print(json.dumps(propose_taste_update(labels, ROOT / "reports" / "proposals"), indent=2))
        print(json.dumps(propose_boundary_bias(labels,ROOT/"reports"/"proposals"),indent=2))
        return 0
    if args.command=="translate":
        from .translation import export_translation
        folder,_,transcript,_=_load_job(args.job)
        export_translation(transcript,args.lang,args.model,folder/"translations",load_config())
        return 0
    if args.command=="series":
        from .polish import split_series
        folder,_,transcript,artifact=_load_job(args.job)
        candidate=next((row for row in artifact.get("candidates",[]) if row["id"]==args.candidate),None)
        if not candidate: raise SystemExit("Candidate absent")
        parts=split_series(candidate,transcript)
        artifact["candidates"]=[row for row in artifact["candidates"] if row["id"] not in {part["id"] for part in parts}]+parts
        atomic_write_json(folder/"candidates.json",artifact)
        print(json.dumps({"parts":parts},indent=2))
        return 0
    if args.command == "bench":
        if args.job and args.candidate:
            from .ops import bench_render
            result=bench_render(args.job,args.candidate,ROOT/"reports"/"bench_render.json")
        else:
            result = bench(ROOT / "reports" / "bench.json")
        (ROOT / "reports" / "bench.md").write_text("# Bench\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "diag":
        print(diag(ROOT / "reports" / "diag.zip"))
        return 0
    if args.command == "update-ytdlp":
        return command_update_ytdlp()
    if args.command == "bakeoff":
        report = ROOT / "reports" / "bakeoff.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        if args.ratings:
            import csv
            from .evaluation import compare_bakeoff
            with Path(args.ratings).open(encoding="utf-8",newline="") as handle:
                results=compare_bakeoff(list(csv.DictReader(handle)))
            atomic_write_json(ROOT/"reports"/"bakeoff.json",results)
            report.write_text("# Bake-off\n\n```json\n"+json.dumps(results,indent=2)+"\n```\n",encoding="utf-8")
        elif not report.exists():
            report.write_text("# Bake-off\n\nNot run: comparable exports and actual blind ratings are required. See bakeoff_plan.md.\n",encoding="utf-8")
        print(report)
        return 0
    if args.command=="evaluate":
        from .evaluation import candidate_metrics
        _,_,_,artifact=_load_job(args.job)
        results=candidate_metrics(artifact.get("candidates",[]),read_json(Path(args.labels),[]))
        atomic_write_json(ROOT/"reports"/(args.job+"_evaluation.json"),results)
        print(json.dumps(results,indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
