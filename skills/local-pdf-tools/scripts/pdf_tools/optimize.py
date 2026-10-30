"""optimize — pikepdf tier: strong lossless optimization + repair.

Uses pikepdf (wheels bundle the qpdf library — no system install):
recompresses streams, generates object streams, drops orphaned
objects, and repairs structural damage on open. Optional
--linearize produces a web-ready linearized file. Images are NOT
re-encoded (lossy recompression stays out of scope). The output is
verified by reopening it and comparing page counts.
"""
from __future__ import annotations

import pikepdf

from .common import (PdfToolError, open_reader, sha256_file,
                     validate_input_pdf, validate_output)


def run(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    # Page count via pypdf first (also validates password handling in
    # our own error language); pikepdf then does the heavy lifting.
    expected_pages = len(open_reader(src, args.password).pages)
    try:
        pdf = pikepdf.open(str(src), password=args.password or "")
    except pikepdf.PasswordError as exc:
        raise PdfToolError(
            "incorrect or missing password for encrypted PDF") from exc
    except pikepdf.PdfError as exc:
        raise PdfToolError(f"could not open/repair PDF: {exc}") from exc
    with pdf:
        pdf.remove_unreferenced_resources()
        # pikepdf 10 renamed the kwarg to object_stream_mode
        pdf.save(out, compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 linearize=args.linearize)
    check = pikepdf.open(out)
    pages_out = len(check.pages)
    check.close()
    if pages_out != expected_pages:
        raise PdfToolError(
            f"verification failed: pages changed {expected_pages} -> "
            f"{pages_out}")
    size_in = src.stat().st_size
    size_out = out.stat().st_size
    warnings: list[str] = []
    if size_out >= size_in:
        warnings.append(
            "no size reduction: the file was already well optimized "
            "(the output is still structurally rebuilt and verified)")
    data = {"out": str(out), "pages_out": pages_out,
            "size_in": size_in, "size_out": size_out,
            "reduced": size_out < size_in,
            "reduction_pct": (round(100 * (size_in - size_out) / size_in, 1)
                              if size_in else 0.0),
            "linearized": bool(args.linearize),
            "engine": f"pikepdf {pikepdf.__version__}",
            "out_sha256": sha256_file(out)}
    return data, warnings
