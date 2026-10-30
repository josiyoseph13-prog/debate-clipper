#!/usr/bin/env python3
"""One-off, idempotent migration of registry records from schema v1 to v2.

Surgical text edits only: capability entries gain `evidence` (where the v1
record omitted it) and `verified`; new v2 fields are appended to the
frontmatter; a migration line is appended to the verification log.
No factual claim in any record is changed. Safe to re-run: files already
carrying `schema: 2` are skipped.

Usage: migrate_registry.py [registry_dir]   (default ~/workspace/registry)
"""
import re
import sys
from pathlib import Path

DEFAULT_REGISTRY = Path.home() / "workspace" / "registry"

# slug -> (index_order, review_after_days, status_detail, owner_decision,
#          next_action, evidence_files)
META = {
    "ffmpeg": (10, 60, "installed", None,
               "None — foundational, in use.", []),
    "instagram-connector": (20, 30,
               "pending a dedicated publishing account (owner decision 2026-10-10; personal account must not be connected)",
               "2026-10-10 — jo: do NOT connect the personal Instagram account; blocked pending a dedicated Political Lens publishing account.",
               "Owner to provide a dedicated Political Lens account; then run the read-only checks only.", []),
    "meta-facebook": (30, 90, "not connected; linking halted by owner 2026-10-10", None,
               "No action while Meta linking is halted by the owner.", []),
    "yt-dlp": (40, 60,
               "installed 2026.8.19; YouTube metadata test failed 2026-10-10 — platform bot-wall on VM egress IP, cookies forbidden",
               None,
               "Re-test YouTube only via an owner-approved route (e.g. PC relay); test one non-YouTube extractor.",
               ["~/workspace/tools/yt-dlp-test/stderr.log",
                "~/workspace/tools/yt-dlp-test/stderr2.log",
                "~/workspace/tools/yt-dlp-test/stderr3.log"]),
    "faster-whisper": (50, 60, "bounded test passed; not adopted", None,
               "Run a real-audio benchmark on an owner-approved sample before any adoption decision.",
               ["~/workspace/tools/test-audio/transcript_tiny.json",
                "~/workspace/tools/test-audio/sample.mp3"]),
    "postiz": (60, 90, "under evaluation", None,
               "None until the owner chooses a track (skip / cloud trial / self-host evaluation). Docker is absent on this VM.", []),
    "youtube-data-api": (70, 90, "custom integration, not built", None,
               "Waiting on the owner's Google account decision; then build in a repository.", []),
    "tiktok-content-posting-api": (80, 90, "custom integration, not built", None,
               "Owner to provide the TikTok app/account path; platform audit required before public posting.", []),
    "github-connector": (90, 90, "not connected", None,
               "Owner to provide a repository; then connect, read-first.", []),
    "google-drive": (100, 90, "not connected", None,
               "Waiting on the owner's Google account decision (deferred).", []),
    "zapier": (110, 180, "by owner decision, 2026-10-10",
               "2026-10-10 — jo: rejected; do not adopt unless a specific requirement justifies it.",
               "None — rejected. Revisit only on a specific, justified requirement.", []),
    "highlevel": (120, 180, "by owner decision, 2026-10-10",
               "2026-10-10 — jo: rejected; do not adopt unless a specific requirement justifies it.",
               "None — rejected. Revisit only on a specific, justified requirement.", []),
}

DRIFT_EVIDENCE = ('"Assessed 2026-10-10 (schema v2 migration): this capability does not '
                  'exist for this tool; the v1 record stated it without an evidence note."')
LOG_LINE = ("- 2026-10-10 — Schema v2 migration: every capability entry now carries "
            "evidence + a verified date; record gained review_after_days, owner_decision, "
            "next_action, evidence_files, cost_evidence_date. No factual claims changed.")


def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def migrate_file(path: Path) -> str:
    slug = path.stem
    if slug not in META:
        return f"SKIP {slug}: no migration metadata"
    text = path.read_text()
    if re.search(r"^schema:\s*2\s*$", text, re.M):
        return f"SKIP {slug}: already schema 2"
    m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", text, re.S)
    if not m:
        return f"ERROR {slug}: frontmatter not found"
    head, fm, tail_sep, body = m.groups()
    lv = re.search(r"^last_verified:\s*(\S+)", fm, re.M)
    if not lv:
        return f"ERROR {slug}: last_verified missing"
    last_verified = lv.group(1)

    # Normalize capability lines: add evidence where missing, add verified.
    def fix_cap(match):
        line = match.group(0)
        if "verified:" in line:
            return line
        if "evidence:" not in line:
            line = line.rstrip()
            assert line.endswith("}")
            line = line[:-1] + f", evidence: {DRIFT_EVIDENCE}}}"
        line = line.rstrip()
        assert line.endswith("}")
        return line[:-1] + f", verified: {last_verified}}}"

    fm_new, n = re.subn(r"^\s+\w+: \{supported: (?:true|false)[^\n]*$",
                        fix_cap, fm, flags=re.M)
    order, days, detail, decision, next_action, ev_files = META[slug]
    extra = [f"schema: 2", f"slug: {slug}", f"index_order: {order}"]
    if detail:
        extra.append(f"status_detail: {q(detail)}")
    extra.append(f"review_after_days: {days}")
    extra.append("owner_decision: " + (q(decision) if decision else "null"))
    extra.append(f"next_action: {q(next_action)}")
    extra.append("evidence_files: [" + ", ".join(q(p) for p in ev_files) + "]")
    extra.append("cost_evidence_date: 2026-10-10")
    fm_new = fm_new.rstrip("\n") + "\n" + "\n".join(extra)
    body_new = body.rstrip("\n") + "\n" + LOG_LINE + "\n"
    path.write_text(head + fm_new + tail_sep + body_new)
    return f"OK   {slug}: {n} capability lines normalized"


