#!/usr/bin/env python3
"""Validate the Pax capability registry (schema v2).

Checks frontmatter parsing, required fields and types, the capability
schema, duplicate slugs/names, evidence-file existence, and broken
internal links. Staleness is reported as a warning, not a failure.

Usage: validate_registry.py [registry_dir]  (default ~/workspace/registry)
Exit: 0 = no errors (warnings allowed), 1 = errors found.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from registry_lib import validate  # noqa: E402

DEFAULT = Path.home() / "workspace" / "registry"


def main():
    registry = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    errors, warnings = validate(registry)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) "
          f"in {registry}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
