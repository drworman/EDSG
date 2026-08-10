#!/usr/bin/env python3
"""Regenerate docs/CRITERIA.md from the criteria definitions.

Run after adding or changing a metric so the reference cannot drift from
the code:

    python scripts/generate_criteria_doc.py

CI does not enforce this: a stale reference is a documentation bug, not a
broken build. Regenerating it is a one-line habit instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from edsg.docs_gen import render_criteria_reference  # noqa: E402


def main() -> int:
    target = ROOT / "docs" / "CRITERIA.md"
    target.write_text(render_criteria_reference(), encoding="utf-8")
    print(f"Wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
