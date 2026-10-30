from __future__ import annotations

import copy
from pathlib import Path

from .chrome import render_chrome
from .core.hashing import content_hash
from .core.io import atomic_write_json
from .core.process import run_process
from .core.tools import require_tool
from .selection import headline_fidelity
from .qa import validate_output


def render_variants(plan, qa_plan, candidate, config, job_dir: Path, maximum: int):
    base = job_dir / "variant_base.mkv"
    if not base.is_file():
        raise ValueError("Lossless variant base is absent")
    variants = []
    for index, headline in enumerate(candidate.get("hook", {}).get("headline_options", [])[:maximum]):
        if not headline_fidelity(headline, candidate.get("text", "")):
            continue
        folder = job_dir / "variants" / f"v{index+1}"
        folder.mkdir(parents=True, exist_ok=True)
        chrome = folder / "chrome.png"
        render_chrome(config, headline, chrome)
        output = folder / "clip.mp4"
        partial = folder / "clip.mp4.part"
        run_process([require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", base, "-loop", "1", "-i", chrome, "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", str(config.get("output", "crf", default=18)), "-preset", config.get("output", "preset", default="medium"), "-c:a", "aac", "-b:a", "160k", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-shortest", "-movflags", "+faststart", "-f", "mp4", partial], timeout=max(120, plan["trim"]["duration"]*15))
        partial.replace(output)
        variant_plan = copy.deepcopy(qa_plan)
        variant_plan.update({"headline": headline, "chrome_png": str(chrome), "variant_id": f"v{index+1}"})
        variant_plan["plan_hash"] = content_hash({key:value for key,value in variant_plan.items() if key != "plan_hash"})
        report = validate_output(output, variant_plan, config, folder / "export_report.json")
        atomic_write_json(folder / "render_plan.json", variant_plan)
        variants.append({"variant_id": f"v{index+1}", "headline": headline, "output": str(output), "status": report["status"], "base": "lossless_ffv1", "generation_loss": "one_final_h264_encode"})
    return variants
