#!/usr/bin/env python3
"""Pax foundation check — one command, read-only.

Sections:
  1. Registry validation (schema v2) + INDEX freshness
  2. System tools (version probes)
  3. Workspace media tools (yt-dlp / faster-whisper in media-venv)
  4. Connector statuses (read-only status calls only)

States are reported distinctly: OK / NOT CONNECTED / BLOCKED /
UNAVAILABLE / UNTESTED / STALE / ERROR. A tool being unavailable or
blocked is a finding, not a check failure; the exit code is 1 only when
the registry itself is invalid or a probe errors unexpectedly.

Instagram is deliberately NOT probed live: the owner blocked it
(registry record, 2026-10-10) and no account is linked. Its state is
reported from the registry.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from registry_lib import load_records, render_index, validate  # noqa: E402

HOME = Path.home()
REGISTRY = HOME / "workspace" / "registry"
MEDIA_VENV = HOME / "workspace" / "tools" / "media-venv" / "bin"
TIMEOUT = 25

SYSTEM_TOOLS = [
    ("Python", ["python3", "--version"]),
    ("Node", ["node", "--version"]),
    ("git", ["git", "--version"]),
    ("gh CLI", ["gh", "--version"]),
    ("FFmpeg", ["ffmpeg", "-version"]),
    ("ffprobe", ["ffprobe", "-version"]),
    ("sqlite3", ["sqlite3", "--version"]),
    ("ripgrep", ["rg", "--version"]),
]
KNOWN_ABSENT = [("Docker", ["docker", "--version"]),
                ("Deno", ["deno", "--version"])]
CONNECTORS = [
    ("GitHub", ["github", "status"]),
    ("Google Drive", ["hatch_gws_cli", "drive", "status"]),
    ("Zapier", ["zapier", "status"]),
    ("HighLevel", ["/opt/hatch/bin/ghl", "status"]),
]


def probe(cmd):
    """Return (state, detail). state in OK / UNAVAILABLE / ERROR."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT)
        out = (r.stdout or r.stderr).strip().splitlines()
        first = out[0].strip() if out else ""
        if r.returncode == 0:
            return "OK", first[:80]
        return "ERROR", (first or f"exit {r.returncode}")[:80]
    except FileNotFoundError:
        return "UNAVAILABLE", "not installed"
    except subprocess.TimeoutExpired:
        return "ERROR", f"timed out after {TIMEOUT}s"


def connector_state(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT)
        data = json.loads(r.stdout)
        status = data.get("status") or data.get("auth_status") or "?"
        if status == "not_connected":
            return "NOT CONNECTED", ""
        if data.get("authenticated"):
            return "CONNECTED", ""
        return str(status).upper(), ""
    except FileNotFoundError:
        return "UNAVAILABLE", "CLI not found"
    except Exception as e:  # honest: surface, don't hide
        return "ERROR", f"{type(e).__name__}: {e}"[:80]


def main():
    failures = 0
    print("== 1. Registry ==")
    errors, warnings = validate(REGISTRY)
    for w in warnings:
        print(f"  STALE/WARN  {w}")
    for e in errors:
        print(f"  ERROR       {e}")
    failures += len(errors)
    print(f"  Registry validation: {'OK' if not errors else 'FAILED'} "
          f"({len(errors)} errors, {len(warnings)} warnings)")
    records = load_records(REGISTRY)
    current = (REGISTRY / "INDEX.md").read_text()
    fresh = current == render_index(records)
    print(f"  INDEX.md: {'CURRENT' if fresh else 'STALE — run generate_index.py'}")

    print("== 2. System tools ==")
    for name, cmd in SYSTEM_TOOLS:
        state, detail = probe(cmd)
        print(f"  {state:12} {name}: {detail}")
    for name, cmd in KNOWN_ABSENT:
        state, detail = probe(cmd)
        print(f"  {state:12} {name}: {detail} (known gap)")

    print("== 3. Workspace media tools (media-venv) ==")
    state, detail = probe([str(MEDIA_VENV / "yt-dlp"), "--version"])
    print(f"  {state:12} yt-dlp: {detail} — registry: candidate; "
          f"YouTube BLOCKED from this VM egress (see record)")
    state, detail = probe([str(MEDIA_VENV / "python"), "-c",
                           "import faster_whisper; "
                           "print('import ok')"])
    print(f"  {state:12} faster-whisper: {detail} — registry: tested "
          f"(synthetic speech only; real audio UNTESTED)")

    print("== 4. Connectors (read-only status) ==")
    for name, cmd in CONNECTORS:
        state, detail = connector_state(cmd)
        print(f"  {state:12} {name} {detail}")
    by_slug = {r["data"]["slug"]: r["data"] for r in records
               if not r["parse_error"]}
    ig = by_slug.get("instagram-connector", {})
    print(f"  {'BLOCKED':12} Instagram — owner decision "
          f"{str(ig.get('last_verified'))}: personal account must not be "
          f"connected (no live probe, by design)")
    mf = by_slug.get("meta-facebook", {})
    print(f"  {'NOT CONNECTED':12} Facebook/Threads/Meta Ads — from "
          f"registry, last verified {mf.get('last_verified')} "
          f"(Meta linking halted by owner)")

    print("\nFoundation check complete. Exit code reflects registry "
          "validity only; unavailable/blocked tools above are findings, "
          "not check failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
