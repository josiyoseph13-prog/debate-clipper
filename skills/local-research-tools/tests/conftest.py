"""Fixtures: a local HTTP server with controlled test pages.

No test touches the live internet. The server logs every request
path so tests can prove robots-denied pages were never fetched.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parent.parent
CLI = SKILL_ROOT / "scripts" / "research_tool.py"

ARTICLE_BODY = (
    "This is the body of a test article about debates and public "
    "argument in modern democracies. " * 8
    + "A second paragraph develops the discussion with considerably "
    "more substantive detail about rhetoric and evidence. " * 8)

ARTICLE = f"""<html><head><title>Fixture Article</title>
<meta property="article:published_time" content="2026-09-15T10:30:00Z">
</head><body><nav>site navigation junk</nav><article>
<h1>Fixture Article</h1><p>{ARTICLE_BODY}</p></article>
<footer>copyright junk</footer></body></html>"""

ARTICLE_NOMETA = f"""<html><head><title>No Meta Article</title></head>
<body><article><h1>No Meta Article</h1><p>{ARTICLE_BODY}</p>
</article></body></html>"""

PAGES = {
    "/robots.txt": (200, "text/plain",
                    "User-agent: *\nDisallow: /private\n"),
    "/article": (200, "text/html", ARTICLE),
    "/mirror": (200, "text/html", ARTICLE),
    "/nometa": (200, "text/html", ARTICLE_NOMETA),
    "/plain": (200, "text/html",
               "<html><head><title>Tiny</title></head>"
               "<body><p>Hello world.</p></body></html>"),
    "/malformed": (200, "text/html",
                   "<html><head><title>Broken<body><p>unclosed "
                   + ARTICLE_BODY + "<div><span>never closed"),
    "/private/secret": (200, "text/html", ARTICLE),
}

REQUEST_LOG: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        REQUEST_LOG.append(self.path)
        entry = PAGES.get(self.path.split("?")[0])
        if entry is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        status, ctype, body = entry
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):  # silence test-server logging
        pass


@pytest.fixture(scope="session")
def server():
    REQUEST_LOG.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def request_log():
    return REQUEST_LOG


def run_cli(*argv: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(CLI), *argv],
                          capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            f"CLI did not emit JSON.\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
    return proc.returncode, payload


def collect(server: str, tmp_path: Path, paths: list[str]) -> tuple[dict, list[dict]]:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("\n".join(server + p for p in paths) + "\n")
    outdir = tmp_path / "out"
    code, payload = run_cli("collect", "--urls", str(urls_file),
                            "--outdir", str(outdir), "--delay", "0")
    assert payload["ok"] is True, payload
    records = [json.loads(line) for line in
               (outdir / "records.jsonl").read_text().splitlines()]
    return payload["data"], records
