"""Article extraction: trafilatura first, readability second,
BeautifulSoup plain-text last. Returns (fields, extractor_name)."""
from __future__ import annotations

import json

import trafilatura
from bs4 import BeautifulSoup
from readability import Document


def extract(html: str, url: str) -> tuple[dict, str]:
    # 1) trafilatura — best article text + metadata (date/author/title)
    try:
        raw = trafilatura.extract(html, url=url, output_format="json",
                                  with_metadata=True)
        if raw:
            data = json.loads(raw)
            if data.get("text") and len(data["text"]) >= 200:
                return {"title": data.get("title"),
                        "date_published": data.get("date"),
                        "author": data.get("author"),
                        "text": data["text"]}, "trafilatura"
    except Exception:
        pass
    # 2) readability — Mozilla-style article isolation
    try:
        doc = Document(html)
        summary_html = doc.summary()
        text = BeautifulSoup(summary_html, "lxml").get_text("\n").strip()
        if len(text) >= 200:
            return {"title": doc.title(), "date_published": None,
                    "author": None, "text": text}, "readability"
    except Exception:
        pass
    # 3) bs4 plain text — always available, weakest signal
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text("\n").strip()
    return {"title": title, "date_published": None, "author": None,
            "text": text}, "bs4-plain"
