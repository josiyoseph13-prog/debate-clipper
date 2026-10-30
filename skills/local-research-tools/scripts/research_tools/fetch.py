"""Polite fetching: robots.txt enforced, one UA, timeouts, size cap.

No cookies, no authentication, no paywall/CAPTCHA bypass — ever.
A robots.txt denial is a result, not an obstacle to route around.
"""
from __future__ import annotations

import os
import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

from .common import MAX_BODY_BYTES, USER_AGENT, ResearchError


def _build_client(timeout: float) -> httpx.Client:
    """HTTP client that survives this machine's proxy setup.

    Facts established by diagnosis (2026-10-11): all egress goes
    through the proxy named by the *_PROXY variables; direct
    connections fail. But httpx's trust_env parsing crashes on the
    bracketed IPv6 entries in NO_PROXY (InvalidURL ':1]'), so the
    proxy URL is read directly and passed explicitly, with loopback
    mounts kept direct for local sources/tests.
    """
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
             or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))
    mounts = None
    if proxy:
        mounts = {
            "all://": httpx.HTTPTransport(proxy=proxy),
            "http://127.0.0.1": httpx.HTTPTransport(),
            "http://localhost": httpx.HTTPTransport(),
        }
    return httpx.Client(headers={"User-Agent": USER_AGENT},
                        follow_redirects=True, timeout=timeout,
                        trust_env=False, mounts=mounts)


class Fetcher:
    def __init__(self, delay: float = 1.0, timeout: float = 45.0):
        # 45s: heavy pages through this machine's egress proxy can
        # exceed 20s (Wikipedia's Debate article timed out at 20s and
        # succeeded well within 45s).
        self.delay = delay
        self.timeout = timeout
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_request_at: dict[str, float] = {}
        self._client = _build_client(timeout)

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        # Fetch robots.txt through our own client and UA: fetching it
        # with urllib's default identity gets a 403 from some hosts
        # (e.g. Wikimedia), which RobotFileParser then treats as
        # "disallow everything" — a false denial.
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: urllib.robotparser.RobotFileParser | None = None
            try:
                resp = self._client.get(origin + "/robots.txt")
                if resp.status_code == 200:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(resp.text.splitlines())
                elif resp.status_code == 404:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse([])  # no robots.txt -> allow
            except httpx.HTTPError:
                parser = None  # unreachable -> proceed openly
            self._robots[origin] = parser
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(USER_AGENT, url)

    def _respect_delay(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last_request_at.get(host)
        if last is not None:
            wait = self.delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[host] = time.monotonic()

    def fetch(self, url: str) -> dict:
        """Return {status, http_status, content_type, text, error}."""
        if not self.allowed(url):
            return {"status": "robots_denied", "http_status": None,
                    "content_type": None, "text": None,
                    "error": "robots.txt disallows this URL for our agent"}
        self._respect_delay(url)
        try:
            with self._client.stream("GET", url) as resp:
                status = resp.status_code
                ctype = resp.headers.get("content-type", "")
                if status >= 400:
                    return {"status": "http_error", "http_status": status,
                            "content_type": ctype, "text": None,
                            "error": f"HTTP {status}"}
                if "text/html" not in ctype and "application/xhtml" not in ctype:
                    return {"status": "skipped_type", "http_status": status,
                            "content_type": ctype, "text": None,
                            "error": f"not an HTML page (content-type: {ctype})"}
                body = b""
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BODY_BYTES:
                        return {"status": "too_large", "http_status": status,
                                "content_type": ctype, "text": None,
                                "error": f"body exceeds {MAX_BODY_BYTES} bytes"}
                charset = resp.encoding or "utf-8"
                return {"status": "fetched", "http_status": status,
                        "content_type": ctype,
                        "text": body.decode(charset, errors="replace"),
                        "error": None}
        except httpx.HTTPError as exc:
            return {"status": "network_error", "http_status": None,
                    "content_type": None, "text": None,
                    "error": f"{type(exc).__name__}: {exc}"}

    def close(self) -> None:
        self._client.close()


def require_http_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ResearchError(f"not an http(s) URL: {url!r}")
    return url
