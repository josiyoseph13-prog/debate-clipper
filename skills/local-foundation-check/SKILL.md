

# Foundation Check

## Purpose
Keep the capability registry truthful: schema-valid records, an INDEX that
can never drift from the records, and a single read-only command that reports
what actually works — distinguishing OK from NOT CONNECTED, BLOCKED,
UNAVAILABLE, UNTESTED, and STALE.

## Tooling
All scripts run with the isolated venv (never the system Python):
`~/workspace/tools/foundation-venv/bin/python` (pyyaml + pytest only).

- `bin/validate_registry.py [registry_dir]` — schema v2 validation:
  required fields/types, capability schema, duplicate slugs/names,
  evidence-file existence, broken internal links; staleness = warning.
  Exit 1 on errors.
- `bin/generate_index.py [registry_dir] [--check]` — rebuild INDEX.md
  from frontmatter, or check freshness without writing.
- `bin/foundation_check.py` — the one-command check: registry + INDEX
  freshness + system tool versions + media-venv tools + read-only
  connector statuses.
- `bin/migrate_registry.py` — the idempotent v1→v2 migration (already
  applied 2026-10-10; kept for future schema bumps).
- `bin/gate_check.py` — the combined security gate for candidate skills
  (procedure: `~/workspace/registry/SECURITY_GATE.md`). `evaluate` hashes
  the skill tree, runs Cisco Skill Scanner + NVIDIA SkillSpector
  (`--no-llm`) from their isolated venvs, applies the gate rules, and
  writes an evaluation record to `~/workspace/registry/gate-evaluations/`.
  `verify` re-checks a tree against a recorded hash (rug-pull check).
  Verdicts: PASS / PASS_WITH_NOTES / HOLD / QUARANTINE / REJECTED.
- `references/schema.md` — the schema v2 contract.
- `tests/` — pytest suites (registry + gate; 26 tests), run with:
  `~/workspace/tools/foundation-venv/bin/python -m pytest ~/workspace/custom-skills/local-foundation-check/tests -v`

## Operating Rules
1. Read-only by default: the checker never installs, connects, or writes
   anything except `generate_index.py` writing INDEX.md when explicitly run.
2. Instagram is never probed live — the owner blocked it; report its state
   from the registry record. No connector write operations, ever, from
   these scripts (status calls only).
3. After ANY registry edit: run the validator, regenerate INDEX, and only
   then report the change as done. A green validator is the evidence.
4. Report states with the checker's words — OK / NOT CONNECTED / BLOCKED /
   UNAVAILABLE / UNTESTED / STALE / ERROR. Never upgrade a state in prose
   beyond what the output shows.
5. Failures stay in the records (`failure_history`, append-only log). Do not
   soften or delete them to make a check pass.
6. Security gate: no skill is adopted without a `gate_check.py evaluate`
   record. Flagged skills are never auto-passed or auto-rejected on scores
   alone — adjudication with a recorded rationale decides, and a Cisco
   credential CRITICAL quarantines by default. The gate never installs a
   skill; adoption is jo's separate decision after reviewing the record.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
