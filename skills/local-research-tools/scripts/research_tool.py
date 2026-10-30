#!/usr/bin/env python3
"""research_tool — Pax's local web-research CLI.

Every command prints exactly one JSON object:
  {"ok": bool, "command": str, "data": {...} | null,
   "warnings": [str], "error": str | null, "timing_ms": int}

Commands:
  doctor                                  environment check
  collect --urls FILE --outdir DIR        polite fetch+extract+dedupe+export
  youtube-info <url-or-id> [--transcript] probe YT metadata/transcript

Safety contract (also in SKILL.md): robots.txt is always obeyed;
requests are rate-limited; no cookies, logins, or bypassing of
paywalls/CAPTCHAs/anti-bot controls; failures are reported as data.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_tools import pipeline, youtube_info  # noqa: E402
from research_tools.common import ResearchError  # noqa: E402


def _emit(ok: bool, command: str, data, warnings, error, started: float) -> int:
    print(json.dumps({
        "ok": ok, "command": command, "data": data, "warnings": warnings,
        "error": error,
        "timing_ms": int((time.monotonic() - started) * 1000),
    }, ensure_ascii=False, indent=2))
    return 0 if ok else (2 if error and "could not" in error else 3)


def _version(dist: str):
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def cmd_doctor(_args) -> tuple[dict, list[str]]:
    libs = {name: _version(name) for name in
            ["httpx", "beautifulsoup4", "trafilatura", "readability-lxml",
             "Scrapy", "feedparser", "tldextract", "youtube-transcript-api"]}
    ytdlp = youtube_info._find_ytdlp()
    core_ok = all(libs[k] for k in
                  ["httpx", "beautifulsoup4", "trafilatura", "tldextract"])
    data = {"libraries": libs, "yt_dlp": ytdlp,
            "core_ok": core_ok,
            "features": {
                "collect": core_ok,
                "article_extraction": libs["trafilatura"] is not None,
                "crawl_framework": libs["Scrapy"] is not None,
                "feed_discovery": libs["feedparser"] is not None,
                "youtube_probe": ytdlp is not None,
            }}
    warnings = []
    if not core_ok:
        warnings.append("core libraries missing — run from the research-venv")
    return data, warnings


def cmd_collect(args) -> tuple[dict, list[str]]:
    urls = pipeline.read_urls_file(args.urls)
    if not urls:
        raise ResearchError(f"no URLs found in {args.urls}")
    summary = pipeline.collect(urls, Path(args.outdir),
                               delay=args.delay, max_pages=args.max_pages)
    warnings = []
    failed = sum(v for k, v in summary["by_status"].items()
                 if k not in ("ok", "duplicate_url", "duplicate_content"))
    if failed:
        warnings.append(f"{failed} URL(s) did not yield content — "
                        "see per-record status/error in the exports")
    return summary, warnings


def cmd_youtube_info(args) -> tuple[dict, list[str]]:
    data = youtube_info.probe(args.target, args.transcript)
    warnings = []
    if data["metadata_status"] != "ok":
        warnings.append("metadata probe: " + data["metadata_status"])
    if args.transcript and data["transcript_status"] != "ok":
        warnings.append("transcript probe: " + data["transcript_status"])
    return data, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research_tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="environment check")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("collect", help="fetch+extract+dedupe+export URLs")
    p.add_argument("--urls", required=True, help="text file, one URL per line")
    p.add_argument("--outdir", required=True)
    p.add_argument("--delay", type=float, default=1.0,
                   help="seconds between requests to the same host")
    p.add_argument("--max-pages", type=int, default=50)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("youtube-info", help="probe YouTube metadata/transcript")
    p.add_argument("target", help="watch URL, youtu.be link, or bare video id")
    p.add_argument("--transcript", action="store_true")
    p.set_defaults(func=cmd_youtube_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    args = build_parser().parse_args(argv)
    try:
        data, warnings = args.func(args)
        return _emit(True, args.command, data, warnings, None, started)
    except ResearchError as exc:
        return _emit(False, args.command, None, [], str(exc), started)
    except Exception as exc:  # never leak a traceback
        return _emit(False, args.command, None, [],
                     f"unexpected {type(exc).__name__}: {exc}", started)


if __name__ == "__main__":
    raise SystemExit(main())
