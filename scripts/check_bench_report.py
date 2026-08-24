"""Validate a benchmark results file produced by ``bpvrptw bench``.

Usage: python scripts/check_bench_report.py results/benchmarks.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_STATUSES = {
    "SOLVED_OPTIMAL",
    "SOLVED_FEASIBLE",
    "TIME_LIMIT",
    "INFEASIBLE",
}
REQUIRED_ROW_KEYS = {
    "instance",
    "status",
    "total_cost",
    "routes",
    "solve_time_seconds",
}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_bench_report.py <results.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"missing report: {path}", file=sys.stderr)
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    if "meta" not in data or "rows" not in data:
        print("report must contain 'meta' and 'rows'", file=sys.stderr)
        return 1
    rows = data["rows"]
    if not rows:
        print("report contains no rows", file=sys.stderr)
        return 1
    n_optimal = 0
    for row in rows:
        missing = REQUIRED_ROW_KEYS - set(row)
        if missing:
            print(f"row {row.get('instance')}: missing keys {sorted(missing)}", file=sys.stderr)
            return 1
        if row["status"] not in ALLOWED_STATUSES | {"ERROR"}:
            print(f"row {row['instance']}: bad status {row['status']!r}", file=sys.stderr)
            return 1
        if row["status"] == "SOLVED_OPTIMAL":
            n_optimal += 1
    errors = [r for r in rows if r["status"] == "ERROR"]
    if errors:
        for r in errors:
            print(f"ERROR row present: {r['instance']} (see results/errors.log)", file=sys.stderr)
        return 1
    if n_optimal < 3:
        print(
            f"only {n_optimal} SOLVED_OPTIMAL rows; expected at least 3 - "
            "the suite looks broken",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {len(rows)} rows, {n_optimal} proven optimal")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
