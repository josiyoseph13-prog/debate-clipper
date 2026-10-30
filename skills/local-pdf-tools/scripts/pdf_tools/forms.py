"""forms — list AcroForm fields and fill them from a JSON data file.

Filling validates every key in the data file against the document's
actual fields first: an unknown field is a clean error, not a silent
partial fill. Booleans in the data file map to checkbox states
(true -> /Yes, false -> /Off); other values are written as strings.
NeedAppearances is set so viewers render the filled values.
"""
from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfWriter

from .common import (PdfToolError, open_reader, sha256_file,
                     validate_input_pdf, validate_output)

_FIELD_TYPES = {"/Tx": "text", "/Btn": "button/checkbox",
                "/Ch": "choice", "/Sig": "signature"}


def _field_summary(fields: dict) -> list[dict]:
    summary = []
    for name, field in fields.items():
        ftype = str(field.get("/FT", ""))
        value = field.get("/V")
        summary.append({
            "name": name,
            "type": _FIELD_TYPES.get(ftype, ftype or "unknown"),
            "value": None if value is None else str(value),
        })
    return summary


def list_fields(args) -> tuple[dict, list[str]]:
    path = validate_input_pdf(args.input)
    reader = open_reader(path, args.password)
    fields = reader.get_fields() or {}
    data = {"file": str(path), "field_count": len(fields),
            "fields": _field_summary(fields)}
    warnings = [] if fields else ["no form fields found in this PDF"]
    return data, warnings


def fill(args) -> tuple[dict, list[str]]:
    src = validate_input_pdf(args.input)
    data_path = Path(args.data).expanduser()
    if not data_path.is_file():
        raise PdfToolError(f"data file not found: {data_path}")
    try:
        values = json.loads(data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PdfToolError(f"data file is not valid JSON: {exc}") from exc
    if not isinstance(values, dict) or not values:
        raise PdfToolError("data file must be a non-empty JSON object "
                           "of field-name -> value")
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.password)
    fields = reader.get_fields() or {}
    if not fields:
        raise PdfToolError("this PDF has no form fields to fill")
    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise PdfToolError(
            f"unknown field(s): {unknown}; "
            f"document fields: {sorted(fields)}")

    normalized = {}
    for key, value in values.items():
        if value is True:
            normalized[key] = "/Yes"
        elif value is False:
            normalized[key] = "/Off"
        elif value is None:
            normalized[key] = ""
        else:
            normalized[key] = str(value)

    writer = PdfWriter()
    writer.append(reader)
    writer.set_need_appearances_writer(True)
    for page in writer.pages:
        writer.update_page_form_field_values(page, normalized)
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()

    # verify by reading the values back from the written file
    check = open_reader(out, None).get_fields() or {}
    filled = {k: (None if check.get(k, {}).get("/V") is None
                  else str(check[k]["/V"])) for k in normalized}
    data = {"out": str(out), "fields_filled": sorted(normalized),
            "values_read_back": filled,
            "out_sha256": sha256_file(out)}
    return data, []
