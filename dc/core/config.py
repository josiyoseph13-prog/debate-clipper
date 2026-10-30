from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "political_lens.json"


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@dataclass(frozen=True)
class AppConfig:
    data: dict[str, Any]
    path: Path = CONFIG_PATH

    @property
    def schema_version(self) -> int:
        return int(self.data.get("schema_version", 0))

    @property
    def canvas(self) -> dict[str, int]:
        return self.data["canvas"]

    @property
    def regions(self) -> dict[str, dict[str, int]]:
        return self.data["regions"]

    def get(self, *keys: str, default: Any = None) -> Any:
        value: Any = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def json(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def hash(self) -> str:
        from .hashing import content_hash

        return content_hash(self.data)


def load_config(path: Path | str | None = None, overrides: dict[str, Any] | None = None) -> AppConfig:
    config_path = Path(path) if path else CONFIG_PATH
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if overrides:
        data = _deep_merge(data, overrides)
    validate_config(data)
    return AppConfig(data, config_path)


def load_preset(name: str = "political_lens") -> AppConfig:
    """Load a named brand preset without hard-coding a second renderer."""
    from .security import validate_id
    validate_id(name)
    preset_path = CONFIG_DIR / "presets" / f"{name}.json"
    if not preset_path.exists():
        raise ValueError(f"Unknown brand preset: {name}")
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    target = preset.get("config")
    if target:
        target_path = ROOT / target
        base = json.loads(target_path.read_text(encoding="utf-8"))
        overrides = preset.get("overrides", {})
        if overrides:
            base = _deep_merge(base, overrides)
        validate_config(base)
        return AppConfig(base, target_path)
    return load_config(preset_path)


def validate_config(data: dict[str, Any]) -> None:
    required = ("schema_version", "canvas", "regions", "header", "captions", "output")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Config missing required sections: {', '.join(missing)}")
    canvas = data["canvas"]
    if int(canvas.get("w", 0)) <= 0 or int(canvas.get("h", 0)) <= 0:
        raise ValueError("Canvas dimensions must be positive")
    regions = data["regions"]
    for name in ("header", "hook", "feed", "bottom_white"):
        if name not in regions:
            raise ValueError(f"Config missing region: {name}")
    feed = regions["feed"]
    bottom = regions["bottom_white"]
    if int(feed["y"]) + int(feed["h"]) + int(bottom["h"]) != int(canvas["h"]):
        raise ValueError("Feed and bottom band do not fill the canvas")
    target_ratio = float(data.get("reference_feed_ratio", int(feed["w"]) / int(feed["h"])))
    if abs((int(feed["w"]) / int(feed["h"])) - target_ratio) > 0.002:
        raise ValueError("Feed aspect ratio is outside the PL-2 tolerance")
    if data["header"]["badge"].get("mode") not in {"brand_check", "platform_style", "none"}:
        raise ValueError("Unsupported badge mode")


def load_safe_zones() -> dict[str, dict[str, Any]]:
    path = CONFIG_DIR / "safe_zones.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_config(name: str, default: Any) -> Any:
    path = CONFIG_DIR / name
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)
