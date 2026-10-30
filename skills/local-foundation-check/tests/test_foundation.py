"""Tests for the foundation-check skill (validator, generator, probes).

Run: ~/workspace/tools/foundation-venv/bin/python -m pytest \
       ~/workspace/custom-skills/local-foundation-check/tests -v
"""
import sys
from datetime import date, timedelta
from pathlib import Path

BIN = Path(__file__).parent.parent / "bin"
sys.path.insert(0, str(BIN))

from registry_lib import load_records, render_index, validate  # noqa: E402
from foundation_check import probe  # noqa: E402

RECORD = """---
name: Test Tool
slug: {slug}
index_name: Test Tool
index_order: 10
official_url: https://example.com/
vendor: Example
category: testing
version: "1.0"
license: MIT
status: tested
status_detail: "fixture"
capabilities:
  read: {{supported: full, label: VERIFIED, evidence: "fixture evidence", verified: {verified}}}
  publish: {{supported: none, label: VERIFIED, evidence: "fixture evidence", verified: {verified}}}
permissions_required: none
sensitive_data: none
dependencies: []
resource_requirements: none
security_risks: none
compatibility: fixture
test_procedure: "fixture"
expected_result: "fixture"
actual_result: "fixture"
last_verified: {verified}
failure_history: []
decision_rationale: "fixture"
alternatives_considered: "none"
rollback_plan: "n/a"
schema: 2
review_after_days: {days}
owner_decision: null
next_action: "None."
evidence_files: []
cost_evidence_date: {verified}
cost: "Free."
---

# Test Tool

Verification log:
- fixture entry
"""


def make_registry(tmp_path, body=None, slug="test-tool", verified=None,
                  days=90):
    verified = verified or date.today().isoformat()
    reg = tmp_path / "registry"
    (reg / "tools").mkdir(parents=True)
    text = body if body is not None else RECORD.format(
        slug=slug, verified=verified, days=days)
    (reg / "tools" / f"{slug}.md").write_text(text)
    (reg / "INDEX.md").write_text(
        "# Index\n\n[test-tool](tools/test-tool.md)\n")
    (reg / "CHANGELOG.md").write_text("# Changelog\n")
    (reg / "PUBLISHING_POLICY.md").write_text("# Policy\n")
    return reg


def test_valid_registry_passes(tmp_path):
    errors, warnings = validate(make_registry(tmp_path))
    assert errors == []
    assert warnings == []


def test_missing_required_field_fails(tmp_path):
    body = RECORD.format(slug="test-tool",
                         verified=date.today().isoformat(), days=90)
    body = body.replace('next_action: "None."\n', "")
    errors, _ = validate(make_registry(tmp_path, body=body))
    assert any("next_action" in e for e in errors)


def test_capability_without_evidence_fails(tmp_path):
    # The actual schema-v1 drift found in the real registry on 2026-10-10.
    body = RECORD.format(slug="test-tool",
                         verified=date.today().isoformat(), days=90)
    body = body.replace(
        'publish: {supported: none, label: VERIFIED, evidence: '
        '"fixture evidence", verified:',
        'publish: {supported: none, label: VERIFIED, verified:')
    errors, _ = validate(make_registry(tmp_path, body=body))
    assert any("publish" in e for e in errors)


def test_duplicate_slug_fails(tmp_path):
    reg = make_registry(tmp_path)
    other = RECORD.format(slug="test-tool",
                          verified=date.today().isoformat(), days=90)
    (reg / "tools" / "test-tool.md").write_text(other)
    (reg / "tools" / "second.md").write_text(
        other.replace("slug: test-tool", "slug: second"))
    # 'second' file has slug second but same name -> duplicate name error
    errors, _ = validate(reg)
    assert any("duplicate" in e for e in errors)


def test_broken_link_fails(tmp_path):
    reg = make_registry(tmp_path)
    (reg / "INDEX.md").write_text("[gone](tools/does-not-exist.md)\n")
    errors, _ = validate(reg)
    assert any("broken link" in e for e in errors)


def test_missing_evidence_file_fails(tmp_path):
    body = RECORD.format(slug="test-tool",
                         verified=date.today().isoformat(), days=90)
    body = body.replace("evidence_files: []",
                          'evidence_files: ["/nonexistent/proof.log"]')
    errors, _ = validate(make_registry(tmp_path, body=body))
    assert any("evidence_file missing" in e for e in errors)


def test_stale_record_warns_not_fails(tmp_path):
    old = (date.today() - timedelta(days=200)).isoformat()
    reg = make_registry(tmp_path, verified=old, days=90)
    errors, warnings = validate(reg)
    assert errors == []
    assert any("STALE" in w for w in warnings)


def test_bad_status_fails(tmp_path):
    body = RECORD.format(slug="test-tool",
                         verified=date.today().isoformat(), days=90)
    body = body.replace("status: tested", "status: sort-of-works")
    errors, _ = validate(make_registry(tmp_path, body=body))
    assert any("status" in e for e in errors)


def test_generator_renders_record_row(tmp_path):
    reg = make_registry(tmp_path)
    out = render_index(load_records(reg))
    assert "| Test Tool | testing | tested (fixture) |" in out
    assert "[test-tool](tools/test-tool.md)" in out
    assert "GENERATED" in out


def test_generator_blocked_rendering(tmp_path):
    body = RECORD.format(slug="test-tool",
                         verified=date.today().isoformat(), days=90)
    body = body.replace("status: tested", "status: blocked")
    reg = make_registry(tmp_path, body=body)
    out = render_index(load_records(reg))
    assert "**blocked** — fixture" in out


def test_probe_distinguishes_missing_binary():
    state, _ = probe(["definitely-not-a-real-binary-xyz123", "--version"])
    assert state == "UNAVAILABLE"
    state, detail = probe(["python3", "--version"])
    assert state == "OK" and "Python" in detail


def test_real_registry_is_valid():
    real = Path.home() / "workspace" / "registry"
    errors, _ = validate(real)
    assert errors == [], f"real registry must stay valid: {errors}"
