#!/usr/bin/env python3
"""Shared library for the Pax capability registry (schema v2).

Used by validate_registry.py, generate_index.py and foundation_check.py.
Read-only: nothing in this module writes to the registry.
"""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

STATUSES = {"candidate", "available", "connected", "tested", "adopted",
            "blocked", "rejected", "deprecated"}
SUPPORTED_VALUES = {"full", "none", "partial", "claimed", "restricted"}
LABELS = {"VERIFIED", "DOCUMENTED", "UNVERIFIED", "UNSUPPORTED"}
CAPABILITY_KEYS = {"supported", "label", "evidence", "verified"}
REQUIRED_FIELDS = {
    "schema": int, "slug": str, "name": str, "category": str,
    "status": str, "capabilities": dict, "cost": str,
    "last_verified": (date, datetime), "review_after_days": int,
    "next_action": str, "evidence_files": list,
    "cost_evidence_date": (date, datetime),
}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def split_record(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    try:
        return yaml.safe_load(m.group(1)), text[m.end():]
    except yaml.YAMLError:
        return None, text


def load_records(registry: Path):
    """Return list of dicts: {path, data, body, parse_error}."""
    records = []
    tools_dir = registry / "tools"
    if not tools_dir.is_dir():
        return records
    for p in sorted(tools_dir.glob("*.md")):
        text = p.read_text()
        data, body = split_record(text)
        records.append({"path": p, "data": data, "body": body,
                        "parse_error": data is None})
    return records


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None


def check_links(registry: Path, records):
    """Every relative markdown link in registry docs must resolve."""
    errors = []
    docs = [registry / "INDEX.md", registry / "CHANGELOG.md",
            registry / "PUBLISHING_POLICY.md"]
    docs += [r["path"] for r in records]
    for doc in docs:
        if not doc.exists():
            continue
        for target in LINK_RE.findall(doc.read_text()):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#")[0]
            if not target:
                continue
            if not (doc.parent / target).exists():
                errors.append(f"{doc.name}: broken link -> {target}")
    return errors


def validate(registry: Path, today: date = None):
    """Return (errors, warnings) for the registry at `registry`."""
    today = today or date.today()
    errors, warnings = [], []
    records = load_records(registry)
    if not records:
        return [f"no records found under {registry}/tools"], warnings
    seen_slugs, seen_names = {}, {}
    for r in records:
        tag = r["path"].name
        if r["parse_error"]:
            errors.append(f"{tag}: frontmatter missing or unparseable YAML")
            continue
        d = r["data"]
        for field, types in REQUIRED_FIELDS.items():
            if field not in d:
                errors.append(f"{tag}: missing required field '{field}'")
            elif not isinstance(d[field], types):
                errors.append(f"{tag}: field '{field}' has wrong type "
                              f"({type(d[field]).__name__})")
        if d.get("schema") != 2:
            errors.append(f"{tag}: schema is {d.get('schema')!r}, expected 2")
        if d.get("slug") != r["path"].stem:
            errors.append(f"{tag}: slug {d.get('slug')!r} != filename stem "
                          f"{r['path'].stem!r}")
        if d.get("slug") in seen_slugs:
            errors.append(f"{tag}: duplicate slug also in "
                          f"{seen_slugs[d['slug']]}")
        seen_slugs[d.get("slug")] = tag
        if d.get("name") in seen_names:
            errors.append(f"{tag}: duplicate name also in "
                          f"{seen_names[d['name']]}")
        seen_names[d.get("name")] = tag
        if d.get("status") not in STATUSES:
            errors.append(f"{tag}: status {d.get('status')!r} not in enum")
        if "owner_decision" not in d:
            errors.append(f"{tag}: missing field 'owner_decision' "
                          f"(use null when none)")
        days = d.get("review_after_days")
        if isinstance(days, int) and not (1 <= days <= 365):
            errors.append(f"{tag}: review_after_days {days} out of range")
        caps = d.get("capabilities") or {}
        if not caps:
            errors.append(f"{tag}: capabilities is empty")
        for cap_name, cap in caps.items():
            if not isinstance(cap, dict) or set(cap) != CAPABILITY_KEYS:
                errors.append(f"{tag}: capability '{cap_name}' keys must be "
                              f"exactly {sorted(CAPABILITY_KEYS)}")
                continue
            if cap["supported"] not in SUPPORTED_VALUES:
                errors.append(f"{tag}: capability '{cap_name}' supported="
                              f"{cap['supported']!r} not in enum")
            if cap["label"] not in LABELS:
                errors.append(f"{tag}: capability '{cap_name}' label "
                              f"{cap['label']!r} not in enum")
            if not str(cap["evidence"]).strip():
                errors.append(f"{tag}: capability '{cap_name}' has empty "
                              f"evidence")
            if as_date(cap["verified"]) is None:
                errors.append(f"{tag}: capability '{cap_name}' verified "
                              f"is not a date")
        for ef in d.get("evidence_files") or []:
            if not Path(str(ef)).expanduser().exists():
                errors.append(f"{tag}: evidence_file missing: {ef}")
        lv = as_date(d.get("last_verified"))
        if lv is None:
            errors.append(f"{tag}: last_verified is not a date")
        elif isinstance(days, int) and lv + timedelta(days=days) < today:
            warnings.append(f"{tag}: STALE — last verified {lv}, review "
                            f"interval {days}d (due {lv + timedelta(days=days)})")
        if "Verification log:" not in r["body"]:
            warnings.append(f"{tag}: body has no 'Verification log:' section")
    errors += check_links(registry, records)
    return errors, warnings


def render_index(records):
    """Build INDEX.md content from record frontmatter (schema v2)."""
    rows = []
    ok = [r for r in records if not r["parse_error"]]
    for r in sorted(ok, key=lambda r: (r["data"].get("index_order", 9999),
                                       r["data"]["name"])):
        d = r["data"]
        display = d.get("index_name") or d["name"]
        detail = d.get("status_detail")
        if d["status"] == "blocked" and detail:
            status_cell = f"**blocked** — {detail}"
        elif detail:
            status_cell = f"{d['status']} ({detail})"
        else:
            status_cell = d["status"]
        lv = as_date(d.get("last_verified"))
        rows.append(f"| {display} | {d['category']} | {status_cell} | "
                    f"{lv.isoformat() if lv else '?'} | "
                    f"[{d['slug']}](tools/{d['slug']}.md) |")
    header = """# Capability Registry — Index

Owner: jo · Maintained by: Pax · Created: 2026-10-10

Status key: `candidate` (under evaluation) · `available` (exists in catalog, not connected) ·
`connected` (live status check passed) · `tested` (a real test produced evidence) ·
`adopted` (in regular use) · `rejected` · `deprecated`

Claims are labelled VERIFIED (directly inspected), DOCUMENTED (official docs/skill files),
UNVERIFIED (plausible, no evidence yet), or UNSUPPORTED (checked and not available).
A record's status only moves up when a dated verification-log entry supports it.

<!-- This table is GENERATED from tools/*.md frontmatter by
     skills/foundation-check/bin/generate_index.py — do not edit it by hand. -->

| Tool | Category | Status | Last verified | Record |
|---|---|---|---|---|
"""
    footer = """
Related planning record: [PUBLISHING_POLICY.md](PUBLISHING_POLICY.md)
Skill adoption procedure: [SECURITY_GATE.md](SECURITY_GATE.md)
Change history: [CHANGELOG.md](CHANGELOG.md)
"""
    return header + "\n".join(rows) + "\n" + footer
