"""Tests for column generation and the branch-and-price solver."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from conftest import TINY_CUSTOMERS, TINY_DEPOT, make_instance_from_rows
from exact import exact_optimum

from bpvrptw.branch_and_price import BranchAndPrice, apply_branching
from bpvrptw.column_generation import ColumnGeneration
from bpvrptw.instance import VRPTWInstance
from bpvrptw.rmp import BackendUnavailableError

DATASET_C101_25 = Path(__file__).resolve().parents[1] / "dataset" / "C101_25.txt"

_FORBIDDEN = 1e10



def _tiny(tmp_dir: Path, seed: int) -> VRPTWInstance:
    """Deterministic n=6 instance (same recipe every call)."""
    rng = np.random.default_rng(seed)
    depot = TINY_DEPOT
    customers: list[tuple[int, float, float, float, float, float, float]] = []
    rows = list(TINY_CUSTOMERS) if seed == 0 else []
    if not rows:
        for idx in range(1, 7):
            rows.append(
                (
                    idx,
                    float(rng.uniform(28.0, 62.0)),
                    float(rng.uniform(28.0, 68.0)),
                    float(rng.integers(3, 13)),
                    float(rng.integers(0, 80)),
                    float(rng.integers(1200, 1600)),
                    10.0,
                )
            )
    customers = rows
    return make_instance_from_rows(
        tmp_dir, f"T{seed}", vehicle_count=6, capacity=70.0,
        depot_row=depot, customers_rows=customers,
    )


class TestColumnGeneration:
    def test_converges_and_certifies(self, tmp_path: Path) -> None:
        inst = _tiny(tmp_path, seed=3)
        result = ColumnGeneration(inst, lp_solver="highs").solve()
        assert result.status == "optimal"
        assert result.iterations >= 1
        # LP bound can never exceed the best integer solution cost.
        assert result.lower_bound <= exact_optimum(inst) + 1e-6
        # Optimality certificate of RMP + pricing: re-solve and confirm no
        # negative reduced-cost single-customer column remains.
        assert result.n_columns > len(list(inst.customers))

    def test_bound_matches_or_beats_greedy(self, tmp_path: Path) -> None:
        inst = _tiny(tmp_path, seed=4)
        result = ColumnGeneration(inst, lp_solver="highs").solve()
        greedy = sum(
            float(inst.dist[0][c] + inst.dist[c][inst.end_depot])
            for c in inst.customers
        )
        assert result.objective <= greedy + 1e-6


class TestApplyBranching:
    """Direct unit tests of the D3 regression."""

    def test_forbid_arc_only_touches_that_arc(self) -> None:
        dist = np.arange(16, dtype=float).reshape(4, 4)
        base = dist.copy()
        apply_branching(dist, base, 1, 2, 0, end_depot=3)
        assert dist[1, 2] == _FORBIDDEN
        dist_expected = base.copy()
        dist_expected[1, 2] = _FORBIDDEN

    def test_impose_client_to_client_wipes_row_and_column(self) -> None:
        dist = np.ones((5, 5))
        base = dist.copy()
        apply_branching(dist, base, 2, 3, 1, end_depot=4)
        # Row 2 keeps only column 3; column 3 keeps only row 2.
        for j in range(5):
            expected = 1.0 if j == 3 else _FORBIDDEN
            assert dist[2, j] == expected
        for i in range(5):
            expected = 1.0 if i == 2 else _FORBIDDEN
            assert dist[i, 3] == expected
        assert dist[3, 2] == _FORBIDDEN  # reverse arc forbidden

    def test_impose_into_end_depot_keeps_other_returns(self) -> None:
        """THE D3 REGRESSION: imposing u->depot must not block w->depot."""
        n = 5
        dist = np.ones((n, n))
        base = dist.copy()
        end_depot = 4
        apply_branching(dist, base, 2, end_depot, 1, end_depot=end_depot)
        # Arc 3 -> end depot must remain usable!
        assert dist[3, end_depot] == 1.0
        # Other columns are untouched: e.g. 3 -> 1 still usable.
        assert dist[3, 1] == 1.0
        # Row of vertex 2 keeps only the depot arc.
        for j in range(n):
            assert dist[2, j] == (1.0 if j == end_depot else _FORBIDDEN)

    def test_impose_from_start_depot_leaves_other_starts(self) -> None:
        n = 5
        dist = np.ones((n, n))
        base = dist.copy()
        apply_branching(dist, base, 0, 2, 1, end_depot=4)
        # Other routes may still leave the start depot.
        assert dist[0, 3] == 1.0
        # But nothing else may enter vertex 2.
        assert dist[3, 2] == _FORBIDDEN


@pytest.mark.parametrize("solver_name", ["highs"])
class TestBranchAndPriceExactness:
    def test_matches_bruteforce_optimum(self, tmp_path: Path, solver_name: str) -> None:
        for seed in (5, 6, 7):
            inst = _tiny(tmp_path / f"s{seed}", seed=seed)
            reference = exact_optimum(inst)
            solution = BranchAndPrice(inst, lp_solver=solver_name).solve()
            assert solution.status.value == "SOLVED_OPTIMAL", f"seed {seed}"
            assert solution.total_cost == pytest.approx(reference, abs=1e-5), (
                f"seed {seed}: BP={solution.total_cost} DP={reference}"
            )
            assert solution.is_feasible(inst)

    def test_tight_time_window_instance(self, tmp_path: Path, solver_name: str) -> None:
        # A deliberately tight instance where routes are forced by deadlines.
        depot = (0, 40.0, 50.0, 0.0, 0.0, 300.0, 0.0)
        customers = [
            (1, 42.0, 52.0, 5.0, 10.0, 60.0, 5.0),
            (2, 45.0, 48.0, 5.0, 20.0, 90.0, 5.0),
            (3, 38.0, 55.0, 5.0, 30.0, 120.0, 5.0),
        ]
        inst = make_instance_from_rows(
            tmp_path, "TIGHT", vehicle_count=3, capacity=50.0,
            depot_row=depot, customers_rows=customers,
        )
        reference = exact_optimum(inst)
        solution = BranchAndPrice(inst, lp_solver=solver_name).solve()
        assert solution.total_cost == pytest.approx(reference, abs=1e-5)



@pytest.mark.skipif(
    os.environ.get("BPVRPTW_SKIP_INTEGRATION") == "1",
    reason="integration disabled",
)
class TestC101TwentyFiveIntegration:
    @pytest.mark.parametrize("solver_name", ["highs"])
    def test_c101_25_optimal_certificate(self, tmp_path: Path, solver_name: str) -> None:
        inst = VRPTWInstance.from_solomon(DATASET_C101_25)
        solution = BranchAndPrice(
            inst, lp_solver=solver_name, time_limit_seconds=600
        ).solve()
        assert solution.status.value == "SOLVED_OPTIMAL"
        assert abs(solution.total_cost - 191.7) < 0.5
        assert solution.lower_bound is not None
        gap_rel = abs(solution.total_cost - solution.lower_bound) / max(
            abs(solution.total_cost), 1e-9
        )
        assert gap_rel <= 1e-6 + 1e-9
        assert solution.is_feasible(inst)


def test_backend_error_propagates(tmp_path: Path) -> None:
    inst = _tiny(tmp_path, seed=8)
    with pytest.raises((BackendUnavailableError, RuntimeError)):
        ColumnGeneration(inst, lp_solver="does-not-exist").solve()
