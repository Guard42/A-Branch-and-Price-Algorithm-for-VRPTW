"""Legacy-vs-new parity check on one instance.

Runs the frozen legacy implementation (legacy/branchBound.py, Gurobi-based)
and the new bpvrptw solver on the same Solomon file and compares the proven
optimal costs. Educational evidence that the rewrite preserved correctness.

Usage:
    python scripts/legacy_parity.py dataset/C101_25.txt

Requires gurobipy with a working license (the legacy code is Gurobi-bound).
Not part of the pytest suite; run manually.
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "legacy"))


def run_legacy(dataset: Path) -> float:
    from branchBound import BranchAndBound  # type: ignore[import-not-found]
    from paramsVRP import ParamsVRP  # type: ignore[import-not-found]
    from route import Route  # type: ignore[import-not-found]

    buf = io.StringIO()
    bp = BranchAndBound()
    params = ParamsVRP()
    started = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        params.init_params(str(dataset))
        init_routes = []
        for i in range(params.nbclients - 2):
            cost = params.dist[0][i + 1] + params.dist[i + 1][params.nbclients - 1]
            init_routes.append(
                Route(path=[0, i + 1, params.nbclients - 1], cost=cost, Q=1.0)
            )
        best_routes: list[Route] = []
        bp.bb_node(params, init_routes, None, best_routes, 0)
    elapsed = time.perf_counter() - started
    total = sum(r.get_cost() for r in best_routes)
    print(f"legacy : cost={total:.4f} routes={len(best_routes)} t={elapsed:.2f}s")
    return total


def run_new(dataset: Path) -> float:
    from bpvrptw.branch_and_price import BranchAndPrice
    from bpvrptw.instance import VRPTWInstance
    from bpvrptw.solution import SolutionStatus

    inst = VRPTWInstance.from_solomon(dataset)
    started = time.perf_counter()
    solution = BranchAndPrice(inst, lp_solver="gurobi").solve()
    elapsed = time.perf_counter() - started
    assert solution.status == SolutionStatus.SOLVED_OPTIMAL, solution.status.value
    print(f"new    : cost={solution.total_cost:.4f} "
          f"routes={len(solution.routes)} t={elapsed:.2f}s")
    return solution.total_cost


def main(argv: list[str]) -> int:
    datasets = [Path(p) for p in argv[1:]] or [REPO / "dataset" / "C101_25.txt"]
    failures = 0
    for ds in datasets:
        print(f"== {ds.name} ==")
        try:
            legacy_cost = run_legacy(ds)
        except Exception as exc:  # noqa: BLE001 - legacy env problems reported
            print(f"legacy : FAILED ({exc})", file=sys.stderr)
            failures += 1
            continue
        new_cost = run_new(ds)
        if abs(legacy_cost - new_cost) > 1e-6:
            print(f"MISMATCH: legacy={legacy_cost} new={new_cost}", file=sys.stderr)
            failures += 1
        else:
            print(f"parity : OK ({new_cost:.4f})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
