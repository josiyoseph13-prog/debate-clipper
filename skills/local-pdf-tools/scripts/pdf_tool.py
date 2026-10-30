#!/usr/bin/env python3
"""pdf_tool — CLI entry point for Pax's pdf-tools skill (step 1).

Every command prints exactly one JSON object to stdout:
  {"ok": bool, "command": str, "data": {...} | null,
   "warnings": [str], "error": str | null, "timing_ms": int}
Exit codes: 0 ok, 2 user error (bad args/paths/passwords/files),
3 unexpected internal error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdf_tools import (compress, create, doctor, extract,  # noqa: E402
                       forms, inspect_pdf, metadata, optimize, pages,
                       secure, stamp, tables)
from pdf_tools.common import PdfToolError  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep the JSON contract even for bad args
        raise PdfToolError(f"invalid arguments: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="pdf_tool", description="Pax pdf-tools (step 1)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check dependencies and features")

    p = sub.add_parser("inspect", help="metadata, pages, encryption status")
    p.add_argument("input")
    p.add_argument("--password")
    p.set_defaults(func=inspect_pdf.run)

    p = sub.add_parser("extract-text", help="page-by-page text extraction")
    p.add_argument("input")
    p.add_argument("--pages", help="e.g. '1-3,5' (default: all)")
    p.add_argument("--password")
    p.add_argument("--out", help="write text to this file instead of JSON")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=extract.run)

    p = sub.add_parser("extract-tables", help="extract tables per page")
    p.add_argument("input")
    p.add_argument("--pages", help="e.g. '1-3,5' (default: all)")
    p.add_argument("--password")
    p.add_argument("--out", help=".json or .csv output file")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=tables.run)

    p = sub.add_parser("create", help="build a PDF from a spec/text file")
    p.add_argument("--spec", help="JSON spec file")
    p.add_argument("--from-text", help="plain-text file (# = heading)")
    p.add_argument("--title", help="title for text mode")
    p.add_argument("--out", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=create.run)

    p = sub.add_parser("stamp", help="watermark/stamp text on pages")
    p.add_argument("input")
    p.add_argument("--text", required=True)
    p.add_argument("--pages", help="e.g. '1-3,5' (default: all)")
    p.add_argument("--opacity", type=float, default=0.15)
    p.add_argument("--angle", type=float, default=45.0)
    p.add_argument("--font-size", type=float)
    p.add_argument("--under", action="store_true",
                   help="draw the stamp under the page content")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=stamp.run)

    p = sub.add_parser("form-fields", help="list AcroForm fields")
    p.add_argument("input")
    p.add_argument("--password")
    p.set_defaults(func=forms.list_fields)

    p = sub.add_parser("fill-form", help="fill AcroForm fields from JSON")
    p.add_argument("input")
    p.add_argument("--data", required=True, help="JSON {field: value}")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=forms.fill)

    p = sub.add_parser("encrypt", help="AES-256 encrypt a copy")
    p.add_argument("input")
    p.add_argument("--password", help="new user password")
    p.add_argument("--owner-password")
    p.add_argument("--input-password",
                   help="password if the input is already encrypted")
    p.add_argument("--out", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=secure.encrypt)

    p = sub.add_parser("decrypt", help="write an unencrypted copy")
    p.add_argument("input")
    p.add_argument("--password", help="the document's password")
    p.add_argument("--out", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=secure.decrypt)

    p = sub.add_parser("edit-metadata",
                       help="write a copy with changed metadata")
    p.add_argument("input")
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--subject")
    p.add_argument("--keywords")
    p.add_argument("--creator")
    p.add_argument("--clear", help="comma list of fields to empty")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=metadata.run)

    p = sub.add_parser("compress",
                       help="lossless stream recompression")
    p.add_argument("input")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=compress.run)

    p = sub.add_parser("optimize",
                       help="pikepdf tier: strong optimization/repair")
    p.add_argument("input")
    p.add_argument("--linearize", action="store_true")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=optimize.run)

    p = sub.add_parser("merge", help="merge PDFs in the given order")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=pages.merge)

    p = sub.add_parser("split", help="split into one file per range chunk")
    p.add_argument("input")
    p.add_argument("--ranges", required=True, help="e.g. '1-2,3'")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--prefix")
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=pages.split)

    p = sub.add_parser("rotate", help="rotate selected pages (default: all)")
    p.add_argument("input")
    p.add_argument("--angle", required=True, type=int)
    p.add_argument("--pages", help="e.g. '1,3-4' (default: all)")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=pages.rotate)

    p = sub.add_parser("reorder", help="reorder pages (exact permutation)")
    p.add_argument("input")
    p.add_argument("--order", required=True, help="e.g. '3,1,2'")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=pages.reorder)

    p = sub.add_parser("extract-pages", help="copy selected pages to a new PDF")
    p.add_argument("input")
    p.add_argument("--pages", required=True, help="e.g. '3,1' (order kept)")
    p.add_argument("--out", required=True)
    p.add_argument("--password")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=pages.extract_pages)

    return parser


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    command = (argv or sys.argv[1:2] or [""])[0]
    result = {"ok": False, "command": command, "data": None,
              "warnings": [], "error": None, "timing_ms": 0}
    exit_code = 0
    try:
        args = build_parser().parse_args(argv)
        result["command"] = args.command
        if args.command == "doctor":
            data, warnings = doctor.run(args)
        else:
            data, warnings = args.func(args)
        result.update(ok=True, data=data, warnings=warnings)
    except PdfToolError as exc:
        result["error"] = str(exc)
        exit_code = 2
    except Exception as exc:  # never leak a traceback to the user
        result["error"] = f"unexpected {type(exc).__name__}: {exc}"
        exit_code = 3
    result["timing_ms"] = int((time.perf_counter() - started) * 1000)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
