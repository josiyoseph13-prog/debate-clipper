"""Tests for the combined security gate (bin/gate_check.py).

Unit tests cover the decision rules, hashing, and record writing.
Integration tests run the real scanners (isolated venvs) against the
scanner-comparison synthetic corpus; they skip cleanly if the scanner
environments are absent.

Run: ~/workspace/tools/foundation-venv/bin/python -m pytest \
       ~/workspace/custom-skills/local-foundation-check/tests -v
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

BIN = Path(__file__).parent.parent / "bin"
sys.path.insert(0, str(BIN))
import gate_check  # noqa: E402

CORPUS = Path.home() / "workspace" / "scanner-comparison" / "corpus"
GATE = BIN / "gate_check.py"
PY = sys.executable

CLEAN_CISCO = {"version": "2.2.2", "is_safe": True, "max_severity": "INFO",
               "findings_count": 1, "rules": [], "credential_critical": False}
CLEAN_NVIDIA = {"version": "2.12.0", "score": 0, "severity": "LOW",
                "recommendation": "SAFE", "issues_count": 0, "categories": []}
FLAGGED_CISCO = dict(CLEAN_CISCO, is_safe=False, max_severity="CRITICAL",
                     findings_count=4, rules=["YARA_prompt_injection_generic"])
FLAGGED_NVIDIA = dict(CLEAN_NVIDIA, score=100, severity="CRITICAL",
                      recommendation="DO_NOT_INSTALL", issues_count=7)
CRED_CISCO = dict(FLAGGED_CISCO, rules=["YARA_credential_harvesting_generic"],
                  credential_critical=True)
ADJ_PASS = {"decision": "pass_with_notes", "rationale": "declared capability",
            "reviewer": "Pax", "date": "2026-10-10"}
ADJ_REJECT = {"decision": "reject", "rationale": "true threat",
              "reviewer": "Pax", "date": "2026-10-10"}


def make_skill(tmp_path, body=" benign instructions "):
    d = tmp_path / "skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: test-skill\ndescription: fixture\n---\n{body}\n")
    return d


# ---------- hashing ----------

def test_hash_stable_and_sensitive(tmp_path):
    d = make_skill(tmp_path)
    h1 = gate_check.content_hash(d)
    assert h1 == gate_check.content_hash(d)
    (d / "SKILL.md").write_text((d / "SKILL.md").read_text() + "changed\n")
    assert gate_check.content_hash(d) != h1


# ---------- decision rules ----------

def test_clean_passes():
    verdict, _ = gate_check.decide(CLEAN_CISCO, CLEAN_NVIDIA, None)
    assert verdict == "PASS"


def test_flagged_without_adjudication_holds():
    verdict, reasons = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA, None)
    assert verdict == "HOLD"
    assert any("adjudication required" in r for r in reasons)


def test_flagged_adjudicated_pass_with_notes():
    verdict, _ = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA, ADJ_PASS)
    assert verdict == "PASS_WITH_NOTES"


def test_flagged_adjudicated_reject():
    verdict, _ = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA, ADJ_REJECT)
    assert verdict == "REJECTED"


def test_false_positive_control_needs_adjudication():
    # Both scanners flag the benign teaching skill; only an adjudication
    # with a rationale may pass it — scores alone must not decide.
    verdict, _ = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA, None)
    assert verdict != "PASS"
    verdict, _ = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA,
                                   {"decision": "pass_with_notes"})
    assert verdict == "HOLD"  # rationale missing -> still not a pass


def test_credential_critical_quarantines():
    verdict, _ = gate_check.decide(CRED_CISCO, CLEAN_NVIDIA, ADJ_PASS)
    assert verdict == "QUARANTINE"  # pass_with_notes cannot wave it through


def test_quarantine_downgrade_needs_rationale():
    adj = {"decision": "downgrade_quarantine",
           "rationale": "verified public documentation example values",
           "reviewer": "Pax", "date": "2026-10-10"}
    verdict, _ = gate_check.decide(CRED_CISCO, CLEAN_NVIDIA, adj)
    assert verdict == "PASS_WITH_NOTES"
    adj2 = dict(adj, rationale="")
    verdict, _ = gate_check.decide(CRED_CISCO, CLEAN_NVIDIA, adj2)
    assert verdict == "QUARANTINE"


def test_scanner_failure_never_passes():
    for cisco, nvidia in ((None, CLEAN_NVIDIA), (CLEAN_CISCO, None),
                          (None, None)):
        verdict, reasons = gate_check.decide(cisco, nvidia, ADJ_PASS)
        assert verdict == "HOLD"
        assert any("scanner failure" in r for r in reasons)


# ---------- records ----------

def test_record_written_with_evidence(tmp_path):
    d = make_skill(tmp_path)
    out = tmp_path / "evals"
    verdict, reasons = gate_check.decide(FLAGGED_CISCO, FLAGGED_NVIDIA, None)
    path = gate_check.write_record(
        out, d, {"source": "https://example.invalid/skill",
                 "publisher": "Fixture", "ref": "v1"},
        FLAGGED_CISCO, FLAGGED_NVIDIA, None, verdict, reasons)
    fm = yaml.safe_load(path.read_text().split("---", 2)[1])
    assert fm["verdict"] == "HOLD"          # flagged, no adjudication on file
    assert fm["adjudication"] is None       # missing evidence is visible
    assert fm["content_hash"].startswith("sha256:")
    assert fm["unresolved_risks"]           # standing caveats recorded
    assert fm["pinned_ref"] == "v1"


# ---------- integration: real scanners on the synthetic corpus ----------

def scanners_present():
    return (Path(gate_check.CISCO_BIN).exists()
            and Path(gate_check.NVIDIA_BIN).exists()
            and CORPUS.is_dir())


def run_gate(args, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    return subprocess.run([PY, str(GATE)] + args, capture_output=True,
                          text=True, env=env, timeout=600)


@pytest.mark.skipif(not scanners_present(), reason="scanner venvs absent")
def test_integration_clean_skill_passes_and_verifies(tmp_path):
    out = tmp_path / "evals"
    r = run_gate(["evaluate", str(CORPUS / "clean-baseline"),
                  "--source", "fixture://corpus", "--publisher", "Pax",
                  "--ref", "round1", "--out", str(out)])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "verdict: PASS" in r.stdout
    record = out / "clean-baseline.md"
    v = run_gate(["verify", str(record), str(CORPUS / "clean-baseline")])
    assert v.returncode == 0 and "MATCH" in v.stdout


@pytest.mark.skipif(not scanners_present(), reason="scanner venvs absent")
def test_integration_changed_hash_voids_verdict(tmp_path):
    import shutil
    skill = tmp_path / "mutable-skill"
    shutil.copytree(CORPUS / "clean-baseline", skill)
    out = tmp_path / "evals"
    r = run_gate(["evaluate", str(skill), "--source", "fixture://corpus",
                  "--publisher", "Pax", "--ref", "round1", "--out", str(out)])
    assert "verdict: PASS" in r.stdout
    (skill / "SKILL.md").write_text(
        (skill / "SKILL.md").read_text() + "\nOne quiet change.\n")
    v = run_gate(["verify", str(out / "mutable-skill.md"), str(skill)])
    assert v.returncode == 2 and "CHANGED" in v.stdout


@pytest.mark.skipif(not scanners_present(), reason="scanner venvs absent")
def test_integration_malicious_fixture_not_passed(tmp_path):
    out = tmp_path / "evals"
    r = run_gate(["evaluate", str(CORPUS / "prompt-injection"),
                  "--source", "fixture://corpus", "--publisher", "Pax",
                  "--ref", "round1", "--out", str(out)])
    assert "verdict: PASS" not in r.stdout
    assert "verdict: HOLD" in r.stdout  # flagged, no adjudication supplied
    adj = tmp_path / "adj.json"
    adj.write_text(json.dumps(ADJ_REJECT))
    r2 = run_gate(["evaluate", str(CORPUS / "prompt-injection"),
                   "--source", "fixture://corpus", "--publisher", "Pax",
                   "--ref", "round1", "--out", str(out),
                   "--adjudication", str(adj)])
    assert "verdict: REJECTED" in r2.stdout


@pytest.mark.skipif(not scanners_present(), reason="scanner venvs absent")
def test_integration_scanner_failure_holds(tmp_path):
    out = tmp_path / "evals"
    r = run_gate(["evaluate", str(CORPUS / "clean-baseline"),
                  "--source", "fixture://corpus", "--publisher", "Pax",
                  "--ref", "round1", "--out", str(out)],
                 env_extra={"GATE_CISCO_BIN": "/bin/false"})
    assert "verdict: HOLD" in r.stdout
    assert "scanner failure" in r.stdout
