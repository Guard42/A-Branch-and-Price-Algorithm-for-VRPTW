"""Regenerate the README full-comparison block from full_comparison.json.

Regenerates the README FULL_COMPARISON markers from
results/full_comparison.json (produced by scripts/bench_full.py).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
data = json.loads((WS / "results" / "full_comparison.json").read_text(encoding="utf-8"))
rows = data["rows"]
lines = [
    "| Instance | Gurobi MIP cost | MIP time (s) | BP cost | BP time (s) | "
    "Cost gap (%) | Time reduced (%) |",
    "|----------|----------------:|-------------:|--------:|------------:|"
    "-------------:|-----------------:|",
]
n_match = 0
for r in rows:
    gc = "-" if r["gurobi_cost"] is None else f"{r['gurobi_cost']:.2f}"
    bc = "-" if r["bp_cost"] is None else f"{r['bp_cost']:.2f}"
    gt = "-" if r["gurobi_time_s"] is None else f"{r['gurobi_time_s']:.1f}"
    bt = "-" if r["bp_time_s"] is None else f"{r['bp_time_s']:.1f}"
    gap = "-" if r["cost_gap_pct"] is None else f"{r['cost_gap_pct']:.3f}"
    tr = "-" if r["time_reduced_pct"] is None else f"{r['time_reduced_pct']:.1f}"
    if r.get("cost_match"):
        n_match += 1
    lines.append(
        f"| `{r['instance']}` | {gc} | {gt} | {bc} | {bt} | {gap} | {tr} |"
    )

block = (
    "<!-- FULL_COMPARISON_START -->\n"
    + "\n".join(lines)
    + f"\n\nBoth methods agree on the optimal cost for **{n_match}/{len(rows)}**\n"
    + "instances (`Cost gap = 0`). `Time reduced` = how much faster\n"
    + "branch-and-price finished than the plain Gurobi MIP model\n"
    + "(negative = the MIP was faster). Rows where either method hit its\n"
    + "30-minute budget show their best incumbent.\n"
    + "<!-- FULL_COMPARISON_END -->"
)

readme_path = WS / "README.md"
readme = readme_path.read_text(encoding="utf-8")
if "<!-- FULL_COMPARISON_START -->" not in readme:
    raise SystemExit("README is missing the FULL_COMPARISON markers")
new_readme = re.sub(
    r"<!-- FULL_COMPARISON_START -->.*?<!-- FULL_COMPARISON_END -->",
    lambda _: block,
    readme,
    flags=re.DOTALL,
)
readme_path.write_text(new_readme, encoding="utf-8")
print(f"README updated: {len(rows)} rows, {n_match} cost matches")
