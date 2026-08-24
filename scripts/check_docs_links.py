"""Verify that every local link inside the repo's Markdown files resolves.

Usage: python scripts/check_docs_links.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")


def main() -> int:
    failures: list[str] = []
    checked = 0
    for md in REPO.rglob("*.md"):
        rel_dir = md.parent
        text = md.read_text(encoding="utf-8")
        # Strip fenced code blocks: they often contain example links.
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        for target in LINK.findall(stripped):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (rel_dir / path_part).resolve()
            checked += 1
            if not resolved.exists():
                failures.append(f"{md.relative_to(REPO)} -> {target}")
    if failures:
        for f in failures:
            print(f"BROKEN: {f}", file=sys.stderr)
        return 1
    print(f"OK: {checked} local markdown links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
