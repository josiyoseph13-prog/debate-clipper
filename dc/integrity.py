from __future__ import annotations

from typing import Any

from .selection import can_auto_approve, integrity_flags


def verify_claims(candidate: dict[str, Any], checked: dict[int | str, dict[str, Any]] | None = None) -> dict[str, Any]:
    checked = checked or {}
    result = dict(candidate)
    claims = []
    for claim in candidate.get("claims", []):
        value = dict(claim)
        update = checked.get(claim.get("word_i"), checked.get(str(claim.get("word_i")), {}))
        value.update(update)
        claims.append(value)
    result["claims"] = claims
    result["claim_checked"] = bool(claims) and all(item.get("claim_checked") for item in claims) or not claims
    result["integrity_flags"] = [flag for flag in candidate.get("integrity_flags", []) if flag.get("code") != "I-7"]
    if not result["claim_checked"] and claims:
        result["integrity_flags"].append({"code": "I-7", "severity": "review", "reason": "One or more checkable claims are not verified by the user"})
    result["auto_allowed"] = can_auto_approve(result)
    return result


def publish_gate(candidate: dict[str, Any], source: dict[str, Any], config) -> tuple[bool, list[str]]:
    reasons = []
    if source.get("rights_class", "unknown") in set(config.get("distribution", "publish", "block_rights", default=["unknown"])):
        reasons.append("rights_class_unknown")
    if any(flag.get("severity") in set(config.get("distribution", "publish", "block_flags", default=["review", "block_auto_approve"])) for flag in candidate.get("integrity_flags", [])):
        reasons.append("integrity_review")
    if candidate.get("claims") and not candidate.get("claim_checked", False):
        reasons.append("claim_checked_missing")
    return not reasons, reasons
