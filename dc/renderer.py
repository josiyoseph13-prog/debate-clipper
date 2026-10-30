from __future__ import annotations

import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .captions import build_captions
from .chrome import render_chrome, render_extras
from .craft import build_craft_ass, render_craft_overlay
from .core.config import AppConfig, ROOT
from .core.hashing import content_hash
from .core.io import atomic_write_json, atomic_copy
from .core.process import ProcessCancelled, run_process, transform_video_stream
from .core.tools import require_tool, filter_script_args
from .framing import framing_plan, path_is_static, rect_at, warp_subpixel
from .ingest import ffprobe
from .layout import crop_rect


def _relative(path: Path, cwd: Path) -> str:
    try:
        return os.path.relpath(path.resolve(), cwd.resolve()).replace("\\", "/")
    except ValueError:
        # Different Windows drives cannot have a relative path. This is safe
        # for argv media inputs; ASS/font assets are staged locally below.
        return path.resolve().as_posix()


def _job_fonts(work_dir: Path) -> str:
    original=ROOT/"assets"/"fonts"
    try:
        return os.path.relpath(original.resolve(),work_dir.resolve()).replace("\\","/")
    except ValueError:
        target=work_dir/"render_fonts"
        if target.is_symlink():raise ValueError("Job font folder must not be a symlink")
        target.mkdir(exist_ok=True)
        from .core.hashing import file_hash
        for source in original.iterdir():
            if source.suffix.lower() not in {".ttf",".otf"}:continue
            destination=target/source.name
            if not destination.is_file() or file_hash(source)!=file_hash(destination):
                atomic_copy(source,destination)
        return target.name


def needs_subpixel(plan,config):
    return bool(plan.get("speaker_frame",{}).get("enabled")) or len(plan["framing"].get("segments",[]))>1 or not path_is_static(plan["framing"].get("path",[]),float(config.get("renderer","static_threshold_px",default=.25)))


def make_render_plan(source: dict[str, Any], candidate: dict[str, Any], config: AppConfig, job_dir: Path, headline: str | None = None, mode: str = "auto", manual_regions: list[dict[str, float]] | None = None) -> dict[str, Any]:
    source_w, source_h = int(source["width"]), int(source["height"])
    duration = float(candidate["end"]) - float(candidate["start"])
    framing = framing_plan(source_w, source_h, duration, config, mode=mode, manual_regions=manual_regions)
    headline = headline if headline is not None else next(iter(candidate.get("hook", {}).get("headline_options", [])), "The full exchange")
    fingerprint = source.get("fingerprint", {})
    from .audio import probe_frame_rate
    probe=dict(source.get("probe", {}))
    try:
        packets=json.loads(run_process([require_tool("ffprobe"),"-v","error","-select_streams","v:0","-read_intervals",f"{candidate['start']}%+{min(20,duration)}","-show_packets","-show_entries","packet=pts_time","-of","json",source["path"]],timeout=30))
        probe["packets"]=packets.get("packets",[])
    except (RuntimeError,ValueError): pass
    frame_rate = probe_frame_rate(probe, float(config.get("output", "fps_cap", default=30)))
    render_plan = {"schema_version": 5, "source": {"path": source["path"], "sha256": fingerprint.get("sha256", source.get("sha256")), "source_id": source["source_id"], "has_audio": bool(source.get("has_audio", True)), "width": source_w, "height": source_h, "fps": source.get("fps"), "meta": source.get("meta", {})}, "trim": {"start": float(candidate["start"]), "end": float(candidate["end"]), "duration": duration}, "candidate_id": candidate["id"], "headline": headline, "framing": framing, "craft": {"question_chip": candidate.get("question_chip"), "evidence_card": candidate.get("evidence_card")}, "config_hash": config.hash(), "output": config.get("output", default={}), "audio": config.get("audio", default={}), "frame_rate": frame_rate, "tool_versions": {"app": "5.0.0"}}
    guard=int(config.get("qa","bottom_guard_px",default=4))
    if guard<0 or 2*guard>=config.regions["feed"]["h"]:raise ValueError("Invalid in-feed boundary guard")
    render_plan["boundary_guards"]={"top_px":guard,"bottom_px":guard,"location":"inside_feed","version":1}
    render_plan["plan_hash"] = content_hash(render_plan)
    for tool in ("ffmpeg","ffprobe"):
        try:
            render_plan["tool_versions"][tool]=run_process([require_tool(tool),"-version"],timeout=10,output_limit=10000).splitlines()[0]
        except RuntimeError:
            render_plan["tool_versions"][tool]="unavailable"
    render_plan["plan_hash"]=content_hash({key:value for key,value in render_plan.items() if key!="plan_hash"})
    atomic_write_json(job_dir / "framing.json", framing)
    atomic_write_json(job_dir / "layout.json", {"schema_version": 5, "preset": config.data.get("preset"), "mode": framing["segments"][0].get("mode"), "regions": config.regions, "headline": headline})
    atomic_write_json(job_dir / "polish.json", {"schema_version": 5, "punch_ins": [], "tight_cut": [], "nameplates": [], "audio": config.get("audio", default={}), "edited": bool(candidate.get("edited", False))})
    atomic_write_json(job_dir / "render_plan.json", render_plan)
    return render_plan


