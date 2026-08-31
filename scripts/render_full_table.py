"""Render the full-comparison table into README.

Reads results/full_comparison.json, builds the README FULL_COMPARISON block
(per-instance costs, runtimes, cost gap, time reduction; TIME_LIMIT rows
marked), and notes any instance where either solver did not finish within
the budget.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
OUT = WS / "results" / "full_comparison.json"
README = WS / "README.md"


def fmt(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "-"
    return f"{v:.{digits}f}"


def main() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    rows = sorted(data["rows"], key=lambda r: r["instance"])

    header = (
        "| Instance | MIP cost | MIP time (s) | BP cost | BP time (s) "
        "| Cost gap (%) | Time reduced (%) |"
    )
    sep = (
        "|----------|---------:|-------------:|--------:|------------:"
        "|-------------:|-----------------:|"
    )
    lines = [header, sep]
    n_match = 0
    incomplete: list[str] = []
    for r in rows:
        inst = r["instance"]
        g_status = r.get("gurobi_status", "")
        b_status = r.get("bp_status", "")
        g_cost = fmt(r.get("gurobi_cost"))
        g_time = fmt(r.get("gurobi_time_s"))
        b_cost = fmt(r.get("bp_cost"))
        b_time = fmt(r.get("bp_time_s"))
        gap = fmt(r.get("cost_gap_pct"), 3)
        tr = fmt(r.get("time_reduced_pct"), 1)
        if g_status != "SOLVED_OPTIMAL":
            g_cost = "limit" if g_cost == "-" else g_cost
            g_time = "limit" if g_time == "-" else g_time
        if b_status != "SOLVED_OPTIMAL":
            b_cost = "limit" if b_cost == "-" else b_cost
            b_time = "limit" if b_time == "-" else b_time
        # mark matched optima
        if r.get("cost_match"):
            n_match += 1
        # collect incomplete instances
        if g_status != "SOLVED_OPTIMAL" or b_status != "SOLVED_OPTIMAL":
            incomplete.append(inst)
        lines.append(
            f"| `{inst}` | {g_cost} | {g_time} | {b_cost} | {b_time} "
            f"| {gap} | {tr} |"
        )

    block = (
        "<!-- FULL_COMPARISON_START -->\n"
        + "\n".join(lines)
        + (
            "\n\nBoth methods agree on the optimal cost for "
            f"**{n_match}/{len(rows)}** instances.\n`Cost gap = 0` means the "
            "branch-and-price optimum equals the direct Gurobi MIP optimum. "
            "`Time reduced` = how much faster branch-and-price finished "
            "(negative = the MIP was faster); `limit` = the 2.5 h budget was "
            "reached without a proven optimum (best incumbent reported).\n"
        )
        + (
            f"\n**Not solved within the 2.5 h budget ({len(incomplete)} "
            "instances):** " + ", ".join(f"`{i}`" for i in sorted(incomplete))
            + " — left for future work as the author has limited time.\n"
        )
        + "<!-- FULL_COMPARISON_END -->"
    )

    readme = README.read_text(encoding="utf-8")
    if "<!-- FULL_COMPARISON_START -->" not in readme:
        raise SystemExit("README missing FULL_COMPARISON markers")
    updated = re.sub(
        r"<!-- FULL_COMPARISON_START -->.*?<!-- FULL_COMPARISON_END -->",
        lambda _: block,
        readme,
        flags=re.DOTALL,
    )
    README.write_text(updated, encoding="utf-8")
    print(f"README updated: {len(rows)} rows, {n_match} cost-match, "
          f"{len(incomplete)} incomplete")


if __name__ == "__main__":
    main()
