from __future__ import annotations

import re
from typing import Any


def metadata_pack(source: dict[str, Any], candidate: dict[str, Any], headline: str) -> dict[str, Any]:
    source_url = source.get("source_url") or source.get("meta", {}).get("webpage_url")
    topic_words = [word for word in re.findall(r"[A-Za-z]{4,}", candidate.get("text", "").lower()) if word not in {"that", "this", "with", "from", "they", "have", "will"}]
    tags = ["#debate", "#politics", "#politicallens"] + [f"#{word}" for word in dict.fromkeys(topic_words[:5])]
    return {"schema_version": 5, "title": headline, "titles": candidate.get("hook", {}).get("headline_options", []), "description": f"Watch the full exchange: {source_url or source.get('path')} at {candidate.get('start', 0):.2f}s.", "hashtags": tags[:8], "pinned_comment": "Which side made the stronger case?", "source_url": source_url, "source_timestamp": candidate.get("start"), "speaker_attribution": "Unknown unless manually labeled", "rights_class": source.get("rights_class", "unknown")}
