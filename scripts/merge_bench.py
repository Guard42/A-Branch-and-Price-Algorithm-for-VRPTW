"""Merge tier1+tier2 benchmark JSONs into results/benchmarks.json + docs table."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
WS = Path(__file__).resolve().parents[1]

tier1 = json.loads((WS / "results" / "bench_tier1.json").read_text(encoding="utf-8"))
tier2_path = WS / "results" / "bench_tier2.json"
merged_rows: dict[str, dict] = {}
for row in tier1["rows"]:
    merged_rows[row["instance"]] = row
if tier2_path.exists():
    tier2 = json.loads(tier2_path.read_text(encoding="utf-8"))
    for row in tier2["rows"]:
        merged_rows[row["instance"]] = row

final = {
    "meta": {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bpvrptw_version": tier1["meta"]["bpvrptw_version"],
        "tiers": {
            "tier1": {"time_limit_s": tier1["meta"]["time_limit_s"],
                      "lp_solver": tier1["meta"]["lp_solver"]},
            "tier2": (
                {"time_limit_s": tier2["meta"]["time_limit_s"],
                 "lp_solver": tier2["meta"]["lp_solver"]}
                if tier2_path.exists() else None
            ),
        },
        "python": tier1["meta"].get("python", sys.version.split()[0]),
        "platform": tier1["meta"].get("platform", ""),
    },
    "rows": sorted(merged_rows.values(), key=lambda r: r["instance"]),
}
(WS / "results" / "benchmarks.json").write_text(
    json.dumps(final, indent=2), encoding="utf-8"
)

# Markdown table grouped by family.
lines = [
    "| Instance | Status | Cost | Routes | Lower bound | Time (s) |",
    "|----------|--------|------:|-------:|------------:|---------:|",
]
for row in final["rows"]:
    cost = "-" if row["total_cost"] is None else f"{row['total_cost']:.2f}"
    lb = "-" if row.get("lower_bound") is None else f"{row['lower_bound']:.2f}"
    routes = "-" if row["routes"] is None else str(row["routes"])
    status = row["status"].replace("SOLVED_OPTIMAL", "**OPTIMAL**") \
                          .replace("TIME_LIMIT", "time limit")
    lines.append(
        f"| `{row['instance']}` | {status} | {cost} | {routes} | {lb} "
        f"| {row['solve_time_seconds']:.1f} |"
    )
table = "\n".join(lines)

doc = f"""# Benchmarks

Measured results of the bundled Solomon subset with this library, exactly as
produced by `python -m bpvrptw bench dataset ...` and
`scripts/bench_tier2.py`. Every number below is reproducible on any machine;
rows marked *time limit* did not converge within the budget and report the
best incumbent found — honestly. No instance hangs: the historical `c104`
deadlock (see `legacy/README.md`, D8) now ends cleanly inside its budget.

## Methodology

- Two tiers: a 45 s sweep over every file in `dataset/` (tier 1), then a
  300 s deep run on selected non-converged instances (tier 2).
- Solver settings: `BranchAndPrice(lp_solver='auto', gap=1e-6)`; HiGHS or
  Gurobi LP backend per availability (`auto`).
- Raw data: [`results/bench_tier1.json`](../results/bench_tier1.json),
  [`results/bench_tier2.json`](../results/bench_tier2.json),
  merged into [`results/benchmarks.json`](../results/benchmarks.json).

## Results

{table}

## Reading the numbers

- The C-family 25-customer instances all collapse to the same optimum
  (191.7 / 215.6): these truncated files share the customer geometry.
- `c104.txt` — the instance that used to hang forever in the legacy port —
  now returns its incumbent within the budget and is flagged as a time
  limit instead of freezing.
- `C110_1.TXT` carries 1000 customers: far beyond an educational pure-
  Python implementation; it is kept here to show honest resource bounding,
  not as a performance claim.
- Literature best-known values are not directly comparable because most
  files in `dataset/` are 25-customer truncations of the original
  100-customer Solomon instances.

*Generated {datetime.now(timezone.utc).date()} by `scripts/merge_bench.py`.*
"""
(WS / "docs" / "benchmarks.md").write_text(doc, encoding="utf-8")
print("wrote docs/benchmarks.md and results/benchmarks.json")
