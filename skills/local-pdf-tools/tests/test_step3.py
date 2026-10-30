"""Step 3 tests: edit-metadata and compress."""
from __future__ import annotations

from pathlib import Path

from conftest import PASSWORD, run_cli, sha256_of
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ---------- edit-metadata ----------

def test_edit_metadata_sets_fields(fixtures, tmp_path):
    before_hash = sha256_of(fixtures["doc3"])
    out = tmp_path / "meta.pdf"
    _, r = run_cli("edit-metadata", str(fixtures["doc3"]),
                   "--title", "New Title", "--author", "Jo",
                   "--subject", "Testing", "--keywords", "a,b,c",
                   "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["before"]["title"] == "Step1 Fixture"
    after = r["data"]["after"]
    assert after["title"] == "New Title"
    assert after["author"] == "Jo"
    assert after["subject"] == "Testing"
    assert after["keywords"] == "a,b,c"
    assert sha256_of(fixtures["doc3"]) == before_hash  # input untouched
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["page_count"] == 3


def test_edit_metadata_clear(fixtures, tmp_path):
    out = tmp_path / "cleared.pdf"
    _, r = run_cli("edit-metadata", str(fixtures["doc3"]),
                   "--clear", "title,author", "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["after"]["title"] in ("", None)
    assert r["data"]["after"]["author"] in ("", None)


def test_edit_metadata_nothing_to_change(fixtures, tmp_path):
    _, r = run_cli("edit-metadata", str(fixtures["doc3"]),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "nothing to change" in r["error"]


def test_edit_metadata_unknown_clear_field(fixtures, tmp_path):
    _, r = run_cli("edit-metadata", str(fixtures["doc3"]),
                   "--clear", "bogus", "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "unknown metadata field" in r["error"]


def test_edit_metadata_encrypted(fixtures, tmp_path):
    out = tmp_path / "enc-meta.pdf"
    _, r = run_cli("edit-metadata", str(fixtures["encrypted"]),
                   "--title", "T", "--out", str(out))
    assert r["ok"] is False  # needs the password first
    _, r = run_cli("edit-metadata", str(fixtures["encrypted"]),
                   "--title", "T", "--password", PASSWORD,
                   "--out", str(out))
    assert r["ok"] is True and r["data"]["after"]["title"] == "T"


# ---------- compress ----------

def _make_uncompressed_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setPageCompression(0)  # streams stored raw -> recompression wins
    for page in range(3):
        for line in range(40):
            c.drawString(72, 720 - line * 12,
                         f"UNCOMPRESSED MARKER page {page} line {line} "
                         "with some repeated body text to take up space.")
        c.showPage()
    c.save()
    return path


def test_compress_reduces_uncompressed(tmp_path):
    src = _make_uncompressed_pdf(tmp_path / "fat.pdf")
    out = tmp_path / "thin.pdf"
    _, r = run_cli("compress", str(src), "--out", str(out))
    assert r["ok"] is True, r["error"]
    d = r["data"]
    assert d["pages_out"] == 3
    assert d["reduced"] is True
    assert d["size_out"] < d["size_in"]
    assert d["reduction_pct"] > 30
    _, rt = run_cli("extract-text", str(out), "--pages", "1")
    assert "UNCOMPRESSED MARKER" in rt["data"]["pages"][0]["text"]


def test_compress_already_compressed_is_honest(fixtures, tmp_path):
    out = tmp_path / "c.pdf"
    _, r = run_cli("compress", str(fixtures["doc3"]), "--out", str(out))
    assert r["ok"] is True
    assert r["data"]["pages_out"] == 3
    if not r["data"]["reduced"]:
        assert any("no size reduction" in w for w in r["warnings"])


def test_compress_malformed(fixtures, tmp_path):
    _, r = run_cli("compress", str(fixtures["bad"]),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "could not read" in r["error"]


def test_doctor_step3_features():
    _, r = run_cli("doctor")
    f = r["data"]["features"]
    assert f["metadata_edit"] is True and f["compress_basic"] is True
