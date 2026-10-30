"""edit-metadata — write a copy with changed document metadata.

Fields: title, author, subject, keywords, creator. --clear takes a
comma list of field names and empties them. At least one change is
required. The result is verified by reading the output's metadata
back; both before and after values are reported.
"""
from __future__ import annotations

from pypdf import PdfReader, PdfWriter

from .common import (PdfToolError, open_reader, sha256_file,
                     validate_input_pdf, validate_output)

_FIELDS = {"title": "/Title", "author": "/Author", "subject": "/Subject",
           "keywords": "/Keywords", "creator": "/Creator"}


def _read_meta(reader: PdfReader) -> dict:
    meta = reader.metadata
    if meta is None:
        return {name: None for name in _FIELDS}
    return {"title": meta.title, "author": meta.author,
            "subject": meta.subject, "keywords": meta.keywords,
            "creator": meta.creator}


def run(args) -> tuple[dict, list[str]]:
    changes: dict[str, str] = {}
    for name in _FIELDS:
        value = getattr(args, name)
        if value is not None:
            changes[name] = value
    clear: list[str] = []
    if args.clear:
        clear = [c.strip().lower() for c in args.clear.split(",") if c.strip()]
        unknown = [c for c in clear if c not in _FIELDS]
        if unknown:
            raise PdfToolError(
                f"unknown metadata field(s) to clear: {unknown}; "
                f"allowed: {sorted(_FIELDS)}")
        for name in clear:
            changes[name] = ""
    if not changes:
        raise PdfToolError(
            "nothing to change: pass at least one of --title/--author/"
            "--subject/--keywords/--creator or --clear")

    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    before = _read_meta(reader)

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # start from the existing metadata so untouched fields survive
    existing = {}
    if reader.metadata:
        for name, key in _FIELDS.items():
            value = before[name]
            if value:
                existing[key] = str(value)
        if reader.metadata.producer:
            existing["/Producer"] = str(reader.metadata.producer)
    for name, value in changes.items():
        existing[_FIELDS[name]] = value
    if existing:
        writer.add_metadata(existing)
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()

    after = _read_meta(PdfReader(str(out)))
    data = {"out": str(out), "changed": sorted(changes),
            "before": before, "after": after,
            "out_sha256": sha256_file(out)}
    return data, []
