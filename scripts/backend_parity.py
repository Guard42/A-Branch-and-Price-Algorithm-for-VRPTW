"""Cross-validate every instance under BOTH LP backends.

For each dataset file, solve twice (HiGHS and Gurobi) with a modest time
limit. Wherever both runs prove optimality, the reported optima MUST match
exactly - that is the correctness contract of the backend abstraction.
Divergent TIME_LIMIT incumbents are reported but do not fail the check
(different simplex paths legitimately reach different incumbents when the
budget expires).

Usage:
    python scripts/backend_parity.py [time_limit_seconds]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from bpvrptw.branch_and_price import BranchAndPrice  # noqa: E402
from bpvrptw.instance import VRPTWInstance  # noqa: E402


def main() -> int:
    tl = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    files = sorted(
        p for p in (WS / "dataset").iterdir()
        if p.is_file() and p.suffix.lower() == ".txt"
    )
    mismatches: list[str] = []
    both_optimal = 0
    rows: list[dict[str, object]] = []
    for path in files:
        inst = VRPTWInstance.from_solomon(path)
        results: dict[str, tuple[str, float | None]] = {}
        for backend in ("highs", "gurobi"):
            solution = BranchAndPrice(
                inst, lp_solver=backend, time_limit_seconds=tl
            ).solve()
            results[backend] = (solution.status.value, solution.total_cost)
        (hs_status, hs_cost), (gr_status, gr_cost) = (
            results["highs"], results["gurobi"]
        )
        agree = hs_cost is not None and gr_cost is not None \
            and abs(hs_cost - gr_cost) < 1e-6
        if hs_status == "SOLVED_OPTIMAL" and gr_status == "SOLVED_OPTIMAL":
            both_optimal += 1
            if not agree:
                mismatches.append(
                    f"{path.name}: highs={hs_cost} gurobi={gr_cost}"
                )
        rows.append({
            "instance": path.name,
            "highs": f"{hs_status}:{hs_cost}",
            "gurobi": f"{gr_status}:{gr_cost}",
            "agree": agree,
        })
        print(f"{path.name:<14} highs={hs_status}:{hs_cost}  "
              f"gurobi={gr_status}:{gr_cost}", flush=True)

    out = WS / "results" / "backend_parity.json"
    out.write_text(json.dumps({"time_limit_s": tl, "rows": rows},
                              indent=2, default=str), encoding="utf-8")
    print(f"\n{len(files)} instances, {both_optimal} proven optimal by BOTH "
          f"backends, {len(mismatches)} mismatches")
    for m in mismatches:
        print(f"MISMATCH {m}", file=sys.stderr)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
