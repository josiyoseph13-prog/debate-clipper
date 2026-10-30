"""compress — lossless content-stream recompression (pypdf).

Recompresses each page's content streams. It does NOT touch images
(re-encoding images is the pikepdf tier), so savings vary: large on
PDFs with uncompressed streams, near zero on already-compressed
files. The result always reports real sizes and whether a reduction
was achieved — never a promised percentage.
"""
from __future__ import annotations

from pypdf import PdfReader, PdfWriter

from .common import (open_reader, sha256_file, validate_input_pdf,
                     validate_output)


def run(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    writer = PdfWriter()
    count = 0
    for page in reader.pages:
        # pypdf 6: a page can only be compressed once it belongs to a
        # writer, so add first, then compress the writer's page.
        added = writer.add_page(page)
        added.compress_content_streams()
        count += 1
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()

    size_in = src.stat().st_size
    size_out = out.stat().st_size
    check = PdfReader(str(out))
    warnings: list[str] = []
    reduced = size_out < size_in
    if not reduced:
        warnings.append(
            "no size reduction: the document's streams were probably "
            "already compressed (image recompression is the optional "
            "pikepdf tier, not basic compression)")
    data = {"out": str(out), "pages_out": len(check.pages),
            "size_in": size_in, "size_out": size_out,
            "reduced": reduced,
            "reduction_pct": (round(100 * (size_in - size_out) / size_in, 1)
                              if size_in else 0.0),
            "out_sha256": sha256_file(out)}
    return data, warnings
