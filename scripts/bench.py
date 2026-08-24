"""Thin wrapper: run the benchmark harness (delegates to bpvrptw.cli).

Usage: python scripts/bench.py dataset --time-limit 45 --json results/bench.json
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bpvrptw.cli import main  # noqa: E402

if __name__ == "__main__":
    argv = ["bench", *sys.argv[1:]]
    sys.exit(main(argv))
