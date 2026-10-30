"""Pipeline tests against the local fixture server (no live net)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from conftest import collect, run_cli


def test_article_ok_with_metadata(server, tmp_path):
    summary, records = collect(server, tmp_path, ["/article"])
    assert summary["by_status"] == {"ok": 1}
    rec = records[0]
    assert rec["title"] == "Fixture Article"
    assert rec["date_published"] == "2026-09-15"
    assert rec["extractor"] == "trafilatura"
    assert rec["text_chars"] >= 200
    assert "site navigation junk" not in rec["text"]


def test_exports_are_valid(server, tmp_path):
    summary, records = collect(server, tmp_path, ["/article", "/gone"])
    outdir = tmp_path / "out"
    rows = list(csv.DictReader(open(outdir / "records.csv")))
    assert len(rows) == 2 and rows[0]["status"] == "ok"
    assert rows[1]["status"] == "http_error"
    lines = (outdir / "records.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["url"].endswith("/article")


def test_duplicate_url_canonical(server, tmp_path):
    summary, records = collect(
        server, tmp_path,
        ["/article", "/article?utm_source=newsletter", "/article/"])
    statuses = [r["status"] for r in records]
    assert statuses[0] == "ok"
    assert statuses.count("duplicate_url") == 2
    assert summary["duplicates_skipped"] == 2


def test_duplicate_content(server, tmp_path):
    _, records = collect(server, tmp_path, ["/article", "/mirror"])
    assert [r["status"] for r in records] == ["ok", "duplicate_content"]


def test_robots_denied_and_never_fetched(server, tmp_path, request_log):
    before = len(request_log)
    _, records = collect(server, tmp_path, ["/private/secret"])
    assert records[0]["status"] == "robots_denied"
    new_requests = request_log[before:]
    assert not any("/private" in p for p in new_requests)


def test_missing_metadata_still_ok(server, tmp_path):
    _, records = collect(server, tmp_path, ["/nometa"])
    assert records[0]["status"] == "ok"
    assert records[0]["date_published"] is None


def test_malformed_page_no_crash(server, tmp_path):
    _, records = collect(server, tmp_path, ["/malformed"])
    assert len(records) == 1
    assert records[0]["status"] in ("ok", "extract_short")


def test_short_page_reported(server, tmp_path):
    _, records = collect(server, tmp_path, ["/plain"])
    assert records[0]["status"] == "extract_short"


def test_network_failure_recorded(tmp_path):
    urls = tmp_path / "urls.txt"
    urls.write_text("http://127.0.0.1:9/unreachable\n")
    code, payload = run_cli("collect", "--urls", str(urls),
                            "--outdir", str(tmp_path / "o"), "--delay", "0")
    assert payload["ok"] is True  # the run succeeds; the URL is a record
    rec = json.loads((tmp_path / "o" / "records.jsonl").read_text().splitlines()[0])
    assert rec["status"] == "network_error" and rec["error"]
