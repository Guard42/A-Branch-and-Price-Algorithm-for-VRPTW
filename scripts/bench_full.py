"""Full comparison: Gurobi MIP baseline vs Branch-and-Price, no time limits.

For every bundled instance this script:
1. solves the direct arc-based Gurobi MIP (no time limit),
2. solves with our branch-and-price (no time limit),
3. saves both solutions' visualizations to fig/solutions/,
4. writes results/full_comparison.json and prints the comparison table.

WARNING: 100-customer instances can take hours for both methods; pass a
comma-separated family filter as argv[1] (e.g. "C1,R1") to restrict.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

import bpvrptw  # noqa: E402  (sys.path shim)
from bpvrptw.branch_and_price import BranchAndPrice  # noqa: E402
from bpvrptw.instance import VRPTWInstance  # noqa: E402
from bpvrptw.mip import solve_mip  # noqa: E402
from bpvrptw.schedule import plot_schedule  # noqa: E402
from bpvrptw.visualization import plot_solution  # noqa: E402

FAMILY_FILTER = sys.argv[1] if len(sys.argv) > 1 else ""
FAMILIES = tuple(f.strip().lower() for f in FAMILY_FILTER.split(",") if f.strip())


def wanted(name: str) -> bool:
    if not FAMILIES:
        return True
    stem = name.rsplit(".", 1)[0].lower()
    # "c1" matches c101_25 / c101 / c102 ...; "rc2" matches rc2xx.
    return any(stem.startswith(f) for f in FAMILIES)

def main() -> None:
    files = sorted(
        p for p in (WS / "dataset").iterdir()
        if p.is_file() and p.suffix.lower() == ".txt" and wanted(p.name)
    )
    rows: list[dict[str, object]] = []
    fig_dir = WS / "fig" / "solutions"
    fig_dir.mkdir(parents=True, exist_ok=True)

    for path in files:
        inst = VRPTWInstance.from_solomon(path)
        name = path.name

        t0 = time.perf_counter()
        mip = solve_mip(inst)
        mip_t = time.perf_counter() - t0

        t0 = time.perf_counter()
        bp = BranchAndPrice(inst, lp_solver="gurobi").solve()
        bp_t = time.perf_counter() - t0

        cost_gap = (
            abs(bp.total_cost - mip.total_cost) / max(abs(mip.total_cost), 1e-9) * 100.0
            if mip.status.value != "INFEASIBLE" else None
        )
        time_reduced = (
            (mip_t - bp_t) / mip_t * 100.0 if mip_t > 1e-9 else None
        )

        # Visualizations of both solutions.
        stem = path.stem
        try:
            plot_solution(
                inst, mip, save_path=fig_dir / f"{stem}_mip.png", show=False,
                title=f"Gurobi MIP - {inst.name}",
            )
            plot_schedule(
                inst, mip, save_path=fig_dir / f"{stem}_mip_gantt.png", show=False,
                title=f"Gurobi MIP schedule - {inst.name}",
            )
            plot_solution(
                inst, bp, save_path=fig_dir / f"{stem}_bp.png", show=False,
                title=f"Branch-and-Price - {inst.name}",
            )
            plot_schedule(
                inst, bp, save_path=fig_dir / f"{stem}_bp_gantt.png", show=False,
                title=f"Branch-and-Price schedule - {inst.name}",
            )
        except Exception as exc:  # noqa: BLE001 - plotting must not kill the run
            print(f"  plot skipped: {exc}", flush=True)

        cost_match = (
            mip.total_cost is not None
            and bp.total_cost is not None
            and abs(mip.total_cost - bp.total_cost) < 1e-6
        )
        row = {
            "instance": name,
            "gurobi_status": mip.status.value,
            "gurobi_cost": round(mip.total_cost, 4) if mip.total_cost else None,
            "gurobi_time_s": round(mip_t, 2),
            "bp_status": bp.status.value,
            "bp_cost": round(bp.total_cost, 4) if bp.total_cost else None,
            "bp_time_s": round(bp_t, 2),
            "cost_gap_pct": round(cost_gap, 4) if cost_gap is not None else None,
            "time_reduced_pct": (
                round(time_reduced, 2) if time_reduced is not None else None
            ),
            "cost_match": cost_match,
        }
        rows.append(row)
        print(
            f"{name:<14} MIP[{mip.status.value}:{mip.total_cost:.1f}:{mip_t:.1f}s] "
            f"BP[{bp.status.value}:{bp.total_cost:.1f}:{bp_t:.1f}s] "
            f"gap={row['cost_gap_pct']}% match={cost_match}",
            flush=True,
        )

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bpvrptw_version": bpvrptw.__version__,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "note": "no time limits; gurobi = direct arc MIP; bp = branch-and-price",
        },
        "rows": rows,
    }
    out = WS / "results" / "full_comparison.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
