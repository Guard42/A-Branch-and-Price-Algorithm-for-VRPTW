"""Coverage tests for branch-and-price edge branches."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import TINY_DEPOT, make_instance_from_rows

from bpvrptw.branch_and_price import BranchAndPrice, apply_branching
from bpvrptw.instance import VRPTWInstance


def _tiny(tmp_dir, seed: int = 21) -> VRPTWInstance:
    rng = np.random.default_rng(seed)
    rows = [
        (
            idx,
            float(rng.uniform(28.0, 62.0)),
            float(rng.uniform(28.0, 68.0)),
            float(rng.integers(3, 13)),
            float(rng.integers(0, 80)),
            float(rng.integers(1200, 1600)),
            10.0,
        )
        for idx in range(1, 7)
    ]
    return make_instance_from_rows(
        tmp_dir, f"COV{seed}", vehicle_count=6, capacity=70.0,
        depot_row=TINY_DEPOT, customers_rows=rows,
    )


class TestNonConvergedNodeSemantics:
    def test_deadline_yields_time_limit_with_incumbent(
        self, tmp_path,
    ) -> None:
        """A starved budget must produce a feasible UB and no fake certificate."""
        inst = _tiny(tmp_path)
        solution = BranchAndPrice(inst, time_limit_seconds=0.01).solve()
        assert solution.status.value in {"TIME_LIMIT", "SOLVED_OPTIMAL",
                                         "SOLVED_FEASIBLE"}
        # The initial single-customer incumbent is always available.
        assert solution.routes, "expected the seed incumbent to survive"
        assert solution.total_cost > 0
        if solution.status.value != "SOLVED_OPTIMAL":
            assert solution.meta["gap_closed"] is False
            if solution.lower_bound is not None:
                assert solution.lower_bound <= solution.total_cost + 1e-6

    def test_meta_reports_gap_fields(self, tmp_path) -> None:
        inst = _tiny(tmp_path / "m", seed=22)
        solution = BranchAndPrice(inst, lp_solver="highs").solve()
        assert solution.meta["gap_closed"] is True
        assert solution.meta["gap_pct"] == pytest.approx(0.0, abs=1e-6)

    def test_verbose_logging_paths(self, tmp_path, caplog) -> None:
        import logging

        inst = _tiny(tmp_path / "v", seed=23)
        with caplog.at_level(logging.INFO, logger="bpvrptw.branch_and_price"):
            solution = BranchAndPrice(
                inst, lp_solver="highs", verbose=True
            ).solve()
        assert solution.status.value == "SOLVED_OPTIMAL"
        assert any(
            "INCUMBENT |" in r.message or "FEAS |" in r.message
            for r in caplog.records
        )


class TestInfeasibleInstances:
    def test_all_singles_infeasible_is_reported(self, tmp_path) -> None:
        """When even seeds fail, BP reports INFEASIBLE rather than crashing."""
        from conftest import write_solomon

        # Customer window unreachable from the depot AND back within depot due.
        path = write_solomon(
            tmp_path, "NOPE", 2, 50.0,
            (0, 40.0, 50.0, 0.0, 0.0, 10.0, 0.0),   # depot closes immediately
            [(1, 45.0, 68.0, 5.0, 0.0, 1000.0, 5.0)],
        )
        inst = VRPTWInstance.from_solomon(path)
        solution = BranchAndPrice(inst).solve()
        assert solution.status.value == "INFEASIBLE"
        assert solution.routes == []


class TestBranchingMatrixHelpers:
    def test_apply_branching_forbid_then_reapply_base(self) -> None:
        dist = np.ones((4, 4))
        base = dist.copy()
        apply_branching(dist, base, 1, 2, 0, end_depot=3)
        assert dist[1, 2] == 1e10
        # Re-applying value=1 restores the arc from the pristine matrix.
        apply_branching(dist, base, 1, 2, 1, end_depot=3)
        assert dist[1, 2] == pytest.approx(base[1, 2])
