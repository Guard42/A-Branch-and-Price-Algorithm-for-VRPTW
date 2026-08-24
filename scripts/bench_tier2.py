"""Tier 2: deep runs (300s each) on selected TIME_LIMIT instances."""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

import bpvrptw  # noqa: E402  (sys.path shim above)
from bpvrptw.branch_and_price import BranchAndPrice  # noqa: E402
from bpvrptw.instance import VRPTWInstance  # noqa: E402

SELECTED = [
    "C103.txt", "C104.txt",          # the historical hang cases
    "C202.txt", "C208.txt",          # C2 family spread
    "R102.txt", "R106.txt", "R201.txt", "R207.txt",
    "RC202.txt", "RC205.txt", "RC207.txt", "RC208.txt",
]
TIME_LIMIT = 300.0

rows: list[dict[str, object]] = []
for name in SELECTED:
    path = WS / "dataset" / name
    if not path.exists():
        print(f"skip missing {name}", flush=True)
        continue
    inst = VRPTWInstance.from_solomon(path)
    t0 = time.perf_counter()
    solution = BranchAndPrice(
        inst, lp_solver="auto", gap=1e-6, time_limit_seconds=TIME_LIMIT
    ).solve()
    elapsed = time.perf_counter() - t0
    rows.append(
        {
            "instance": name,
            "status": solution.status.value,
            "total_cost": round(solution.total_cost, 6),
            "routes": len(solution.routes),
            "lower_bound": solution.lower_bound,
            "solve_time_seconds": round(elapsed, 3),
        }
    )
    print(f"{name}: {solution.status.value} cost={solution.total_cost:.2f} "
          f"LB={solution.lower_bound} t={elapsed:.1f}s", flush=True)

payload = {
    "meta": {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bpvrptw_version": bpvrptw.__version__,
        "time_limit_s": TIME_LIMIT,
        "lp_solver": "auto",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    },
    "rows": rows,
}
out = WS / "results" / "bench_tier2.json"
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"wrote {out}")
