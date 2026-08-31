"""Drive the remaining full-comparison instances (RC104-RC108, RC201-RC208).

Skips instances already recorded in results/full_comparison.json, runs the
direct Gurobi MIP (2.5h cap) then branch-and-price (2.5h cap) for each
remaining instance, and incrementally saves after every instance.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from bpvrptw.branch_and_price import BranchAndPrice  # noqa: E402
from bpvrptw.instance import InstanceFormatError, VRPTWInstance  # noqa: E402
from bpvrptw.mip import solve_mip  # noqa: E402

PER_SOLVER_LIMIT = 9000.0  # 2.5 hours per method per instance
OUT = WS / "results" / "full_comparison.json"

files = sorted(
    p for p in (WS / "dataset").iterdir()
    if p.is_file() and p.suffix.lower() == ".txt"
)


def load_rows() -> tuple[list[dict], set[str]]:
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
        rows = list(data.get("rows", []))
        done = {r["instance"] for r in rows}
        return rows, done
    return [], set()


def save_rows(rows: list[dict]) -> None:
    OUT.write_text(
        json.dumps({"meta": {"incremental": True}, "rows": rows}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    rows, done = load_rows()
    print(f"resuming: {len(done)} instances already completed", flush=True)
    for path in files:
        name = path.name
        if name in done:
            print(f"skip {name} (already done)", flush=True)
            continue
        try:
            inst = VRPTWInstance.from_solomon(path)
        except InstanceFormatError as exc:
            print(f"skip {name} (parse error: {exc})", flush=True)
            continue

        print(f"=== {name}: MIP (limit {PER_SOLVER_LIMIT:.0f}s) ===", flush=True)
        t0 = time.perf_counter()
        mip = solve_mip(inst, time_limit_seconds=PER_SOLVER_LIMIT)
        mip_t = time.perf_counter() - t0
        print(f"    MIP done: {mip.status.value} cost={mip.total_cost:.2f} "
              f"t={mip_t:.1f}s", flush=True)

        print(f"=== {name}: BP (limit {PER_SOLVER_LIMIT:.0f}s) ===", flush=True)
        t0 = time.perf_counter()
        bp = BranchAndPrice(
            inst, lp_solver="gurobi", time_limit_seconds=PER_SOLVER_LIMIT
        ).solve()
        bp_t = time.perf_counter() - t0
        print(f"    BP done: {bp.status.value} cost={bp.total_cost:.2f} "
              f"t={bp_t:.1f}s", flush=True)

        cost_gap = None
        if mip.total_cost and bp.total_cost and mip.status.value != "INFEASIBLE":
            cost_gap = round(
                abs(bp.total_cost - mip.total_cost)
                / abs(mip.total_cost) * 100.0, 4
            )
        time_reduced = None
        if mip_t > 1e-9 and bp.total_cost is not None:
            time_reduced = round((mip_t - bp_t) / mip_t * 100.0, 2)

        row = {
            "instance": name,
            "gurobi_status": mip.status.value,
            "gurobi_cost": round(mip.total_cost, 4) if mip.total_cost else None,
            "gurobi_time_s": round(mip_t, 2),
            "bp_status": bp.status.value,
            "bp_cost": round(bp.total_cost, 4) if bp.total_cost else None,
            "bp_time_s": round(bp_t, 2),
            "cost_gap_pct": cost_gap,
            "time_reduced_pct": time_reduced,
            "cost_match": bool(
                mip.total_cost and bp.total_cost
                and abs(mip.total_cost - bp.total_cost) < 1e-6
            ),
        }
        rows.append(row)
        save_rows(rows)
        print(f"=== {name} SAVED ({len(rows)} total) ===", flush=True)

    print(f"ALL DONE: {len(rows)} rows saved to {OUT}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - report and die loudly
        import traceback
        traceback.print_exc()
        sys.exit(1)