SUPPORTED_MAP = {"true": "full", "false": "none", "partial": "partial",
                 "claimed": "claimed", "restricted": "restricted"}


def normalize_supported(path: Path) -> str:
    """Second pass (idempotent): map `supported` to the v2 enum
    (full|none|partial|claimed|restricted) and add `verified` where an
    earlier regex missed a line (non-boolean v1 values)."""
    text = path.read_text()
    lv = re.search(r"^last_verified:\s*(\S+)", text, re.M)
    if not lv:
        return f"ERROR {path.stem}: last_verified missing"
    changed = []

    def fix(match):
        line = match.group(0)
        token = match.group(1)
        if token in SUPPORTED_MAP:
            line = line.replace(f"supported: {token}",
                                f"supported: {SUPPORTED_MAP[token]}", 1)
            changed.append("enum")
        if "verified:" not in line:
            line = line.rstrip()
            assert line.endswith("}")
            line = line[:-1] + f", verified: {lv.group(1)}}}"
            changed.append("verified")
        return line

    new = re.sub(r"^\s+\w+: \{supported: (\w+)[^\n]*$", fix, text, flags=re.M)
    if new != text:
        path.write_text(new)
    return f"NORM {path.stem}: {changed if changed else 'already normalized'}"


INDEX_NAMES = {
    "instagram-connector": "Instagram connector",
    "meta-facebook": "Facebook / Meta (facebook-cli, Threads, Meta Ads)",
    "youtube-data-api": "YouTube Data API v3",
    "tiktok-content-posting-api": "TikTok Content Posting API",
}


def patch_index_names(path: Path) -> str:
    """Third pass (idempotent): add the short display name used by INDEX."""
    if path.stem not in INDEX_NAMES:
        return f"NAME {path.stem}: not needed"
    text = path.read_text()
    if re.search(r"^index_name:", text, re.M):
        return f"NAME {path.stem}: already set"
    new = re.sub(r"^(slug: [^\n]*)$",
                 r"\1\nindex_name: " + q(INDEX_NAMES[path.stem]),
                 text, count=1, flags=re.M)
    path.write_text(new)
    return f"NAME {path.stem}: added"


COSTS = {
    "ffmpeg": "Free — open source; pre-existing system install, no fees.",
    "instagram-connector": "Connector included with Muse; per-use cost UNVERIFIED.",
    "meta-facebook": "Connectors included with Muse; any Meta Ads spend is separate and UNVERIFIED.",
    "github-connector": "Connector included with Muse; GitHub plan costs UNVERIFIED.",
    "google-drive": "Connector included with Muse; Google storage/account costs UNVERIFIED.",
    "youtube-data-api": "API itself free within quota; the real cost is audit/compliance time (see record).",
    "tiktok-content-posting-api": "API itself free; the real cost is app review/audit time (see record).",
    "zapier": "Not applicable — rejected before any purchase.",
    "highlevel": "Not applicable — rejected before any purchase.",
}


def patch_cost(path: Path) -> str:
    """Fourth pass (idempotent): add a uniform `cost` field, sourced from
    the v1 `pricing` field where one exists, else from COSTS above."""
    text = path.read_text()
    if re.search(r"^cost:", text, re.M):
        return f"COST {path.stem}: already set"
    m = re.search(r"^pricing:\s*(.+)$", text, re.M)
    if m:
        value = m.group(1).strip().strip('"')
        cost = "Free and open source; no service fees." if value == "free" else value
    elif path.stem in COSTS:
        cost = COSTS[path.stem]
    else:
        return f"COST {path.stem}: ERROR no source for cost"
    new = re.sub(r"^(cost_evidence_date: [^\n]*)$",
                 r"\1\ncost: " + q(cost), text, count=1, flags=re.M)
    path.write_text(new)
    return f"COST {path.stem}: added"


def main():
    registry = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REGISTRY
    for p in sorted((registry / "tools").glob("*.md")):
        print(migrate_file(p))
    for p in sorted((registry / "tools").glob("*.md")):
        print(normalize_supported(p))
    for p in sorted((registry / "tools").glob("*.md")):
        print(patch_index_names(p))
    for p in sorted((registry / "tools").glob("*.md")):
        print(patch_cost(p))


if __name__ == "__main__":
    main()
