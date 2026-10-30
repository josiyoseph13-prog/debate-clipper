"""Fixtures: synthetic PDFs generated locally with reportlab + pypdf.

No downloaded samples — the suite is fully self-contained.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PROJECT = Path(__file__).resolve().parents[2]
PYTHON = PROJECT / "pdf-venv" / "bin" / "python"
CLI = PROJECT / "skill" / "scripts" / "pdf_tool.py"
PASSWORD = "test-password"


def run_cli(*argv: str):
    proc = subprocess.run(
        [str(PYTHON), str(CLI), *argv],
        capture_output=True, text=True, timeout=120)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            f"CLI did not emit JSON.\nstdout: {proc.stdout[:500]}\n"
            f"stderr: {proc.stderr[:500]}")
    return proc, result


def make_pdf(path: Path, texts: list[str], title: str | None = None,
             author: str | None = None) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    if title:
        c.setTitle(title)
    if author:
        c.setAuthor(author)
    for text in texts:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return path


def make_table_pdf(path: Path) -> Path:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    table = Table([["Item", "Qty"], ["Apples", "42"], ["Pears", "7"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "#000000")]))
    doc.build([table])
    return path


def make_form_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle("Form Fixture")
    c.drawString(72, 750, "Name:")
    c.acroForm.textfield(name="name", x=120, y=738, width=220, height=18)
    c.drawString(72, 700, "Agree:")
    c.acroForm.checkbox(name="agree", x=120, y=690, size=14)
    c.drawString(72, 660, "Color:")
    # NOTE: reportlab 5.0.1 AcroForm.choice crashes without value=
    # (upstream UnboundLocalError in its listbox extras path).
    c.acroForm.choice(name="color", options=["red", "green", "blue"],
                      value="red", x=120, y=648, width=120, height=18)
    c.showPage()
    c.save()
    return path


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory) -> dict:
    d = tmp_path_factory.mktemp("pdf-fixtures")
    doc3 = make_pdf(d / "doc3.pdf",
                    ["ALPHA PAGE ONE", "BRAVO PAGE TWO", "CHARLIE PAGE THREE"],
                    title="Step1 Fixture", author="Pax Tests")
    doc2 = make_pdf(d / "doc2.pdf", ["DELTA PAGE ONE", "ECHO PAGE TWO"])
    blank = make_pdf(d / "blank.pdf", [""])
    # encrypted copy of doc3 (AES-256 via pypdf + cryptography)
    reader = PdfReader(str(doc3))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=PASSWORD, algorithm="AES-256")
    enc = d / "encrypted.pdf"
    with open(enc, "wb") as fh:
        writer.write(fh)
    bad = d / "bad.pdf"
    bad.write_bytes(b"this is not a pdf at all")
    table_pdf = make_table_pdf(d / "table.pdf")
    form_pdf = make_form_pdf(d / "form.pdf")
    return {"dir": d, "doc3": doc3, "doc2": doc2, "blank": blank,
            "encrypted": enc, "bad": bad, "password": PASSWORD,
            "table": table_pdf, "form": form_pdf}


def sha256_of(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()
