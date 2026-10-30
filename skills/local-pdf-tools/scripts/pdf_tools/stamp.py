"""stamp — text watermark/stamp over (or under) pages.

The overlay is drawn with reportlab at each page's own size, rotated
and translucent, then merged with pypdf. The input is never modified.
"""
from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .common import (PdfToolError, open_reader, parse_pages_spec,
                     sha256_file, validate_input_pdf, validate_output)


def _make_overlay(text: str, width: float, height: float,
                  opacity: float, angle: float, font_size: float):
    """Return (reader, page); the reader is kept alive by the caller
    until the writer has been written out."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(angle)
    c.setFillAlpha(opacity)
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.showPage()
    c.save()
    buf.seek(0)
    reader = PdfReader(buf)
    return reader, reader.pages[0]


def run(args) -> tuple[dict, list[str]]:
    if not args.text.strip():
        raise PdfToolError("--text must not be empty")
    if not 0 < args.opacity <= 1:
        raise PdfToolError("--opacity must be in (0, 1]")
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    count = len(reader.pages)
    targets = (parse_pages_spec(args.pages, count) if args.pages
               else list(range(1, count + 1)))
    writer = PdfWriter()
    keep_alive: list[PdfReader] = []
    for i, page in enumerate(reader.pages, start=1):
        if i in targets:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            font_size = args.font_size or max(24.0, min(width, height) / 9)
            overlay_reader, overlay = _make_overlay(
                args.text, width, height, args.opacity, args.angle,
                font_size)
            keep_alive.append(overlay_reader)
            if args.under:
                overlay.merge_page(page)   # content drawn over the stamp
                writer.add_page(overlay)
            else:
                page.merge_page(overlay)   # stamp drawn over the content
                writer.add_page(page)
        else:
            writer.add_page(page)
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()
    data = {"out": str(out), "pages_in": count, "pages_out": count,
            "stamped_pages": targets, "under": bool(args.under),
            "out_sha256": sha256_file(out)}
    return data, []
