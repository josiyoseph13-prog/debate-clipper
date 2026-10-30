#!/usr/bin/env python3
"""Combined security gate for candidate agent skills.

Implements the gate designed and trialled in
~/workspace/scanner-comparison/COMBINED_GATE.md:

  evaluate: hash the skill tree, run Cisco Skill Scanner (static) and
            NVIDIA SkillSpector (--no-llm) from their isolated venvs,
            apply the gate decision rules, and write an evaluation
            record (Markdown + YAML frontmatter).
  verify:   recompute a skill tree's hash and compare it with the hash
            recorded in an evaluation record (the rug-pull check).

Decision rules (see decide()):
  - any scanner failure            -> HOLD (never a pass)
  - Cisco credential CRITICAL       -> QUARANTINE (adjudication may
                                       downgrade only with a rationale)
  - content-threat flags            -> HOLD until adjudication;
                                       adjudicated -> PASS_WITH_NOTES or
                                       REJECTED
  - both scanners clean             -> PASS (with standing residual risks)

Scanner binaries can be overridden with GATE_CISCO_BIN / GATE_NVIDIA_BIN
(used by the tests to simulate scanner failure).

Usage:
  gate_check.py evaluate SKILL_DIR --source URL --publisher NAME \
      --ref VERSION_OR_COMMIT [--adjudication adjudication.json] \
      [--out DIR]
  gate_check.py verify EVALUATION.md SKILL_DIR
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

HOME = Path.home()
CISCO_BIN = os.environ.get(
    "GATE_CISCO_BIN",
    str(HOME / "workspace/scanner-comparison/envs/cisco-venv/bin/skill-scanner"))
NVIDIA_BIN = os.environ.get(
    "GATE_NVIDIA_BIN",
    str(HOME / "workspace/scanner-comparison/envs/nvidia-venv/bin/skillspector"))
DEFAULT_OUT = HOME / "workspace" / "registry" / "gate-evaluations"
SCAN_TIMEOUT = 300
RESIDUAL_RISKS = [
    "Static scanners provably miss indirect prompt injection and payloads "
    "hidden in referenced files (measured 2026-10-10); a PASS means no "
    "evidence found, not proven safe.",
    "LLM-based scanner modes were not used (no API keys); semantic "
    "detection is unevaluated.",
]


def content_hash(skill_dir: Path) -> str:
    """sha256 over sorted (relative path, bytes) of the whole tree."""
    h = hashlib.sha256()
    files = sorted(
        p for p in skill_dir.rglob("*")
        if p.is_file() and ".git" not in p.parts)
    for p in files:
        h.update(str(p.relative_to(skill_dir)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def skill_name(skill_dir: Path) -> str:
    md = skill_dir / "SKILL.md"
    if md.exists():
        text = md.read_text(errors="replace")
        if text.startswith("---"):
            try:
                fm = yaml.safe_load(text.split("---", 2)[1])
                if isinstance(fm, dict) and fm.get("name"):
                    return str(fm["name"])
            except yaml.YAMLError:
                pass
    return skill_dir.name


def run_cisco(skill_dir: Path):
    """Return a summary dict, or None on any failure."""
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "cisco.json"
            subprocess.run(
                [CISCO_BIN, "scan", str(skill_dir), "--format", "json",
                 "--output-json", str(out)],
                capture_output=True, text=True, timeout=SCAN_TIMEOUT)
            if not out.exists():
                return None
            d = json.loads(out.read_text())
        s = d.get("summary") if isinstance(d.get("summary"), dict) else d
        findings = s.get("findings") or d.get("findings") or []
        return {
            "version": "2.2.2",
            "is_safe": bool(s.get("is_safe")),
            "max_severity": s.get("max_severity"),
            "findings_count": s.get("findings_count", len(findings)),
            "rules": sorted({f.get("rule_id") for f in findings
                             if isinstance(f, dict) and f.get("rule_id")}),
            "credential_critical": any(
                isinstance(f, dict)
                and "credential" in str(f.get("rule_id", "")).lower()
                and f.get("severity") == "CRITICAL"
                for f in findings),
        }
    except Exception:
        return None


def run_nvidia(skill_dir: Path):
    """Return a summary dict, or None on any failure."""
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "nvidia.json"
            subprocess.run(
                [NVIDIA_BIN, "scan", str(skill_dir), "--no-llm",
                 "--format", "json", "--output", str(out)],
                capture_output=True, text=True, timeout=SCAN_TIMEOUT)
            if not out.exists():
                return None
            d = json.loads(out.read_text())
        ra = d.get("risk_assessment") or {}
        issues = d.get("issues") or []
        return {
            "version": "2.12.0",
            "score": ra.get("score"),
            "severity": ra.get("severity"),
            "recommendation": ra.get("recommendation"),
            "issues_count": len(issues),
            "categories": sorted({i.get("category") for i in issues
                                  if isinstance(i, dict)
                                  and i.get("category")}),
        }
    except Exception:
        return None


def decide(cisco, nvidia, adjudication):
    """Pure gate logic. Returns (verdict, reasons[]).

    adjudication: None or {decision, rationale, reviewer, date} with
    decision in {pass_with_notes, reject, downgrade_quarantine}.
    """
    reasons = []
    if cisco is None or nvidia is None:
        failed = [n for n, s in (("cisco", cisco), ("nvidia", nvidia))
                  if s is None]
        return "HOLD", [f"scanner failure: {', '.join(failed)} — "
                        f"a gate verdict is never issued on partial evidence"]
    adj = adjudication or {}
    adj_ok = bool(adj.get("rationale"))
    if cisco["credential_critical"]:
        if adj.get("decision") == "downgrade_quarantine" and adj_ok:
            reasons.append("credential CRITICAL downgraded by adjudication "
                           "with recorded rationale")
            return "PASS_WITH_NOTES", reasons
        return "QUARANTINE", ["Cisco credential CRITICAL finding — "
                              "quarantined pending owner review"]
    flagged = (not cisco["is_safe"]
               or nvidia["recommendation"] == "DO_NOT_INSTALL"
               or (isinstance(nvidia["score"], (int, float))
                   and nvidia["score"] >= 25))
    if flagged:
        reasons.append(
            f"content flags: cisco safe={cisco['is_safe']} "
            f"max={cisco['max_severity']}; nvidia score={nvidia['score']} "
            f"rec={nvidia['recommendation']}")
        if not adj:
            return "HOLD", reasons + ["adjudication required — flagged "
                                      "skills are never auto-passed or "
                                      "auto-rejected on scores alone"]
        if adj.get("decision") == "reject":
            return "REJECTED", reasons + ["adjudication: reject"]
        if adj.get("decision") == "pass_with_notes" and adj_ok:
            return "PASS_WITH_NOTES", reasons + [
                "adjudication: pass with capability notes"]
        return "HOLD", reasons + ["adjudication present but incomplete "
                                  "(decision/rationale missing)"]
    return "PASS", ["both scanners clean"]


def write_record(out_dir: Path, skill_dir: Path, meta: dict,
                 cisco, nvidia, adjudication, verdict, reasons) -> Path:
    slug = skill_dir.name.lower().replace(" ", "-").replace("_", "-")
    record = {
        "skill_name": skill_name(skill_dir),
        "slug": slug,
        "source_url": meta["source"],
        "publisher": meta["publisher"],
        "pinned_ref": meta["ref"],
        "content_hash": content_hash(skill_dir),
        "evaluated": date.today().isoformat(),
        "cisco": cisco,
        "nvidia": nvidia,
        "adjudication": adjudication,
        "verdict": verdict,
        "unresolved_risks": RESIDUAL_RISKS,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.md"
    body = [f"# Gate evaluation — {record['skill_name']}", "",
            f"Verdict: **{verdict}**", ""]
    body += [f"- {r}" for r in reasons]
    body += ["", "Scanner findings and adjudication are in the frontmatter. "
             "A PASS means no evidence was found by static scanning — "
             "not that the skill is proven safe.", ""]
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False)
                    + "---\n\n" + "\n".join(body))
    return path


def cmd_evaluate(args) -> int:
    skill_dir = Path(args.skill_dir)
    if not skill_dir.is_dir():
        print(f"ERROR: not a directory: {skill_dir}")
        return 2
    adjudication = None
    if args.adjudication:
        adjudication = json.loads(Path(args.adjudication).read_text())
    cisco = run_cisco(skill_dir)
    nvidia = run_nvidia(skill_dir)
    verdict, reasons = decide(cisco, nvidia, adjudication)
    path = write_record(Path(args.out), skill_dir,
                        {"source": args.source, "publisher": args.publisher,
                         "ref": args.ref},
                        cisco, nvidia, adjudication, verdict, reasons)
    print(f"verdict: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    print(f"record: {path}")
    return 0


def cmd_verify(args) -> int:
    text = Path(args.evaluation).read_text()
    fm = yaml.safe_load(text.split("---", 2)[1])
    recorded = fm.get("content_hash")
    current = content_hash(Path(args.skill_dir))
    if recorded == current:
        print(f"MATCH — skill tree is identical to the evaluated tree "
              f"({recorded[:23]}…)")
        return 0
    print(f"CHANGED — recorded {recorded} but current tree hashes to "
          f"{current}. The gate verdict no longer applies; re-evaluate.")
    return 2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("skill_dir")
    ev.add_argument("--source", required=True)
    ev.add_argument("--publisher", required=True)
    ev.add_argument("--ref", required=True)
    ev.add_argument("--adjudication")
    ev.add_argument("--out", default=str(DEFAULT_OUT))
    vf = sub.add_parser("verify")
    vf.add_argument("evaluation")
    vf.add_argument("skill_dir")
    args = ap.parse_args()
    return cmd_evaluate(args) if args.cmd == "evaluate" else cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
