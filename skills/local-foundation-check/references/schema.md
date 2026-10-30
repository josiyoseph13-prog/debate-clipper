# Capability Registry — Schema v2 (2026-10-10)

One Markdown file per tool under `~/workspace/registry/tools/<slug>.md`:
YAML frontmatter (machine-checked) + a human body whose core is an
append-only `Verification log:`.

## Required record fields

| Field | Type | Notes |
|---|---|---|
| schema | int | Must be `2` |
| slug | string | Must equal the filename stem; unique |
| index_name | string (optional) | Short display name for INDEX |
| index_order | int | Row order in the generated INDEX |
| name, official_url, vendor, category, version, license | string | Descriptive identity |
| status | enum | candidate · available · connected · tested · adopted · blocked · rejected · deprecated |
| status_detail | string | Short note rendered next to the status in INDEX |
| status_note | string (optional) | Longer status explanation (e.g. block reason) |
| capabilities | map | See below — every entry fully evidenced |
| cost | string | What it costs, or that cost is UNVERIFIED |
| cost_evidence_date | date | When the cost statement was last checked |
| permissions_required, sensitive_data, dependencies, resource_requirements, security_risks, compatibility | — | Risk/safety picture |
| test_procedure, expected_result, actual_result | string | The last test, honestly reported |
| last_verified | date | Last date any part of the record was verified |
| review_after_days | int 1–365 | Staleness interval; validator warns when overdue |
| owner_decision | string \| null | Dated owner decision (blocks, rejections); null when none |
| next_action | string | The single next step that would move this record forward |
| evidence_files | list of paths | Logs/artifacts backing claims; validator checks they exist |
| failure_history | list | Failures are kept, never deleted |
| decision_rationale, alternatives_considered, rollback_plan | string | Adoption reasoning |

## Capability entries (uniform — this was the v1 drift)

```yaml
capabilities:
  publish: {supported: full, label: VERIFIED, evidence: "what proves this", verified: 2026-10-10}
```

- `supported` ∈ `full · none · partial · claimed · restricted`
  (v1 used true/false plus partial/claimed/restricted inconsistently;
  v2 uses one enum, avoiding YAML boolean traps like `yes/no`).
- `label` ∈ `VERIFIED · DOCUMENTED · UNVERIFIED · UNSUPPORTED`.
- `evidence` is mandatory and non-empty — a claim without evidence does
  not enter the registry.
- `verified` is the date THIS capability was last checked (v1 only had a
  record-level date, which hid stale capabilities).

## Gate evaluation records (skill adoption)

Skills are not tool records. Each candidate skill that goes through the
security gate (procedure: `~/workspace/registry/SECURITY_GATE.md`) gets one
record at `~/workspace/registry/gate-evaluations/<slug>.md` with frontmatter:
`skill_name, slug, source_url, publisher, pinned_ref, content_hash (sha256
of the whole tree), evaluated, cisco {...summary}, nvidia {...summary},
adjudication (null or {decision, rationale, reviewer, date}), verdict
(PASS · PASS_WITH_NOTES · HOLD · QUARANTINE · REJECTED), unresolved_risks`.
The verdict applies to the recorded hash only; `gate_check.py verify`
detects any later change. These records are evidence for an adoption
decision — they are not approvals, and the gate never installs anything.

## Rules

1. INDEX.md is generated (`generate_index.py`), never hand-edited.
2. A status only moves up with a dated verification-log entry + evidence.
3. Failures are appended to `failure_history` and the log, never erased.
4. Blocked/rejected records must carry an `owner_decision` with a date.
5. The validator (`validate_registry.py`) must pass before any registry
   change is reported as done.
