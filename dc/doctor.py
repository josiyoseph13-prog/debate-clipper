from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from importlib import metadata
from pathlib import Path
from typing import Any

from .core.config import ROOT, load_config, load_safe_zones
from .core.process import run_process
from .core.tools import find_tool
from .core.hashing import file_hash
from .captions import calibrate_caption
from .audio import probe_frame_rate


def run_doctor() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        config = load_config()
        checks.append({"name": "config_schema", "status": "pass", "value": config.schema_version})
    except Exception as exc:
        config = None
        checks.append({"name": "config_schema", "status": "fail", "value": str(exc)})
    checks.append({"name": "python", "status": "pass" if sys.version_info >= (3, 11) else "warn", "value": sys.version.split()[0], "threshold": "3.11+"})
    for tool in ("ffmpeg", "ffprobe"):
        path = find_tool(tool)
        if path:
            try:
                output = run_process([path, "-version"], timeout=10, output_limit=16000)
                capabilities = {"libass": "--enable-libass" in output, "harfbuzz": "harfbuzz" in output.lower(), "x264": "libx264" in output}
                checks.append({"name": tool, "status": "pass" if all(capabilities.values()) else "warn", "value": output.splitlines()[0] if output else path, "path": path, "capabilities": capabilities, "message": "full libass/HarfBuzz/x264 capability not confirmed" if not all(capabilities.values()) else "required render capabilities found"})
            except Exception as exc:
                checks.append({"name": tool, "status": "fail", "value": str(exc)})
        else:
            checks.append({"name": tool, "status": "warn", "value": "not found; render unavailable"})
    for module in ("PIL", "numpy", "cv2", "fastapi", "typer", "faster_whisper", "sherpa_onnx"):
        checks.append({"name": f"python:{module}", "status": "pass" if importlib.util.find_spec(module) else "warn", "value": module})
    if config:
        badge = config.get("header", "badge", "mode", default="brand_check")
        checks.append({"name": "badge_mode", "status": "warn" if badge == "platform_style" else "pass", "value": badge, "message": "platform-style badge requires a truly verified account" if badge == "platform_style" else "brand-safe badge"})
        checks.append({"name": "safe_zone_verified", "status": "warn" if any(item.get("verified_on") is None for item in load_safe_zones().values()) else "pass", "value": "unverified profiles are conservative"})
        logo = ROOT / config.get("header", "logo", "file", default="assets/logo.png")
        wordmark=ROOT/config.get("header","wordmark","file",default="assets/wordmark.png")
        checks.append({"name": "logo_asset", "status": "pass" if logo.is_file() else "warn", "value": str(logo), "sha256":file_hash(logo) if logo.is_file() else None,"message":"supplied artwork found; original image retained" if logo.is_file() else "logo absent; fallback used"})
        checks.append({"name":"wordmark_asset","status":"pass" if wordmark.is_file() else "warn","value":str(wordmark),"message":"separate wordmark found" if wordmark.is_file() else "Separate horizontal wordmark absent; live-font fallback is not an exact asset match"})
        font_files = [config.get("captions", "font_file", default="assets/fonts/Poppins-ExtraBold.ttf"), config.get("header", "handle", "font", default="assets/fonts/Poppins-Regular.ttf"), "assets/fonts/NotoColorEmoji.ttf"]
        for font_file in font_files:
            font_path = ROOT / font_file
            checks.append({"name": f"font:{font_path.name}", "status": "pass" if font_path.exists() else "warn", "value": str(font_path), "message": "configured font is absent; compatibility fallback will be used" if not font_path.exists() else "font file found"})
        if importlib.util.find_spec("PIL"):
            try:
                from PIL import ImageFont

                emoji_font = ROOT / "assets/fonts/NotoColorEmoji.ttf"
                if emoji_font.exists():
                    from .chrome import emoji_image
                    from .core.hashing import content_hash
                    glyph=emoji_image("🎓",55,config)
                    checks.append({"name": "emoji_glyph", "status": "pass", "value": "🎓","method":"RGBA raster differs from missing-glyph bitmap","bitmap_sha256":content_hash(glyph.tobytes())})
                else:
                    checks.append({"name": "emoji_glyph", "status": "warn", "value": "font absent"})
            except Exception as exc:
                checks.append({"name": "emoji_glyph", "status": "warn", "value": str(exc)})
    checks.append({"name": "path_with_spaces", "status": "pass" if " " in str(ROOT) and os.access(ROOT, os.W_OK) else "warn", "value": str(ROOT)})
    try:
        (ROOT / "work").mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="doctor_", suffix=".tmp", dir=ROOT / "work", delete=True) as handle:
            handle.write(b"write-access")
            handle.flush()
        checks.append({"name": "write_access", "status": "pass", "value": str(ROOT / "work")})
    except OSError as exc:
        checks.append({"name": "write_access", "status": "fail", "value": str(exc)})
    usage = shutil.disk_usage(ROOT)
    checks.append({"name": "free_disk", "status": "pass" if usage.free > 1024 * 1024 * 1024 else "warn", "value_bytes": usage.free, "threshold_bytes": 1024 * 1024 * 1024})
    model_dir = ROOT / "assets" / "models"
    model_files = [path for path in model_dir.rglob("*") if path.is_file() and path.suffix.lower() not in {".json",".md",".txt"}] if model_dir.exists() else []
    hashes = []
    for model in model_files:
        digest = file_hash(model)
        hashes.append({"path": str(model.relative_to(ROOT)), "sha256": digest})
    models_doc = (ROOT / "MODELS.md").read_text(encoding="utf-8") if (ROOT / "MODELS.md").exists() else ""
    hashes_recorded = bool(model_files) and all(item["sha256"] in models_doc for item in hashes)
    checks.append({"name": "offline_models", "status": "pass" if model_files and hashes_recorded else "warn", "value": hashes, "message": "optional model weights are absent; CPU/heuristic fallbacks remain active" if not model_files else ("model hashes verified" if hashes_recorded else "model hashes must be recorded in MODELS.md")})
    checks.append({"name": "requirements_lock", "status": "pass" if (ROOT / "requirements.lock").exists() else "fail", "value": str(ROOT / "requirements.lock")})
    lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8") if (ROOT / "requirements.lock").exists() else ""
    checks.append({"name": "requirements_hashes", "status": "pass" if "--hash=" in lock_text else "warn", "value": "hashes present" if "--hash=" in lock_text else "version pins only"})
    checks.append({"name": "model_licence_table", "status": "pass" if (ROOT / "MODELS.md").exists() else "warn", "value": str(ROOT / "MODELS.md")})
    from .core.io import read_json
    registry=read_json(model_dir/"registry.json",{}) or {}
    for name in registry.get("models",{}):
        try:
            from .models import model_spec
            registered=model_spec(name)
            checks.append({"name":"model_registry:"+name,"status":"pass","value":registered["license"]})
        except (ValueError,RuntimeError) as exc:
            optional_missing = (
                isinstance(exc, ValueError)
                and str(exc).startswith("Missing or escaping model file")
                and registry.get("models", {}).get(name, {}).get("default_enabled") is False
            )
            if optional_missing:
                checks.append({"name":"model_registry:"+name,"status":"warn","value":str(exc),"message":"optional model not installed; it is disabled by default and nothing downloads implicitly"})
            else:
                checks.append({"name":"model_registry:"+name,"status":"fail","value":str(exc)})
    if config:
        calibration = ROOT / "config" / "caption_calibration.json"
        calibration_result = calibrate_caption(config, calibration)
        checks.append({"name": "caption_calibration", "status": "pass" if calibration_result.get("status") == "calibrated" else "warn", "value": calibration_result.get("status"), "message": "Measured libass fill" if calibration_result.get("status") == "calibrated" else "Reference calibration not established", "path": str(calibration)})
    try:
        ytdlp_version = metadata.version("yt-dlp")
        lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8") if (ROOT / "requirements.lock").exists() else ""
        pinned = f"yt-dlp=={ytdlp_version}" in lock_text
        checks.append({"name": "yt_dlp_pin", "status": "pass" if pinned else "warn", "value": ytdlp_version, "message": "version is pinned" if pinned else "installed version differs from requirements.lock"})
    except metadata.PackageNotFoundError:
        checks.append({"name": "yt_dlp_pin", "status": "warn", "value": "yt-dlp not installed"})
    input_files = sorted((ROOT / "input").glob("*")) if (ROOT / "input").exists() else []
    sample = next((path for path in input_files if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}), None)
    if sample and find_tool("ffprobe"):
        try:
            probe = json.loads(run_process([find_tool("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", sample], timeout=30))
            fps = probe_frame_rate(probe)
            checks.append({"name": "vfr_probe_sample", "status": "pass", "value": fps, "path": str(sample)})
        except Exception as exc:
            checks.append({"name": "vfr_probe_sample", "status": "warn", "value": str(exc)})
    else:
        checks.append({"name": "vfr_probe_sample", "status": "warn", "value": "no local sample or ffprobe"})
    checks.append({"name": "studio_bind", "status": "pass" if not config or config.get("security", "bind", default="127.0.0.1") == "127.0.0.1" else "fail", "value": config.get("security", "bind", default="127.0.0.1") if config else None})
    checks.append({"name": "keyring", "status": "pass" if importlib.util.find_spec("keyring") else "warn", "value": "optional until API publisher is enabled"})
    return {"schema_version": 5, "status": "fail" if any(check["status"] == "fail" for check in checks) else ("warn" if any(check["status"] == "warn" for check in checks) else "pass"), "checks": checks}


def print_doctor(report: dict[str, Any]) -> None:
    print(json.dumps(report, indent=2, ensure_ascii=False))
