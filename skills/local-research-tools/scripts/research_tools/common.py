"""Shared helpers: errors, URL canonicalization, domain parsing."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

USER_AGENT = "PaxResearch/1.0 (+local research tool; respects robots.txt)"
MAX_BODY_BYTES = 5_000_000

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
}


class ResearchError(Exception):
    """An error that should be reported as clean JSON, not a traceback."""


def canonicalize_url(url: str) -> str:
    """Normalize a URL for deduplication: lowercase scheme/host, drop
    default ports, fragments and tracking parameters, sort the query,
    and drop a trailing slash (except for the root path)."""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in _TRACKING_PARAMS))
    return urlunsplit((scheme, netloc, path, query, ""))


def registered_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return ext.top_domain_under_public_suffix or (ext.domain or "")


def content_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})")


def youtube_video_id(url_or_id: str) -> str | None:
    value = url_or_id.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value
    match = _VIDEO_ID_RE.search(value)
    return match.group(1) if match else None
