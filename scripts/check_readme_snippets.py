"""Execute the runnable Python snippets embedded in README.md.

Usage: python scripts/check_readme_snippets.py
Every fenced block tagged ```python runnable must be self-contained (it
creates its own instance files) and must run without error.
"""

from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
FENCE = re.compile(r"```python\s+runnable\n(.*?)```", re.DOTALL)


def main() -> int:
    readme = REPO / "README.md"
    if not readme.exists():
        print("README.md not found", file=sys.stderr)
        return 1
    text = readme.read_text(encoding="utf-8")
    snippets = FENCE.findall(text)
    if not snippets:
        print("no ```python runnable blocks found in README.md", file=sys.stderr)
        return 1
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        for idx, snippet in enumerate(snippets, start=1):
            try:
                exec(compile(snippet, f"<readme-snippet-{idx}>", "exec"), {"__name__": "__main__"})  # noqa: S102
                print(f"snippet {idx}: OK")
            except Exception:  # noqa: BLE001 - report and continue
                failures += 1
                print(f"snippet {idx}: FAILED", file=sys.stderr)
                traceback.print_exc()
    if failures:
        print(f"{failures} snippet(s) failed", file=sys.stderr)
        return 1
    print(f"all {len(snippets)} runnable snippets passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
