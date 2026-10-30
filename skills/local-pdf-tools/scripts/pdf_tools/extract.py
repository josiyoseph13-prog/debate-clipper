"""extract-text — page-by-page text extraction via pdfplumber.

Pages are processed one at a time and released as we go, so memory
stays bounded on large documents. A page that fails to extract becomes
a warning and an empty page, not a crashed run.
"""
from __future__ import annotations

import pdfplumber

from .common import (PdfToolError, open_reader, parse_pages_spec,
                     sha256_file, validate_input_pdf, validate_output)


def run(args) -> tuple[dict, list[str]]:
    path = validate_input_pdf(args.input)
    # Validate encryption/password and get the page count with pypdf
    # first, so password problems produce our clean errors.
    reader = open_reader(path, args.password)
    page_count = len(reader.pages)

    if args.pages:
        wanted = parse_pages_spec(args.pages, page_count)
    else:
        wanted = list(range(1, page_count + 1))

    warnings: list[str] = []
    try:
        pdf = pdfplumber.open(str(path), password=args.password or "")
    except Exception as exc:
        raise PdfToolError(f"could not open PDF for extraction: {exc}") from exc

    pages_out: list[dict] = []
    total_chars = 0
    with pdf:
        for page_no in wanted:
            page = pdf.pages[page_no - 1]
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # keep going page-by-page
                warnings.append(
                    f"page {page_no}: extraction failed "
                    f"({type(exc).__name__})")
                text = ""
            total_chars += len(text)
            pages_out.append({"page": page_no, "chars": len(text),
                              "text": text})

    data: dict = {
        "file": str(path),
        "page_count": page_count,
        "pages_extracted": len(pages_out),
        "chars_total": total_chars,
    }
    if args.out:
        out = validate_output(args.out, args.overwrite, [path])
        text_all = "\n\n".join(p["text"] for p in pages_out)
        out.write_text(text_all, encoding="utf-8")
        data["out"] = str(out)
        data["out_sha256"] = sha256_file(out)
    else:
        data["pages"] = pages_out
    return data, warnings
