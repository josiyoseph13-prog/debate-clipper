"""Step 4 tests: optimize (pikepdf tier)."""
from __future__ import annotations

from pathlib import Path

from conftest import PASSWORD, run_cli
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def _make_uncompressed_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setPageCompression(0)
    for page in range(3):
        for line in range(40):
            c.drawString(72, 720 - line * 12,
                         f"OPTIMIZE MARKER page {page} line {line} "
                         "with repeated body text to take up space.")
        c.showPage()
    c.save()
    return path


def test_optimize_reduces_uncompressed(tmp_path):
    src = _make_uncompressed_pdf(tmp_path / "fat.pdf")
    out = tmp_path / "opt.pdf"
    _, r = run_cli("optimize", str(src), "--out", str(out))
    assert r["ok"] is True, r["error"]
    d = r["data"]
    assert d["pages_out"] == 3
    assert d["reduced"] is True and d["reduction_pct"] > 30
    assert "pikepdf" in d["engine"]
    _, rt = run_cli("extract-text", str(out), "--pages", "1")
    assert "OPTIMIZE MARKER" in rt["data"]["pages"][0]["text"]


def test_optimize_normal_doc(fixtures, tmp_path):
    out = tmp_path / "opt3.pdf"
    _, r = run_cli("optimize", str(fixtures["doc3"]), "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["pages_out"] == 3
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["page_count"] == 3


def test_optimize_linearize(fixtures, tmp_path):
    out = tmp_path / "lin.pdf"
    _, r = run_cli("optimize", str(fixtures["doc3"]), "--linearize",
                   "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["linearized"] is True
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["page_count"] == 3


def test_optimize_malformed(fixtures, tmp_path):
    _, r = run_cli("optimize", str(fixtures["bad"]),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "could not" in r["error"]


def test_optimize_encrypted(fixtures, tmp_path):
    out = tmp_path / "enc-opt.pdf"
    _, r = run_cli("optimize", str(fixtures["encrypted"]),
                   "--out", str(out))
    assert r["ok"] is False  # password required
    _, r = run_cli("optimize", str(fixtures["encrypted"]),
                   "--password", PASSWORD, "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["pages_out"] == 3


def test_doctor_optimize_tier_on():
    _, r = run_cli("doctor")
    assert r["data"]["features"]["optimize_tier_pikepdf"] is True
    assert r["data"]["libraries"]["pikepdf"] == "10.16.0"
