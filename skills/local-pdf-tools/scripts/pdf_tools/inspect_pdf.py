"""inspect — page count, metadata, page dimensions, encryption status."""
from __future__ import annotations

from .common import (open_reader, open_reader_lenient, sha256_file,
                     validate_input_pdf)


def _meta_str(value) -> str | None:
    if value is None:
        return None
    return str(value)


def run(args) -> tuple[dict, list[str]]:
    path = validate_input_pdf(args.input)
    warnings: list[str] = []
    data: dict = {
        "file": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    reader = open_reader_lenient(path)
    data["pdf_version"] = getattr(reader, "pdf_header", None)
    data["encrypted"] = bool(reader.is_encrypted)

    if reader.is_encrypted and not args.password:
        # Report what is knowable without the password; page-level
        # details require decryption.
        data["page_count"] = None
        data["metadata"] = None
        data["pages"] = []
        warnings.append("encrypted PDF: pass --password for page count, "
                        "metadata and page dimensions")
        return data, warnings

    if reader.is_encrypted:
        reader = open_reader(path, args.password)

    meta = reader.metadata
    data["metadata"] = {
        "title": _meta_str(meta.title) if meta else None,
        "author": _meta_str(meta.author) if meta else None,
        "subject": _meta_str(meta.subject) if meta else None,
        "creator": _meta_str(meta.creator) if meta else None,
        "producer": _meta_str(meta.producer) if meta else None,
        "creation_date": _meta_str(meta.creation_date) if meta else None,
        "modification_date": _meta_str(meta.modification_date) if meta else None,
    }
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        pages.append({
            "page": i,
            "width_pt": round(float(box.width), 2),
            "height_pt": round(float(box.height), 2),
            "rotation": int(page.rotation or 0),
        })
    data["page_count"] = len(pages)
    data["pages"] = pages
    return data, warnings