def _filter_script(plan: dict[str, Any], config: AppConfig, work_dir: Path, has_audio: bool, video_input: int = 0, audio_input: int = 0, video_is_feed: bool = False, chrome_input: int = 1, craft_input: int = 2, extras_input: int = 3, evidence_input: int = 4, loudnorm_stats: dict[str, Any] | None = None) -> str:
    feed = config.regions["feed"]
    canvas = config.canvas
    rect = plan["framing"]["path"][0]
    crop_w, crop_h = max(2, int(round(rect["w"]))), max(2, int(round(rect["h"])))
    crop_x, crop_y = max(0, int(round(rect["x"]))), max(0, int(round(rect["y"])))
    ass = "captions.ass"
    fonts = "'"+_job_fonts(work_dir).replace("'",r"\'")+"'"
    duration = float(plan["trim"]["duration"])
    fps = float(plan.get("frame_rate", {}).get("target_cfr", config.get("output", "fps_cap", default=30)))
    mode = str(plan.get("framing", {}).get("segments", [{}])[0].get("mode", "SINGLE"))
    if mode == "WIDE" and not video_is_feed:
        feed_chain = f"[{video_input}:v]trim=start=0:end={duration},setpts=PTS-STARTPTS,split=2[widebg][widefg];[widebg]scale={feed['w']}:{feed['h']}:force_original_aspect_ratio=increase,crop={feed['w']}:{feed['h']},boxblur=20:2[blur];[widefg]scale={feed['w']}:{feed['h']}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1[fg];[blur][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps},subtitles={ass}:fontsdir={fonts}[feed]"
    elif mode == "DUAL" and not video_is_feed and len(plan["framing"].get("segments", [{}])[0].get("regions", [])) >= 2:
        first, second = plan["framing"]["segments"][0]["regions"][:2]
        panel_h = int(feed['h']) // 2
        divider = int(config.get("framing", "divider_px", default=4))
        feed_chain = f"[{video_input}:v]trim=start=0:end={duration},setpts=PTS-STARTPTS,split=2[a][b];[a]crop={int(first['w'])}:{int(first['h'])}:{int(first['x'])}:{int(first['y'])},scale={feed['w']}:{panel_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={feed['w']}:{panel_h}[at];[b]crop={int(second['w'])}:{int(second['h'])}:{int(second['x'])}:{int(second['y'])},scale={feed['w']}:{panel_h}:force_original_aspect_ratio=increase:flags=lanczos,crop={feed['w']}:{panel_h}[bt];[at][bt]vstack=inputs=2,drawbox=x=0:y={panel_h-divider//2}:w=iw:h={divider}:color=white@0.6:t=fill,setsar=1,fps={fps},subtitles={ass}:fontsdir={fonts}[feed]"
    elif video_is_feed:
        feed_chain = f"[{video_input}:v]trim=start=0:end={duration},setpts=PTS-STARTPTS,scale={feed['w']}:{feed['h']}:flags=lanczos,fps={fps},setsar=1,subtitles={ass}:fontsdir={fonts}[feed]"
    else:
        feed_chain = f"[{video_input}:v]trim=start=0:end={duration},setpts=PTS-STARTPTS,crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={feed['w']}:{feed['h']}:flags=lanczos,fps={fps},setsar=1,subtitles={ass}:fontsdir={fonts}[feed]"
    fast_glow=config.get("captions","glow","method",default="ass_layers")=="fast_glow" and config.get("craft","caption_mode",default="hormozi_glow")=="hormozi_glow"
    if fast_glow:
        feed_chain=feed_chain.replace(f",subtitles={ass}:fontsdir={fonts}[feed]","[rawfeed]")
        sigma=float(config.get("captions","glow","outer_blur",default=16))
        feed_chain+=f";color=c=black@0:s={feed['w']}x{feed['h']}:r={fps}:d={duration},format=rgba,subtitles=active_fill.ass:fontsdir={fonts}:alpha=1,gblur=sigma={sigma},colorchannelmixer=aa=0.5[halo];[rawfeed][halo]overlay=0:0:shortest=1,subtitles=captions_lite.ass:fontsdir={fonts}[feed]"
    chip = plan.get("craft", {}).get("question_chip") or {"start": 0, "end": 0}
    card = plan.get("craft", {}).get("evidence_card") or {"start": 0, "end": 0}
    feed_chain = feed_chain.replace("[feed]", f",subtitles=craft.ass:fontsdir={fonts}[feed]")
    if plan.get("debug_overlay"):
        feed_chain=feed_chain.replace("[feed]",f",subtitles=debug.ass:fontsdir={fonts}[feed]")
    if plan.get("emoji_pops"):
        feed_chain=feed_chain.replace("[feed]","[popped0]")
        for index,item in enumerate(plan["emoji_pops"]):
            target="feed" if index==len(plan["emoji_pops"])-1 else f"popped{index+1}"
            feed_chain+=f";movie={item['file']},setpts=PTS-STARTPTS,format=rgba[emoji{index}];[popped{index}][emoji{index}]overlay={item['x']}:{item['y']}:enable='gte(t,{item['start']})*lt(t,{item['end']})'[{target}]"
    # Physical white pixels inside the feed protect chrome/footer from codec
    # spread. Missing fields retain the behavior of older saved RenderPlans.
    guards=plan.get("boundary_guards",{})
    guard_filters=[]
    for edge in ("top","bottom"):
        pixels=int(guards.get(edge+"_px",0))
        if pixels<0 or 2*pixels>=feed["h"]:raise ValueError("Invalid saved boundary guard")
        if pixels:guard_filters.append(f"drawbox=x=0:y={'0' if edge=='top' else 'ih-'+str(pixels)}:w=iw:h={pixels}:color=white:t=fill")
    if guard_filters:feed_chain=feed_chain.replace("[feed]",","+",".join(guard_filters)+"[feed]")
    graph = [feed_chain, f"color=c=white:s={canvas['w']}x{canvas['h']}:r={fps}:d={duration}[bg]", f"[bg][feed]overlay={feed['x']}:{feed['y']}:shortest=1[base]", f"[{craft_input}:v]format=rgba[craft]", f"[base][craft]overlay={feed['x']}:{feed['y']}:shortest=1:enable='gte(t,{float(chip.get('start', 0))})*lt(t,{float(chip.get('end', 2.5))})'[questioned]", f"[{evidence_input}:v]format=rgba[evidence]", f"[questioned][evidence]overlay={feed['x']}:{feed['y']}:shortest=1:enable='gte(t,{float(card.get('start', 0))})*lt(t,{float(card.get('end', 1.8))})'[augmented]", f"[{chrome_input}:v]format=rgba[chrome]", "[augmented][chrome]overlay=0:0:shortest=1[chromed]", f"[{extras_input}:v]format=rgba[extras]", "[chromed][extras]overlay=0:0:shortest=1[extras_composed]"]
    progress = config.get("polish", "progress_bar", default={})
    final = "extras_composed"
    if progress.get("enabled"):
        margin = int(progress.get("x", canvas["w"] * .11))
        bar_w = int(canvas["w"] - margin * 2)
        bar_h = int(progress.get("h", 6))
        bar_y = int(progress.get("y", config.regions["bottom_white"]["y"] + 8))
        graph.extend([f"color=c=0xE6E8EB:s={bar_w}x{bar_h}:r={fps}:d={duration}[track]", f"color=c=0xEC0000:s={bar_w}x{bar_h}:r={fps}:d={duration}[progress]", f"[track][progress]overlay=x='-w+min(1,t/{duration})*w':y=0:shortest=1[bar]", f"[extras_composed][bar]overlay={margin}:{bar_y}:shortest=1[progress_composed]"])
        final = "progress_composed"
    graph.append(f"[{final}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[outv]")
    if has_audio:
        fade = float(config.get("audio", "fade_ms", default=30)) / 1000
        # Every source input is sought to the clip start before decoding.
        audio_trim = f"atrim=start=0:end={duration}"
        target_lufs = float(config.get('audio', 'target_lufs', default=-14))
        true_peak = float(config.get("audio", "true_peak_db", default=-1))
        # Normalize to the same peak ceiling as the final limiter, so the
        # limiter does not undo the measured loudness gain.
        window_loudnorm=config.get("audio","window_loudnorm",default=False)
        loudnorm = f"loudnorm=I={target_lufs}:TP={true_peak-1.5}:LRA=11" if window_loudnorm else f"loudnorm=I={target_lufs}:TP={true_peak}"
        if loudnorm_stats:
            try:
                if window_loudnorm:
                    values={key:float(loudnorm_stats[key]) for key in ("measured_I","measured_LRA","measured_TP","measured_thresh","offset")}
                    if all(math.isfinite(value) for value in values.values()):
                        loudnorm += ":" + ":".join(f"{key}={value}" for key,value in values.items()) + ":linear=false"
                else:
                    # Saved V5 presets retain their original audio graph.
                    measured_i=float(loudnorm_stats.get("measured_I"))
                    loudnorm=f"volume={target_lufs-measured_i:.3f}dB,{loudnorm}"
            except (KeyError, TypeError, ValueError):
                pass
        # Leave headroom for AAC true-peak overshoot after encoding.
        limiter = 10 ** ((true_peak - 1.5) / 20)
        audio_hz = int(config.get('output', 'audio_hz', default=48000))
        normalization = f",{loudnorm},alimiter=limit={limiter:.6f}:attack=5:release=50:level=false:latency=true" if config.get("audio", "loudnorm", default=True) else ""
        denoise = ",afftdn=nr=6" if config.get("audio", "denoise", default=False) else ""
        graph.append(f"[{audio_input}:a]{audio_trim},asetpts=PTS-STARTPTS{denoise},afade=t=in:st=0:d={fade},afade=t=out:st={max(0, duration-fade)}:d={fade}{normalization},aresample={audio_hz}[outa]")
    return ";\n".join(graph) + ";\n"


