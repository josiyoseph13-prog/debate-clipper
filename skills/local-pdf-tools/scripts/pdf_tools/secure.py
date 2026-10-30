"""secure — encrypt and decrypt PDFs (pypdf AES-256 via cryptography).

Both commands write a NEW file and then verify it: an encrypted output
must actually require (and accept) the password; a decrypted output
must open with no password. Verification results are in the JSON data.
"""
from __future__ import annotations

from pypdf import PdfReader, PdfWriter

from .common import (PdfToolError, open_reader, sha256_file,
                     validate_input_pdf, validate_output)


def _copy_pages(reader: PdfReader, out) -> PdfWriter:
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(out, "wb") as fh:
        writer.write(fh)
    return writer


def encrypt(args) -> tuple[dict, list[str]]:
    if not args.password:
        raise PdfToolError("encrypt requires --password")
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    reader = open_reader(src, args.input_password)
    writer = PdfWriter()
    count = 0
    for page in reader.pages:
        writer.add_page(page)
        count += 1
    writer.encrypt(user_password=args.password,
                   owner_password=args.owner_password or args.password,
                   algorithm="AES-256")
    with open(out, "wb") as fh:
        writer.write(fh)
    writer.close()

    check = PdfReader(str(out))
    verified = bool(check.is_encrypted)
    if verified:
        verified = int(check.decrypt(args.password)) != 0
    warnings = []
    if len(args.password) < 8:
        warnings.append("password is short (< 8 characters)")
    data = {"out": str(out), "pages_out": count, "algorithm": "AES-256",
            "verified_encrypted": verified,
            "out_sha256": sha256_file(out)}
    if not verified:
        raise PdfToolError("verification failed: output is not properly "
                           "encrypted")
    return data, warnings


def decrypt(args) -> tuple[dict, list[str]]:
    if not args.password:
        raise PdfToolError("decrypt requires --password")
    src = validate_input_pdf(args.input)
    out = validate_output(args.out, args.overwrite, [src])
    probe = PdfReader(str(src))
    if not probe.is_encrypted:
        raise PdfToolError(f"{src.name} is not encrypted")
    reader = open_reader(src, args.password)  # wrong password errors here
    writer = _copy_pages(reader, out)
    writer.close()
    check = PdfReader(str(out))
    verified = not check.is_encrypted
    data = {"out": str(out), "pages_out": len(check.pages),
            "verified_unencrypted": verified,
            "out_sha256": sha256_file(out)}
    if not verified:
        raise PdfToolError("verification failed: output is still encrypted")
    return data, []
