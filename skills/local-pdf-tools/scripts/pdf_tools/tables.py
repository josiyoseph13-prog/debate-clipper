"""extract-tables — pdfplumber table detection, per page, page-by-page.

JSON (default) returns every table's rows. --out file.csv writes all
tables stacked with leading `page` / `table` columns; --out file.json
writes the same structure as the JSON result.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pdfplumber

from .common import (PdfToolError, open_reader, parse_pages_spec,
                     sha256_file, validate_input_pdf, validate_output)


def run(args) -> tuple[dict, list[str]]:
    path = validate_input_pdf(args.input)
    reader = open_reader(path, args.password)
    page_count = len(reader.pages)
    wanted = (parse_pages_spec(args.pages, page_count) if args.pages
              else list(range(1, page_count + 1)))

    warnings: list[str] = []
    try:
        pdf = pdfplumber.open(str(path), password=args.password or "")
    except Exception as exc:
        raise PdfToolError(f"could not open PDF for tables: {exc}") from exc

    pages_data: list[dict] = []
    table_total = 0
    with pdf:
        for page_no in wanted:
            page = pdf.pages[page_no - 1]
            page_tables = []
            try:
                found = page.find_tables() or []
                for table in found:
                    rows = [[("" if cell is None else str(cell))
                             for cell in row]
                            for row in (table.extract() or [])]
                    page_tables.append({
                        "rows": rows,
                        "row_count": len(rows),
                        "col_count": max((len(r) for r in rows), default=0),
                    })
            except Exception as exc:  # isolate per-page failures
                warnings.append(
                    f"page {page_no}: table extraction failed "
                    f"({type(exc).__name__})")
            table_total += len(page_tables)
            pages_data.append({"page": page_no, "tables": page_tables})

    data: dict = {"file": str(path), "page_count": page_count,
                  "tables_total": table_total, "pages": pages_data}
    if args.out:
        out = validate_output(args.out, args.overwrite, [path])
        if out.suffix.lower() == ".json":
            payload = {"file": data["file"], "pages": pages_data}
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        elif out.suffix.lower() == ".csv":
            with open(out, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                for pdata in pages_data:
                    for t_idx, table in enumerate(pdata["tables"], start=1):
                        for row in table["rows"]:
                            writer.writerow([pdata["page"], t_idx, *row])
        else:
            raise PdfToolError("--out must end in .json or .csv")
        data["out"] = str(out)
        data["out_sha256"] = sha256_file(out)
        del data["pages"]  # content lives in the file now
    return data, warnings