def render_subpixel_feed(source: Path, plan: dict[str, Any], config: AppConfig, output_path: Path) -> Path:
    """Normalize frame cadence before warping, then preserve a lossless feed."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for moving camera paths") from exc
    feed = config.regions["feed"]
    import numpy as np
    fps = float(plan.get("frame_rate", {}).get("target_cfr", 30))
    width, height = int(plan["source"]["width"]), int(plan["source"]["height"])
    duration = float(plan["trim"]["duration"])
    decode_args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", str(plan["trim"]["start"]), "-i", _relative(source, output_path.parent), "-t", str(duration), "-an", "-vf", f"fps={fps}", "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"]
    encode_args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pixel_format", "bgr24", "-video_size", f"{feed['w']}x{feed['h']}", "-framerate", str(fps), "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", "-f", "matroska", output_path.name]
    def transform(raw, frame_index):
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
        time=frame_index/fps
        segment=next((row for row in plan["framing"]["segments"] if row["t0"]<=time<row["t1"]),plan["framing"]["segments"][-1])
        if plan.get("speaker_frame",{}).get("enabled") and segment["mode"]!="WIDE":
            from .speaker_frame import compose_frame
            image=compose_frame(frame,segment,feed["w"],feed["h"])
            index=plan["framing"]["segments"].index(segment)
            cuts=plan["framing"].get("debug",{}).get("camera_cuts",[])
            if index and 0<=time-segment["t0"]<.18 and not any(abs(cut-segment["t0"])<.2 for cut in cuts):
                previous=plan["framing"]["segments"][index-1]
                if previous["mode"]!="WIDE":
                    old=compose_frame(frame,previous,feed["w"],feed["h"])
                    weight=(time-segment["t0"])/.18
                    image=np.rint(old*(1-weight)+image*weight).astype(np.uint8)
            return image.tobytes()
        if segment["mode"]=="WIDE":
            scale=max(feed["w"]/width,feed["h"]/height)
            background=cv2.resize(frame,(round(width*scale),round(height*scale)),interpolation=cv2.INTER_LINEAR)
            ox,oy=(background.shape[1]-feed["w"])//2,(background.shape[0]-feed["h"])//2
            background=cv2.GaussianBlur(background[oy:oy+feed["h"],ox:ox+feed["w"]],(0,0),20)
            scale=min(feed["w"]/width,feed["h"]/height)
            foreground=cv2.resize(frame,(round(width*scale),round(height*scale)),interpolation=cv2.INTER_LANCZOS4)
            ox,oy=(feed["w"]-foreground.shape[1])//2,(feed["h"]-foreground.shape[0])//2
            background[oy:oy+foreground.shape[0],ox:ox+foreground.shape[1]]=foreground
            return background.tobytes()
        if segment["mode"]=="DUAL":
            panel_height=feed["h"]//2
            images=[warp_subpixel(frame,rect,feed["w"],panel_height) for rect in segment["regions"][:2]]
            background=np.concatenate(images,axis=0)
            divider=int(config.get("framing","divider_px",default=4))
            background[panel_height-divider//2:panel_height+(divider+1)//2]=255
            return background.tobytes()
        rect = rect_at(plan["framing"]["path"], time)
        return warp_subpixel(frame, rect, int(feed["w"]), int(feed["h"])).tobytes()
    count = transform_video_stream(decode_args, encode_args, width * height * 3, transform, output_path.parent, max(120, duration * 20))
    atomic_write_json(output_path.parent / "moving_feed_manifest.json", {"schema_version": 5, "fps": fps, "frames": count, "codec": "ffv1", "mode": "single_frame_stream", "plan_hash": plan.get("plan_hash")})
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Sub-pixel intermediate was empty")
    return output_path


def _measure_loudnorm(source: Path, plan: dict[str, Any], config: AppConfig) -> dict[str, Any] | None:
    if not config.get("audio", "loudnorm", default=True):
        return None
    try:
        duration=float(plan["trim"]["duration"])
        fade=float(config.get("audio","fade_ms",default=30))/1000
        denoise="afftdn=nr=6," if config.get("audio","denoise",default=False) else ""
        filters=f"atrim=start=0:end={duration},asetpts=PTS-STARTPTS,{denoise}afade=t=in:st=0:d={fade},afade=t=out:st={max(0,duration-fade)}:d={fade},loudnorm=I={config.get('audio','target_lufs',default=-14)}:TP={float(config.get('audio','true_peak_db',default=-1))-1.5}:LRA=11:print_format=json"
        # Seek before decoding, exactly as the real render does. An output-side
        # seek measures pre-clip audio too and gives a wrong first-pass gain.
        if config.get("audio","window_loudnorm",default=False):
            output = run_process([require_tool("ffmpeg"), "-hide_banner", "-ss", str(plan["trim"]["start"]), "-i", source, "-t", str(duration), "-vn", "-af", filters, "-f", "null", "-"], timeout=max(120, int(duration * 10)), output_limit=100_000)
        else:
            output = run_process([require_tool("ffmpeg"), "-hide_banner", "-i", source, "-ss", str(plan["trim"]["start"]), "-t", str(duration), "-vn", "-af", f"loudnorm=I={config.get('audio','target_lufs',default=-14)}:TP={config.get('audio','true_peak_db',default=-1)}:LRA=11:print_format=json", "-f", "null", "-"], timeout=max(120,int(duration*10)),output_limit=100_000)
        blocks = re.findall(r"\{\s*\"input_i\".*?\}", output, flags=re.S)
        if not blocks:
            return None
        raw = json.loads(blocks[-1])
        return {"measured_I": raw.get("input_i"), "measured_LRA": raw.get("input_lra"), "measured_TP": raw.get("input_tp"), "measured_thresh": raw.get("input_thresh"), "offset": raw.get("target_offset", 0)}
    except ProcessCancelled:
        raise
    except Exception:
        return None


def lossless_caption_samples(plan: dict[str, Any], config: AppConfig, work_dir: Path, sample_dir: Path, times: list[float]) -> dict[str, list[Path]]:
    """Exercise the real composition graph without lossy encoder noise.

    Lossless PNG sets measure isolation and the active halo independently of
    neighbouring white words. This is a real composition, not a mock.
    """
    fps = float(plan.get("frame_rate", {}).get("target_cfr", 30))
    frame_ids = sorted(set(max(0, int(time * fps)) for time in times))
    if not frame_ids:
        raise ValueError("No caption events available for A/B QA")
    sample_dir.mkdir(parents=True, exist_ok=True)
    ass_lines = (work_dir / "captions.ass").read_text(encoding="utf-8").splitlines()
    active_lines = []
    baseline_lines = []
    style=config.get("craft","caption_mode",default="hormozi_glow")
    active_rgb=config.get("captions","base" if style=="gravitas" else "active").lstrip("#")
    active_bgr=int(active_rgb[4:6]+active_rgb[2:4]+active_rgb[:2],16)
    def active_colour(match):
        visible=(int(match.group(1),16)&0xffffff)==active_bgr
        return match.group(0)+(r"\alpha&H00&" if visible else r"\alpha&HFF&")
    for line in ass_lines:
        if not line.startswith("Dialogue:") or line.startswith("Dialogue: -1,"):
            baseline_lines.append(line)
        if not line.startswith("Dialogue:"):
            active_lines.append(line)
        elif line.startswith("Dialogue: -1,"):
            active_lines.append(line)
        elif line.startswith("Dialogue: 2,"):
            # Derive the expected active glyph from the text layer, even when
            # glow is missing or disabled. Preserve invisible neighbours' text
            # advances so multiword layout/pop stays identical.
            line=line.replace(",,{",r",,{\bord0\blur0\shad0\alpha&HFF&",1)
            line=re.sub(r"\\c&H([0-9A-Fa-f]{6,8})&",active_colour,line)
            active_lines.append(line)
    active_ass = sample_dir / "active_fill.ass"
    active_ass.write_text("\n".join(active_lines) + "\n", encoding="utf-8")
    baseline_ass=sample_dir/"baseline.ass"
    baseline_ass.write_text("\n".join(baseline_lines)+"\n",encoding="utf-8")
    no_glow_ass=sample_dir/"no_glow.ass"
    no_glow_ass.write_text("\n".join(line for line in ass_lines if not line.startswith(("Dialogue: 0,","Dialogue: 1,")))+"\n",encoding="utf-8")
    expression = "+".join(f"eq(n\\,{index})" for index in frame_ids)
    graph = _filter_script(plan, config, work_dir, False)
    source = Path(plan["source"]["path"])
    moving = needs_subpixel(plan,config)
    if moving:
        source = work_dir / "moving_feed.mkv"
        graph = _filter_script(plan, config, work_dir, False, video_is_feed=True)
    seek = [] if moving else ["-ss", str(plan["trim"]["start"])]
    paths = {}
    fast_glow=config.get("captions","glow","method",default="ass_layers")=="fast_glow" and config.get("craft","caption_mode",default="hormozi_glow")=="hormozi_glow"
    if fast_glow:
        from .core.config import _deep_merge
        no_fast=AppConfig(_deep_merge(config.json(),{"captions":{"glow":{"method":"ass_layers"}}}),config.path)
        bare_graph=_filter_script(plan,no_fast,work_dir,False,video_is_feed=moving)
    variants=("captions","baseline","active_fill","no_glow") if config.get("craft","caption_mode",default="hormozi_glow")=="hormozi_glow" else ("captions","baseline","active_fill")
    for variant in variants:
        target_graph = graph
        if fast_glow and variant!="captions":
            target_graph=bare_graph
        if variant == "baseline":
            target_graph = target_graph.replace("subtitles=captions.ass:",f"subtitles={_relative(baseline_ass,work_dir)}:")
        elif variant == "active_fill":
            target_graph = target_graph.replace("subtitles=captions.ass:", f"subtitles={_relative(active_ass, work_dir)}:")
        elif variant == "no_glow":
            target_graph = target_graph.replace("subtitles=captions.ass:",f"subtitles={_relative(no_glow_ass,work_dir)}:")
        target_graph = target_graph.replace("[outv]", f"[composed];[composed]select={expression}[outv]")
        script = sample_dir / f"{variant}.graph"
        script.write_text(target_graph, encoding="utf-8")
        output_template = sample_dir / f"{variant}_%03d.png"
        args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *seek, "-i", _relative(source, work_dir), "-loop", "1", "-i", "chrome.png", "-loop", "1", "-i", "craft.png", "-loop", "1", "-i", "extras.png", "-loop", "1", "-i", "evidence.png", *filter_script_args(_relative(script,work_dir)), "-map", "[outv]", "-an", "-frames:v", str(len(frame_ids)), "-fps_mode", "vfr", "-c:v", "png", _relative(output_template, work_dir)]
        run_process(args, cwd=work_dir, timeout=max(120, float(plan["trim"]["duration"]) * 10))
        paths[variant] = sorted(sample_dir.glob(f"{variant}_*.png"))
        if len(paths[variant]) != len(frame_ids):
            raise RuntimeError(f"Lossless {variant} sample count mismatch")
    return paths


def _encoder_segment(config: AppConfig, encoder: str) -> list[str]:
    """ffmpeg args for one output encoder at the configured quality.

    Quality mapping from the measured encoder test on this machine
    (30 s of real 1080x1920 output): x264 crf 18 ~= QSV ICQ 19 ~=
    NVENC CQ 19 by SSIM, so both hardware encoders use crf + 1.
    """
    crf = int(config.get("output", "crf", default=18))
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf + 1), "-pix_fmt", "nv12"]
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", str(crf + 1), "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", str(config.get("output", "preset", default="medium")), "-crf", str(crf), "-pix_fmt", "yuv420p"]


def _configured_encoder(config: AppConfig) -> str:
    encoder = str(config.get("output", "encoder", default="libx264"))
    return encoder if encoder in ("h264_qsv", "h264_nvenc") else "libx264"


def _video_encode_args(config: AppConfig) -> list[str]:
    return _encoder_segment(config, _configured_encoder(config))


def _with_encoder(args: list[str], config: AppConfig, encoder: str) -> list[str]:
    """Copy of ffmpeg args with the video-encoder segment replaced."""
    args = list(args)
    start = args.index("-c:v")
    end = len(args)
    for marker in ("-c:a", "-movflags", "-shortest"):
        if marker in args[start:]:
            end = min(end, args.index(marker, start))
    return args[:start] + _encoder_segment(config, encoder) + args[end:]


def render(plan: dict[str, Any], config: AppConfig, work_dir: Path, output_path: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    from .contracts import validate_render_plan
    validate_render_plan(plan)
    from .layout import validate_layout
    if not validate_layout(config).passed:
        raise ValueError("Layout invariants failed")
    if plan.get("source_spans"):
        from .timeline import prepare_edited_source, runtime_plan
        plan = runtime_plan(plan, prepare_edited_source(plan, work_dir))
        atomic_write_json(work_dir / "runtime_plan.json", plan)
    source = Path(plan["source"]["path"])
    probe = ffprobe(source)
    has_audio = any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))
    chrome_path = work_dir / "chrome.png"
    craft_path = work_dir / "craft.png"
    extras_path = work_dir / "extras.png"
    ass_path = work_dir / "captions.ass"
    render_chrome(config, plan.get("headline", ""), chrome_path)
    build_craft_ass(plan, config, work_dir / "craft.ass")
    if plan.get("debug_overlay"):
        from .captions import ass_time
        feed=config.regions["feed"]
        header=f"[Script Info]\nScriptType: v4.00+\nPlayResX: {feed['w']}\nPlayResY: {feed['h']}\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: D,Poppins SemiBold,22,&H000000FF,&H000000FF,&H000000FF,&HFF000000,-1,0,0,0,100,100,0,0,1,2,0,7,0,0,0,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        debug=[header]
        for x,y,w,h in plan.get("caption_exclusions",[]):
            debug.append(f"Dialogue: 0,0:00:00.00,{ass_time(plan['trim']['duration'])},D,,0,0,0,,{{\\pos({x},{y-feed['y']})\\p1\\1a&HFF&}}m 0 0 l {w} 0 {w} {h} 0 {h} 0 0\n")
        debug.append(f"Dialogue: 1,0:00:00.00,{ass_time(plan['trim']['duration'])},D,,0,0,0,,{{\\pos(20,20)}}{plan['framing']['segments'][0]['mode']} · {','.join(plan['framing']['segments'][0].get('reasons',[]))}\n")
        (work_dir/"debug.ass").write_text("".join(debug),encoding="utf-8")
    render_craft_overlay(plan, config, craft_path, kind="question_chip")
    render_craft_overlay(plan, config, work_dir / "evidence.png", kind="evidence_card")
    source_meta = plan.get("source", {}).get("meta", {}) or {}
    source_label = source_meta.get("channel") or source_meta.get("title") or str(plan.get("source", {}).get("path", "")).split("/")[-1]
    render_extras(config, extras_path, str(source_label))
    # The transcript is stored in the plan by the CLI; callers may also provide a ready ASS.
    transcript = plan.get("transcript", {"segments": []})
    user_disabled=bool(config.get("captions","user_disabled",default=False))
    suppress=bool(plan.get("source_text_policy",{}).get("source_has_captions") and config.get("source_text","trust_source_captions",default=False)) or user_disabled
    build_captions(transcript, float(plan["trim"]["start"]), float(plan["trim"]["end"]), config, ass_path, exclusions=plan.get("caption_exclusions"),suppress=suppress,suppress_reason="Captions turned off for this clip by the user" if user_disabled else "Explicit user trust_source_captions setting; source text accuracy is unverified")
    if config.get("captions","glow","method",default="ass_layers")=="fast_glow":
        lines=ass_path.read_text(encoding="utf-8").splitlines()
        lite=[line for line in lines if not line.startswith(("Dialogue: 0,","Dialogue: 1,"))]
        active=[]
        for line in lines:
            if not line.startswith("Dialogue:"): active.append(line)
            elif line.startswith("Dialogue: 0,"):
                line=re.sub(r"\\bord[0-9.]+",r"\\bord0",line)
                line=re.sub(r"\\blur[0-9.]+",r"\\blur0",line)
                line=re.sub(r"\\alpha&H(?!FF)[0-9A-Fa-f]{2}&",r"\\alpha&H00&",line)
                active.append(line)
        (work_dir/"captions_lite.ass").write_text("\n".join(lite)+"\n",encoding="utf-8")
        (work_dir/"active_fill.ass").write_text("\n".join(active)+"\n",encoding="utf-8")
    plan["artifact_hashes"]={"chrome":content_hash(chrome_path),"captions":content_hash(ass_path),"framing":content_hash(plan["framing"]),"config":config.hash()}
    atomic_write_json(work_dir/"render_artifacts.json",{"schema_version":5,"plan_hash":plan["plan_hash"],"hashes":plan["artifact_hashes"]})
    atomic_write_json(work_dir/"renderer_config.json",{"schema_version":5,"config":config.json(),"config_hash":config.hash()})
    loudnorm_stats = _measure_loudnorm(source, plan, config) if has_audio else None
    script_path = work_dir / "render.graph"
    moving = needs_subpixel(plan,config)
    moving_feed = work_dir / "moving_feed.mkv"
    if moving:
        render_subpixel_feed(source, plan, config, moving_feed)
    video_input = 0
    audio_input = 0
    script_path.write_text(_filter_script(plan, config, work_dir, has_audio, video_input=video_input, audio_input=audio_input, video_is_feed=moving, loudnorm_stats=loudnorm_stats), encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".part")
    try:
        partial.unlink()
    except FileNotFoundError:
        pass
    video_input_path = moving_feed if moving else source
    seek = [] if moving else ["-ss", str(plan["trim"]["start"])]
    args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *seek, "-i", _relative(video_input_path, work_dir), "-loop", "1", "-i", "chrome.png", "-loop", "1", "-i", "craft.png", "-loop", "1", "-i", "extras.png", "-loop", "1", "-i", "evidence.png"]
    if moving and has_audio:
        args += ["-ss", str(plan["trim"]["start"]), "-i", _relative(source, work_dir)]
        script_path.write_text(_filter_script(plan, config, work_dir, has_audio, video_input=0, audio_input=5, video_is_feed=True, loudnorm_stats=loudnorm_stats), encoding="utf-8")
    graph_args=filter_script_args("render.graph")
    args += [*graph_args, "-map", "[outv]"]
    if has_audio:
        args += ["-map", "[outa]", "-c:a", "aac", "-b:a", f"{int(config.get('output', 'audio_kbps', default=160))}k"]
    optional_audio=[]
    audio_input_count=6 if moving and has_audio else 5
    music_file=config.get("audio","music_file")
    sfx_file=config.get("audio","sfx_file")
    if music_file or sfx_file:
        if not has_audio: raise ValueError("Optional music/SFX needs a source audio track")
        graph=script_path.read_text(encoding="utf-8").replace("[outa]","[speech]")
        speech="speech"
        inputs=[]
        if music_file:
            if not config.get("audio","music_licensed",default=False): raise ValueError("Music requires a recorded user licence attestation")
            music_path=Path(music_file)
            if not music_path.is_file(): raise ValueError("Music file absent")
            inputs += ["-stream_loop","-1","-i",str(music_path.resolve())]
            gain=float(config.get("audio","music_gain",default=.06))
            graph+=f"[{audio_input_count}:a]atrim=duration={plan['trim']['duration']},asetpts=PTS-STARTPTS,volume={gain}[music];[speech]asplit[side][voice];[music][side]sidechaincompress=threshold=0.03:ratio=8:attack=10:release=250[ducked];[voice][ducked]amix=inputs=2:normalize=0[mixed];\n"
            speech="mixed"
            audio_input_count+=1
        if sfx_file:
            if not config.get("audio","sfx_licensed",default=False): raise ValueError("SFX requires a recorded licence attestation")
            if not Path(sfx_file).is_file(): raise ValueError("SFX file absent")
            inputs += ["-i",str(Path(sfx_file).resolve())]
            graph+=f"[{audio_input_count}:a]volume=0.1,apad,atrim=duration={plan['trim']['duration']}[sfx];[{speech}][sfx]amix=inputs=2:normalize=0[sfxmixed];\n"
            speech="sfxmixed"
        graph+=f"[{speech}]alimiter=limit=0.8:level=false:latency=true,aresample={config.get('output','audio_hz',default=48000)}[outa];\n"
        script_path.write_text(graph,encoding="utf-8")
        filter_index=args.index(graph_args[0])
        args[filter_index:filter_index]=inputs
    args += _video_encode_args(config) + ["-movflags", "+faststart", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-shortest", "-f", "mp4", _relative(partial, work_dir)]
    if plan.get("cache_variants"):
        base = work_dir / "variant_base.mkv"
        base_args = args[:args.index("-c:v")] + ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p", "-shortest", "-f", "matroska", base.name]
        if has_audio:
            audio_index = base_args.index("-c:a")
            base_args[audio_index+1] = "pcm_s16le"
            kbps = base_args.index("-b:a")
            del base_args[kbps:kbps+2]
        run_process(base_args, cwd=work_dir, timeout=max(120, int(plan["trim"]["duration"] * 20)))
        args = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", base.name, *_video_encode_args(config), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-f", "mp4", _relative(partial, work_dir)]
    encoder_used = _configured_encoder(config)
    try:
        run_process(args, cwd=work_dir, timeout=max(120, int(plan["trim"]["duration"] * 20)))
    except Exception:
        if encoder_used == "libx264":
            raise
        # A configured hardware encoder must never break an export:
        # retry once with the always-available software encoder.
        encoder_used = "libx264 (fallback)"
        run_process(_with_encoder(args, config, "libx264"), cwd=work_dir, timeout=max(120, int(plan["trim"]["duration"] * 20)))
    if not partial.exists() or partial.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce an output")
    os.replace(partial, output_path)
    return {"schema_version": 5, "status": "rendered", "output": str(output_path), "output_sha256": content_hash(output_path), "plan_hash": plan["plan_hash"], "encoder": encoder_used, "chrome": str(chrome_path), "captions": str(ass_path), "craft": str(craft_path), "extras": str(extras_path), "has_audio": has_audio}
