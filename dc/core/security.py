from __future__ import annotations

import html
import re
import secrets
from urllib.parse import urlparse
from pathlib import Path


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def escape_text(value: object) -> str:
    return html.escape(str(value), quote=True)


def new_token(byte_count: int = 24) -> str:
    return secrets.token_urlsafe(byte_count)


def validate_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value) or ".." in value or value.endswith(".") or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        raise ValueError("Invalid resource id")
    return value


def safe_child(root: Path, resource_id: str, suffix: str = "") -> Path:
    validate_id(resource_id)
    if Path(resource_id).drive or Path(resource_id).name != resource_id or ".." in Path(resource_id).parts:
        raise ValueError("Unsafe resource path")
    result = (root / f"{resource_id}{suffix}").resolve()
    root_resolved = root.resolve()
    if result != root_resolved and root_resolved not in result.parents:
        raise ValueError("Path escapes resource root")
    return result


def origin_is_local(origin: str | None, host: str | None = None, allow_lan: bool = False) -> bool:
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(host and parsed.netloc.lower() == host.lower())
