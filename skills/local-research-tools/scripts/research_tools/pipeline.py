"""collect — fetch a list of URLs politely, extract, dedupe, export.

Writes records.jsonl (full text) and records.csv (metadata) into the
output directory and returns a summary. Every input URL produces
exactly one record — failures are records too, never silent drops.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from .common import (canonicalize_url, content_hash, registered_domain)
from .extract import extract
from .fetch import Fetcher, require_http_url

_CSV_FIELDS = ["url", "canonical_url", "domain", "title",
               "date_published", "author", "collected_at", "status",
               "http_status", "extractor", "text_chars", "error"]


def collect(urls: list[str], outdir: Path, delay: float = 1.0,
            max_pages: int = 50) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(delay=delay)
    records: list[dict] = []
    seen_urls: dict[str, str] = {}
    seen_content: dict[str, str] = {}
    duplicates = 0
    try:
        for raw_url in urls[:max_pages]:
            url = require_http_url(raw_url)
            canonical = canonicalize_url(url)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            base = {"url": url, "canonical_url": canonical,
                    "domain": registered_domain(canonical),
                    "collected_at": now}
            if canonical in seen_urls:
                records.append({**base, "status": "duplicate_url",
                                "title": None, "date_published": None,
                                "author": None, "http_status": None,
                                "extractor": None, "text_chars": 0,
                                "text": "", "error":
                                f"same canonical URL as {seen_urls[canonical]}"})
                duplicates += 1
                continue
            seen_urls[canonical] = url
            got = fetcher.fetch(url)
            if got["status"] != "fetched":
                records.append({**base, "status": got["status"],
                                "title": None, "date_published": None,
                                "author": None,
                                "http_status": got["http_status"],
                                "extractor": None, "text_chars": 0,
                                "text": "", "error": got["error"]})
                continue
            fields, extractor = extract(got["text"], url)
            text = fields["text"] or ""
            digest = content_hash(text) if text else None
            if digest and digest in seen_content:
                records.append({**base, "status": "duplicate_content",
                                "title": fields["title"],
                                "date_published": fields["date_published"],
                                "author": fields["author"],
                                "http_status": got["http_status"],
                                "extractor": extractor, "text_chars": len(text),
                                "text": "", "error":
                                f"same content as {seen_content[digest]}"})
                duplicates += 1
                continue
            if digest:
                seen_content[digest] = url
            status = "ok" if len(text) >= 200 else "extract_short"
            records.append({**base, "status": status,
                            "title": fields["title"],
                            "date_published": fields["date_published"],
                            "author": fields["author"],
                            "http_status": got["http_status"],
                            "extractor": extractor,
                            "text_chars": len(text), "text": text,
                            "error": None if status == "ok" else
                            "extracted text under 200 chars"})
    finally:
        fetcher.close()

    jsonl_path = outdir / "records.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    csv_path = outdir / "records.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record.get(k) for k in _CSV_FIELDS})

    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    return {"records": len(records), "by_status": counts,
            "duplicates_skipped": duplicates,
            "jsonl": str(jsonl_path), "csv": str(csv_path)}


def read_urls_file(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
