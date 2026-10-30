#!/usr/bin/env python3
"""Generate registry INDEX.md from record frontmatter (schema v2).

Usage:
  generate_index.py [registry_dir]           rewrite INDEX.md
  generate_index.py [registry_dir] --check   exit 1 if INDEX.md is stale
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from registry_lib import load_records, render_index  # noqa: E402

DEFAULT = Path.home() / "workspace" / "registry"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    registry = Path(args[0]) if args else DEFAULT
    content = render_index(load_records(registry))
    index_path = registry / "INDEX.md"
    if check:
        current = index_path.read_text() if index_path.exists() else ""
        if current == content:
            print("INDEX.md is current.")
            return 0
        print("INDEX.md is STALE — regenerate with generate_index.py")
        return 1
    index_path.write_text(content)
    print(f"Wrote {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
