"""Tests for the direct Gurobi MIP baseline model."""

from __future__ import annotations

from pathlib import Path

import pytest

from bpvrptw.instance import VRPTWInstance
from bpvrptw.mip import solve_mip

pytest.importorskip("gurobipy")

DATASET_C101_25 = Path(__file__).resolve().parents[1] / "dataset" / "C101_25.txt"


def test_mip_matches_bp_on_c101_25() -> None:
    """The textbook MIP must agree with the proven branch-and-price optimum."""
    from bpvrptw.branch_and_price import BranchAndPrice

    inst = VRPTWInstance.from_solomon(DATASET_C101_25)
    mip = solve_mip(inst, time_limit_seconds=120)
    assert mip.status.value == "SOLVED_OPTIMAL"
    assert abs(mip.total_cost - 191.7) < 0.5
    assert mip.is_feasible(inst)

    bp = BranchAndPrice(inst, lp_solver="highs").solve()
    assert bp.status.value == "SOLVED_OPTIMAL"
    assert abs(bp.total_cost - mip.total_cost) < 1e-6


def test_mip_capacity_is_enforced(tmp_path: Path) -> None:
    """A tiny instance whose optimal solution needs two vehicles."""
    from conftest import TINY_CUSTOMERS, TINY_DEPOT, make_instance_from_rows

    inst = make_instance_from_rows(
        tmp_path, "CAPMIP", vehicle_count=6, capacity=20.0,
        depot_row=TINY_DEPOT, customers_rows=TINY_CUSTOMERS,
    )
    sol = solve_mip(inst, time_limit_seconds=60)
    assert sol.status.value == "SOLVED_OPTIMAL"
    # capacity 20 with demands 5..12 -> at least 3 routes.
    assert len(sol.routes) >= 3
    for r in sol.routes:
        assert r.load <= inst.capacity + 1e-9


def test_mip_infeasible_reported(tmp_path: Path) -> None:
    from conftest import write_solomon

    # Depot due window closes before any round trip can return.
    path = write_solomon(
        tmp_path, "NOPE", 2, 50.0,
        (0, 40.0, 50.0, 0.0, 0.0, 5.0, 0.0),
        [(1, 45.0, 68.0, 5.0, 0.0, 1000.0, 5.0)],
    )
    inst = VRPTWInstance.from_solomon(path)
    sol = solve_mip(inst, time_limit_seconds=30)
    assert sol.status.value in {"INFEASIBLE", "TIME_LIMIT", "ERROR"}
