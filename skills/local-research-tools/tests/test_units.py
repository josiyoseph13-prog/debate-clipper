"""Unit tests: canonicalization, ids, doctor, youtube error paths."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from conftest import run_cli  # noqa: E402
from research_tools.common import (canonicalize_url,  # noqa: E402
                                   youtube_video_id)


def test_canonicalize_strips_tracking_and_fragment():
    assert canonicalize_url(
        "HTTPS://Example.COM:443/path/?utm_source=x&b=2&a=1#frag"
    ) == "https://example.com/path?a=1&b=2"


def test_canonicalize_keeps_meaningful_query():
    assert canonicalize_url("https://ex.com/watch?v=abc") == \
        "https://ex.com/watch?v=abc"


def test_youtube_id_forms():
    assert youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") \
        == "dQw4w9WgXcQ"
    assert youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_video_id("https://example.com/nope") is None


def test_youtube_info_rejects_non_youtube():
    code, payload = run_cli("youtube-info", "https://example.com/nope")
    assert payload["ok"] is False
    assert "could not find a YouTube video id" in payload["error"]


def test_doctor_reports_core():
    code, payload = run_cli("doctor")
    assert payload["ok"] is True
    assert payload["data"]["core_ok"] is True
    assert payload["data"]["features"]["youtube_probe"] is True
