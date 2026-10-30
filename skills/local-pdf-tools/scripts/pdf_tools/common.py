"""Shared plumbing: errors, validation, page-spec parsing, safe IO.

Safety rules enforced here for every command:
- inputs must exist and look like PDFs;
- outputs are new files: they must not exist unless --overwrite is
  given, and must never be one of the inputs (originals are sacred);
- encrypted inputs need an explicit --password; wrong passwords and
  malformed files produce clean errors, never tracebacks.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfToolError(Exception):
    """A user-facing error; the CLI turns it into a JSON error result."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def validate_input_pdf(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.exists():
        raise PdfToolError(f"input not found: {p}")
    if not p.is_file():
        raise PdfToolError(f"input is not a file: {p}")
    if p.suffix.lower() != ".pdf":
        raise PdfToolError(f"input is not a .pdf file: {p}")
    return p


def validate_output(path_str: str, overwrite: bool, inputs: list[Path]) -> Path:
    p = Path(path_str).expanduser()
    if not p.parent.exists():
        raise PdfToolError(f"output directory does not exist: {p.parent}")
    resolved = p.resolve()
    for inp in inputs:
        if resolved == inp.resolve():
            raise PdfToolError("output must not overwrite an input PDF")
    if p.exists() and not overwrite:
        raise PdfToolError(
            f"output already exists: {p} (pass --overwrite to replace it)")
    return p


def open_reader(path: Path, password: str | None) -> PdfReader:
    """Open a PDF, decrypting if needed; clean errors for bad files."""
    try:
        reader = PdfReader(str(path))
    except (PdfReadError, Exception) as exc:  # pypdf raises several types
        raise PdfToolError(f"could not read PDF {path.name}: {exc}") from exc
    if reader.is_encrypted:
        if not password:
            raise PdfToolError(
                f"{path.name} is encrypted: pass --password to open it")
        try:
            result = reader.decrypt(password)
        except Exception as exc:
            raise PdfToolError(
                f"could not decrypt {path.name}: {exc}") from exc
        if int(result) == 0:
            raise PdfToolError(f"wrong password for {path.name}")
    return reader


def open_reader_lenient(path: Path) -> PdfReader:
    """Open without decrypting (for encryption-status inspection)."""
    try:
        return PdfReader(str(path))
    except Exception as exc:
        raise PdfToolError(f"could not read PDF {path.name}: {exc}") from exc


def _parse_page_token(token: str, page_count: int) -> list[int]:
    token = token.strip()
    if not token:
        raise PdfToolError("empty page spec element")
    if "-" in token:
        lo_s, hi_s = token.split("-", 1)
        try:
            lo, hi = int(lo_s), int(hi_s)
        except ValueError:
            raise PdfToolError(f"invalid page range: '{token}'") from None
        if lo < 1 or hi < lo or hi > page_count:
            raise PdfToolError(
                f"page range '{token}' out of bounds (document has "
                f"{page_count} pages)")
        return list(range(lo, hi + 1))
    try:
        n = int(token)
    except ValueError:
        raise PdfToolError(f"invalid page number: '{token}'") from None
    if n < 1 or n > page_count:
        raise PdfToolError(
            f"page {n} out of bounds (document has {page_count} pages)")
    return [n]


def parse_pages_spec(spec: str, page_count: int) -> list[int]:
    """'1-3,5' -> [1,2,3,5]; order preserved, duplicates allowed."""
    pages: list[int] = []
    for token in spec.split(","):
        pages.extend(_parse_page_token(token, page_count))
    if not pages:
        raise PdfToolError("page spec selects no pages")
    return pages


def parse_chunks_spec(spec: str, page_count: int) -> list[list[int]]:
    """'1-2,3' -> [[1,2],[3]]; one chunk per comma element (for split)."""
    chunks = []
    for token in spec.split(","):
        chunks.append(_parse_page_token(token, page_count))
    if not chunks:
        raise PdfToolError("split spec selects nothing")
    return chunks


def parse_order_spec(spec: str, page_count: int) -> list[int]:
    """'3,1,2' -> [3,1,2]; must be an exact permutation of 1..page_count."""
    try:
        order = [int(t.strip()) for t in spec.split(",")]
    except ValueError:
        raise PdfToolError(f"invalid order spec: '{spec}'") from None
    if sorted(order) != list(range(1, page_count + 1)):
        raise PdfToolError(
            f"order must list every page 1..{page_count} exactly once")
    return order
