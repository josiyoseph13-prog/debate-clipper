"""create — build a PDF from a JSON spec or a plain-text file (reportlab).

JSON spec shape (validated strictly; unknown blocks are an error):
  {"title": str, "author": str,
   "blocks": [
     {"type": "heading", "text": str, "level": 1|2|3},
     {"type": "paragraph", "text": str},
     {"type": "table", "rows": [[cell, ...], ...], "header": true|false},
     {"type": "spacer", "height": number},
     {"type": "pagebreak"}]}

Text mode: lines starting "# " / "## " become headings, blank lines
become spacing, every other line becomes a paragraph.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from .common import PdfToolError, sha256_file, validate_output

_BLOCK_TYPES = {"heading", "paragraph", "table", "spacer", "pagebreak"}


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _validate_spec(spec) -> dict:
    if not isinstance(spec, dict):
        raise PdfToolError("spec must be a JSON object")
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise PdfToolError("spec.blocks must be a non-empty list")
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise PdfToolError(f"block {i} is not an object")
        btype = block.get("type")
        if btype not in _BLOCK_TYPES:
            raise PdfToolError(
                f"block {i}: unknown type '{btype}' "
                f"(allowed: {sorted(_BLOCK_TYPES)})")
        if btype in ("heading", "paragraph"):
            if not isinstance(block.get("text"), str) or not block["text"]:
                raise PdfToolError(f"block {i} ({btype}) needs text")
            if btype == "heading" and block.get("level", 1) not in (1, 2, 3):
                raise PdfToolError(f"block {i}: heading level must be 1-3")
        elif btype == "table":
            rows = block.get("rows")
            if (not isinstance(rows, list) or not rows
                    or any(not isinstance(r, list) or not r for r in rows)):
                raise PdfToolError(
                    f"block {i}: table needs non-empty rows of cells")
        elif btype == "spacer":
            height = block.get("height", 12)
            if not isinstance(height, (int, float)) or not 0 < height <= 700:
                raise PdfToolError(f"block {i}: spacer height must be 1-700")
    return spec


def _blocks_from_text(text: str) -> list[dict]:
    blocks: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            blocks.append({"type": "spacer", "height": 8})
        elif stripped.startswith("## "):
            blocks.append({"type": "heading", "text": stripped[3:],
                           "level": 2})
        elif stripped.startswith("# "):
            blocks.append({"type": "heading", "text": stripped[2:],
                           "level": 1})
        else:
            blocks.append({"type": "paragraph", "text": stripped})
    if not blocks:
        raise PdfToolError("text file produced no content blocks")
    return blocks


def _build(spec: dict, out: Path) -> int:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(out), pagesize=letter,
        leftMargin=72, rightMargin=72, topMargin=72, bottomMargin=72,
        title=spec.get("title") or "Untitled",
        author=spec.get("author") or "")
    flow = []
    for block in spec["blocks"]:
        btype = block["type"]
        if btype == "heading":
            flow.append(Paragraph(_esc(block["text"]),
                                  styles[f"Heading{block.get('level', 1)}"]))
        elif btype == "paragraph":
            flow.append(Paragraph(_esc(block["text"]), styles["BodyText"]))
            flow.append(Spacer(1, 6))
        elif btype == "table":
            rows = [[_esc(str(cell)) for cell in row]
                    for row in block["rows"]]
            table = Table(rows, repeatRows=1 if block.get("header") else 0)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, "#888888"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            flow.append(table)
            flow.append(Spacer(1, 8))
        elif btype == "spacer":
            flow.append(Spacer(1, float(block.get("height", 12))))
        elif btype == "pagebreak":
            flow.append(PageBreak())

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(letter[0] / 2, 36, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    from pypdf import PdfReader
    return len(PdfReader(str(out)).pages)


def run(args) -> tuple[dict, list[str]]:
    if bool(args.spec) == bool(args.from_text):
        raise PdfToolError("pass exactly one of --spec or --from-text")
    out = validate_output(args.out, args.overwrite, [])
    if args.spec:
        spec_path = Path(args.spec).expanduser()
        if not spec_path.is_file():
            raise PdfToolError(f"spec file not found: {spec_path}")
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PdfToolError(f"spec is not valid JSON: {exc}") from exc
        spec = _validate_spec(spec)
    else:
        text_path = Path(args.from_text).expanduser()
        if not text_path.is_file():
            raise PdfToolError(f"text file not found: {text_path}")
        try:
            text = text_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PdfToolError(f"text file is not UTF-8: {exc}") from exc
        spec = {"title": args.title or text_path.stem,
                "blocks": _blocks_from_text(text)}
        _validate_spec(spec)
    pages = _build(spec, out)
    data = {"out": str(out), "pages_out": pages,
            "blocks": len(spec["blocks"]),
            "out_sha256": sha256_file(out)}
    return data, []
