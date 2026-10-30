"""Page operations: merge, split, rotate, reorder, extract-pages (pypdf).

Inputs are opened read-only and never modified; every operation writes
a brand-new output file (validated by common.validate_output).
"""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from .common import (PdfToolError, open_reader, parse_chunks_spec,
                     parse_order_spec, parse_pages_spec, sha256_file,
                     validate_input_pdf, validate_output)


def _write(writer: PdfWriter, out: Path) -> None:
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()


def _out_data(out: Path, pages_in: int, pages_out: int) -> dict:
    return {"out": str(out), "pages_in": pages_in, "pages_out": pages_out,
            "out_sha256": sha256_file(out)}


def merge(args) -> tuple[dict, list[str]]:
    inputs = [validate_input_pdf(p) for p in args.inputs]
    if len(inputs) < 2:
        raise PdfToolError("merge needs at least two input PDFs")
    out = validate_output(args.out, args.overwrite, inputs)
    writer = PdfWriter()
    total = 0
    readers = [open_reader(p, args.password) for p in inputs]
    for reader in readers:
        for page in reader.pages:
            writer.add_page(page)
            total += 1
    _write(writer, out)
    data = _out_data(out, total, total)
    data["inputs"] = [str(p) for p in inputs]
    return data, []


def split(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    reader = open_reader(src, args.password)
    count = len(reader.pages)
    chunks = parse_chunks_spec(args.ranges, count)
    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_dir():
        raise PdfToolError(f"out-dir does not exist: {out_dir}")
    prefix = args.prefix or src.stem
    outputs = [out_dir / f"{prefix}-part{i}.pdf"
               for i in range(1, len(chunks) + 1)]
    for out in outputs:  # validate ALL outputs before writing any
        validate_output(str(out), args.overwrite, [src])
    results = []
    for chunk, out in zip(chunks, outputs):
        writer = PdfWriter()
        for page_no in chunk:
            writer.add_page(reader.pages[page_no - 1])
        _write(writer, out)
        results.append({"out": str(out), "pages": chunk,
                        "out_sha256": sha256_file(out)})
    return {"input": str(src), "pages_in": count, "outputs": results}, []


def rotate(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    angle = args.angle % 360
    if angle not in (90, 180, 270):
        raise PdfToolError("angle must be one of 90, 180, 270 "
                           "(or -90/-180/-270)")
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    count = len(reader.pages)
    targets = (parse_pages_spec(args.pages, count) if args.pages
               else list(range(1, count + 1)))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        if i in targets:
            page.rotate(angle)
        writer.add_page(page)
    _write(writer, out)
    data = _out_data(out, count, count)
    data["rotated_pages"] = targets
    data["angle"] = angle
    return data, []


def reorder(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    count = len(reader.pages)
    order = parse_order_spec(args.order, count)
    writer = PdfWriter()
    for page_no in order:
        writer.add_page(reader.pages[page_no - 1])
    _write(writer, out)
    data = _out_data(out, count, count)
    data["order"] = order
    return data, []


def extract_pages(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    count = len(reader.pages)
    wanted = parse_pages_spec(args.pages, count)
    writer = PdfWriter()
    for page_no in wanted:
        writer.add_page(reader.pages[page_no - 1])
    _write(writer, out)
    data = _out_data(out, count, len(wanted))
    data["pages"] = wanted
    return data, []
