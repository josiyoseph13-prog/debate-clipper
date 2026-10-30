"""doctor — report library versions, binaries, and feature availability."""
from __future__ import annotations

import importlib.metadata
import platform
import shutil

CORE_LIBS = ["pypdf", "pdfplumber", "pdfminer.six", "Pillow", "reportlab",
             "cryptography"]
OPTIONAL_LIBS = ["pikepdf", "pypdfium2", "pytesseract"]
BINARIES = ["pdftotext", "pdfinfo", "pdftoppm", "pdfimages",
            "tesseract", "gs", "qpdf"]


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def run(_args) -> tuple[dict, list[str]]:
    libraries = {name: _version(name) for name in CORE_LIBS + OPTIONAL_LIBS}
    binaries = {name: shutil.which(name) for name in BINARIES}
    core_ok = all(libraries[name] for name in CORE_LIBS)
    features = {
        "inspect": core_ok,
        "extract_text": libraries["pdfplumber"] is not None,
        "extract_tables": libraries["pdfplumber"] is not None,
        "page_operations": libraries["pypdf"] is not None,
        "create": libraries["reportlab"] is not None,
        "forms": libraries["pypdf"] is not None,
        "watermark": libraries["reportlab"] is not None,
        "encrypt_decrypt": libraries["cryptography"] is not None,
        "metadata_edit": libraries["pypdf"] is not None,
        "compress_basic": libraries["pypdf"] is not None,
        "optimize_tier_pikepdf": libraries["pikepdf"] is not None,
        "ocr_tier": binaries["tesseract"] is not None,
    }
    warnings: list[str] = []
    if not features["ocr_tier"]:
        warnings.append("OCR unavailable: tesseract binary not installed "
                        "(optional tier, by design)")
    if not features["optimize_tier_pikepdf"]:
        warnings.append("pikepdf not installed: advanced optimize tier "
                        "unavailable (optional)")
    data = {
        "python": platform.python_version(),
        "libraries": libraries,
        "binaries": {k: (v is not None) for k, v in binaries.items()},
        "core_ok": core_ok,
        "features": features,
    }
    return data, warnings
