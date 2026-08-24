"""Focused tests for :mod:`bpvrptw.column_generation`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from conftest import TINY_DEPOT, make_instance_from_rows

from bpvrptw.column_generation import ColumnGeneration, MasterInfeasibleError
from bpvrptw.instance import VRPTWInstance


def _tiny(tmp_dir: Path, seed: int) -> VRPTWInstance:
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
        tmp_dir, f"CG{seed}", vehicle_count=6, capacity=70.0,
        depot_row=TINY_DEPOT, customers_rows=rows,
    )


class TestColumnGeneration:
    def test_converges_with_status_optimal(self, tmp_path: Path) -> None:
        result = ColumnGeneration(_tiny(tmp_path, 3), lp_solver="highs").solve()
        assert result.status == "optimal"
        assert result.iterations >= 1
        assert result.n_columns > 6  # seeds alone are not LP-optimal here
        # At convergence the objective IS the dual bound.
        assert result.lower_bound == pytest.approx(result.objective)

    def test_bound_beats_all_seeds(self, tmp_path: Path) -> None:
        inst = _tiny(tmp_path, 4)
        result = ColumnGeneration(inst, lp_solver="highs").solve()
        seed_cost = sum(
            float(inst.dist[0][c] + inst.dist[c][inst.end_depot])
            for c in inst.customers
        )
        assert result.objective <= seed_cost + 1e-6

    def test_column_values_align_with_primals(self, tmp_path: Path) -> None:
        result = ColumnGeneration(_tiny(tmp_path, 5), lp_solver="highs").solve()
        assert len(result.column_values) == result.n_columns
        # Coverage rows are >= 1, so a single all-customers column with value
        # 1 is feasible; total primal flow must be at least 1.
        total_used = sum(value for _, value in result.column_values)
        assert total_used >= 1.0 - 1e-6
    def test_iteration_limit_respected(self, tmp_path: Path) -> None:
        result = ColumnGeneration(_tiny(tmp_path, 6), lp_solver="highs").solve(
            max_iterations=2
        )
        assert result.iterations <= 2
        assert result.status in {"optimal", "iteration_limit"}

    def test_time_limit_respected(self, tmp_path: Path) -> None:
        result = ColumnGeneration(_tiny(tmp_path, 7), lp_solver="highs").solve(
            time_limit_seconds=30.0
        )
        assert result.status in {"optimal", "time_limit"}

    def test_unknown_solver_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError):
            ColumnGeneration(_tiny(tmp_path, 8), lp_solver="nope").solve()

    def test_infeasible_master_detected(self, tmp_path: Path) -> None:
        # The only customer's single-customer route is infeasible -> seeding
        # fails outright (its time window is unreachable from the depot).
        from conftest import write_solomon

        inst_file = write_solomon(
            tmp_path, "INF", 2, 50.0,
            (0, 40.0, 50.0, 0.0, 0.0, 1000.0, 0.0),
            [(1, 45.0, 68.0, 5.0, 2000.0, 2005.0, 10.0)],
        )
        inst = VRPTWInstance.from_solomon(inst_file)
        with pytest.raises(MasterInfeasibleError):
            ColumnGeneration(inst, lp_solver="highs").solve()
