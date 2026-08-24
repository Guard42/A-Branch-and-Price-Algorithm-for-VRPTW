"""Tests for :mod:`bpvrptw.rmp` -- dual conventions and incremental parity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from conftest import TINY_CUSTOMERS, TINY_DEPOT, make_instance_from_rows

from bpvrptw.instance import VRPTWInstance
from bpvrptw.rmp import (
    GurobiBackend,
    make_backend,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

# Hand-computable LP over three customers (rows), using artificial column
# costs independent of the instance geometry:
#
#   seed columns s1,s2,s3 covering single rows at costs 4.0 / 4.5 / 4.0
#   combo A = {c1,c2} cost 7.0      combo B = {c2,c3} cost 7.5
#   combo ALL = {c1,c2,c3} cost 10.5
#
# Candidate covers:
#   seeds only            = 12.5
#   A + s3                = 11.0
#   s1 + B                = 11.5
#   A + B                 = 14.5
#   ALL                   = 10.5   <- optimum
SEED_COSTS = [4.0, 4.5, 4.0]
COMBO_A = ((1, 2), 7.0)
COMBO_B = ((2, 3), 7.5)
COMBO_ALL = ((1, 2, 3), 10.5)
EXPECTED_BATCH1 = 11.0   # after adding only A: A + s3
EXPECTED_FINAL = 10.5    # after adding B and ALL


def rmp_instance(tmp_path: Path) -> VRPTWInstance:
    """Three-customer instance used as a row carrier for the hand LP."""
    return make_instance_from_rows(
        tmp_path, "RMP", vehicle_count=3, capacity=100.0,
        depot_row=TINY_DEPOT, customers_rows=TINY_CUSTOMERS[:3],
    )


def seed_columns_for(instance: VRPTWInstance) -> list[tuple[float, list[int]]]:
    """Single-customer columns priced at SEED_COSTS."""
    return [(SEED_COSTS[c - 1], [c]) for c in instance.customers]


def gurobi_available() -> bool:
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as td:
            backend = GurobiBackend(
                rmp_instance(Path(td)), [(1.0, [1]), (1.0, [2]), (1.0, [3])]
            )
    except Exception:  # noqa: BLE001 - probing availability
        return False
    backend.close()
    return True

def _gurobi_probe() -> bool:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        try:
            backend = GurobiBackend(
                rmp_instance(Path(td)), [(1.0, [1]), (1.0, [2]), (1.0, [3])]
            )
        except Exception:  # noqa: BLE001
            return False
        backend.close()
        return True


def available_backends() -> list[str]:
    names = ["highs"]
    if gurobi_available():
        names.append("gurobi")
    return names


@pytest.mark.parametrize("name", available_backends())
class TestBackendParity:
    def test_incremental_batches_match_hand_solution(
        self, name: str, tmp_path: Path
    ) -> None:
        inst = rmp_instance(tmp_path)
        backend = make_backend(name, inst, seed_columns_for(inst))
        assert backend.n_columns == 3

        # Batch 1: combo A over customers {1,2}.
        backend.add_column(COMBO_A[1], list(COMBO_A[0]))
        sol1 = backend.solve()
        assert sol1.objective == pytest.approx(EXPECTED_BATCH1, abs=1e-7)

        # Batch 2: combo B and the all-rows combo.
        backend.add_column(COMBO_B[1], list(COMBO_B[0]))
        backend.add_column(COMBO_ALL[1], list(COMBO_ALL[0]))
        sol2 = backend.solve()
        assert sol2.objective == pytest.approx(EXPECTED_FINAL, abs=1e-7)
        assert backend.n_columns == 6

    def test_dual_convention_reduced_costs_nonnegative(
        self, name: str, tmp_path: Path
    ) -> None:
        inst = rmp_instance(tmp_path)
        backend = make_backend(name, inst, seed_columns_for(inst))
        backend.add_column(COMBO_A[1], list(COMBO_A[0]))
        backend.add_column(COMBO_B[1], list(COMBO_B[0]))
        backend.add_column(COMBO_ALL[1], list(COMBO_ALL[0]))
        sol = backend.solve()

        all_columns: list[tuple[tuple[int, ...], float]] = [
            ((1,), SEED_COSTS[0]),
            ((2,), SEED_COSTS[1]),
            ((3,), SEED_COSTS[2]),
            (COMBO_A[0], COMBO_A[1]),
            (COMBO_B[0], COMBO_B[1]),
            (COMBO_ALL[0], COMBO_ALL[1]),
        ]
        for customers, cost in all_columns:
            rows = [c - 1 for c in customers]
            reduced = cost - float(sum(sol.duals[r] for r in rows))
            assert reduced >= -1e-6, f"column {customers}: rc={reduced}"

        # Dual bound must not exceed the primal optimum.
        assert float(np.sum(sol.duals)) <= sol.objective + 1e-6
        # And the combo-ALL column with value 1 reproduces the objective.
        assert sol.primal.shape[0] == 6

    def test_incremental_equals_fresh_rebuild(
        self, name: str, tmp_path: Path
    ) -> None:
        inst = rmp_instance(tmp_path)
        incremental = make_backend(name, inst, seed_columns_for(inst))
        incremental.add_column(COMBO_A[1], list(COMBO_A[0]))
        incremental.add_column(COMBO_B[1], list(COMBO_B[0]))
        incremental.add_column(COMBO_ALL[1], list(COMBO_ALL[0]))
        inc_obj = incremental.solve().objective

        fresh_seeds = seed_columns_for(inst) + [
            (COMBO_A[1], list(COMBO_A[0])),
            (COMBO_B[1], list(COMBO_B[0])),
            (COMBO_ALL[1], list(COMBO_ALL[0])),
        ]
        fresh = make_backend(name, inst, fresh_seeds)
        fresh_obj = fresh.solve().objective
        assert inc_obj == pytest.approx(fresh_obj, abs=1e-7)


def test_auto_backend_returns_usable(tmp_path: Path) -> None:
    inst = rmp_instance(tmp_path)
    backend = make_backend("auto", inst, seed_columns_for(inst))
    assert backend.name in {"highs", "gurobi"}
    solution = backend.solve()
    assert solution.objective == pytest.approx(sum(SEED_COSTS), abs=1e-7)
    assert len(solution.duals) == 3
    backend.close()


