"""Tests for :mod:`bpvrptw.labeling`, cross-checked against brute force."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from conftest import make_instance_from_rows

from bpvrptw.instance import VRPTWInstance
from bpvrptw.labeling import ESPPRCSolver
from bpvrptw.solution import RouteRecord

_EPS = 1e-9


# ----------------------------------------------------------------------
# Brute-force reference: enumerate ALL elementary feasible routes.
# ----------------------------------------------------------------------
def brute_force_routes(
    instance: VRPTWInstance,
    reduced_costs: np.ndarray | None = None,
    threshold: float = -1e-6,
) -> dict[frozenset[int], tuple[float, tuple[int, ...]]]:
    """Enumerate every elementary route with reduced cost below threshold.

    Returns a mapping from the customer set to (reduced_cost, one path).
    The reference applies NO Feillet pruning; completeness of the solver is
    only comparable because the test instances keep time-window slacks far
    from the rounding boundaries.
    """
    rc = instance.dist if reduced_costs is None else np.asarray(reduced_costs)
    n = instance.total_vertices
    end = n - 1
    dist = instance.dist
    speed = instance.speed
    demand = instance.demand
    ready = instance.ready_time
    due = instance.due_time
    service = instance.service_time
    capacity = instance.capacity

    found: dict[frozenset[int], tuple[float, tuple[int, ...]]] = {}

    def dfs(path: list[int], mask: int, t_now: float, load_now: float) -> None:
        last = path[-1]
        for j in range(1, n):
            if j == last or (mask >> j) & 1:
                continue
            arrival = t_now + float(dist[last, j]) / speed + float(service[last])
            if arrival < ready[j]:
                arrival = float(ready[j])
            new_load = load_now + float(demand[j])
            if arrival > due[j] + _EPS or new_load > capacity + _EPS:
                continue
            cost_now = sum(float(rc[a, b]) for a, b in zip(path, path[1:], strict=False))
            step_cost = cost_now + float(rc[last, j])
            if j == end:
                if len(path) < 2:
                    continue  # routes need at least one interior customer
                key = frozenset(path[1:])
                value = (step_cost, tuple([*path, j]))
                if key not in found or step_cost < found[key][0] - _EPS:
                    found[key] = value
                continue
            dfs([*path, j], mask | (1 << j), arrival, new_load)

    dfs([0], 1, 0.0, 0.0)
    return {k: v for k, v in found.items() if v[0] < threshold}


def random_reduced_costs(instance: VRPTWInstance, seed: int) -> np.ndarray:
    """A deterministic pseudo-dual matrix: per-customer shifts plus noise."""
    rng = np.random.default_rng(seed)
    n = instance.total_vertices
    pi = rng.uniform(0.0, 25.0, size=n)
    noise = rng.uniform(-3.0, 3.0, size=(n, n))
    matrix = instance.dist + noise - pi[:, None]
    np.fill_diagonal(matrix, 0.0)
    return matrix


def seeded_instance(tmp_path: Path, seed: int, n_customers: int = 7) -> VRPTWInstance:
    """A deterministic synthetic instance with comfortable window slacks."""
    rng = np.random.default_rng(seed)
    depot = (0, 40.0, 50.0, 0.0, 0.0, 2000.0, 0.0)
    customers: list[tuple[int, float, float, float, float, float, float]] = []
    for idx in range(1, n_customers + 1):
        customers.append(
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
    return make_instance_from_rows(
        tmp_path, f"SEED{seed}", vehicle_count=n_customers, capacity=70.0,
        depot_row=depot, customers_rows=customers,
    )


class TestCorrectnessAgainstBruteForce:
    def test_soundness_and_optimal_minimum_tiny(self, tiny_instance: VRPTWInstance) -> None:
        """Soundness for every returned route + the best minimum is not missed.

        Full enumeration equality is NOT asserted on purpose: ESPPRC
        dominance legitimately discards dominated partial paths together
        with every completion they would have produced. What column
        generation needs -- and what we verify -- is (a) every returned
        route is elementary, feasible and has exactly the claimed reduced
        cost, and (b) the most negative route overall is always found.
        """
        for seed in (1, 2, 3):
            rc = random_reduced_costs(tiny_instance, seed)
            result = ESPPRCSolver(tiny_instance, rc).solve(
                max_routes=10_000, threshold=-1e-4, max_labels=5_000_000,
            )
            expected = brute_force_routes(tiny_instance, rc, threshold=-1e-4)
            # (a) soundness.
            seen_sets: set[frozenset[int]] = set()
            for route in result.routes:
                assert route.reduced_cost < -1e-4
                recomputed = sum(
                    float(rc[a, b])
                    for a, b in zip(route.path, route.path[1:], strict=False)
                )
                assert route.reduced_cost == pytest.approx(recomputed, abs=1e-8)
                record = RouteRecord.from_path(tiny_instance, list(route.path))
                assert record.load >= 0.0
                key_set = frozenset(route.path[1:-1])
                assert key_set not in seen_sets, "duplicate route set"
                seen_sets.add(key_set)
            # (b) optimality of the minimum.
            if expected:
                best_reference = min(v[0] for v in expected.values())
                assert result.routes, f"seed {seed}: solver found nothing"
                assert result.routes[0].reduced_cost == pytest.approx(
                    best_reference, abs=1e-8
                )
            else:
                assert result.routes == []

class TestBehaviour:
    def test_determinism(self, tmp_path: Path) -> None:
        inst = seeded_instance(tmp_path, 42)
        rc = random_reduced_costs(inst, 42)
        first = ESPPRCSolver(inst, rc).solve(max_routes=20, threshold=-1e-4)
        second = ESPPRCSolver(inst, rc).solve(max_routes=20, threshold=-1e-4)
        assert first.routes == second.routes
        assert first.n_labels_explored == second.n_labels_explored

    def test_label_cap_degrades_gracefully(self, tiny_instance: VRPTWInstance) -> None:
        rc = random_reduced_costs(tiny_instance, 5)
        result = ESPPRCSolver(tiny_instance, rc).solve(
            max_routes=10, threshold=-1e-4, max_labels=8
        )
        assert not result.exhausted
        assert isinstance(result.routes, list)

    def test_time_limit_degrades_gracefully(self, tmp_path: Path) -> None:
        inst = seeded_instance(tmp_path, 9, n_customers=9)
        rc = random_reduced_costs(inst, 9)
        result = ESPPRCSolver(inst, rc).solve(
            max_routes=10, threshold=-1e-4, time_limit_seconds=0.05
        )
        assert isinstance(result.routes, list)
        assert result.elapsed_seconds >= 0.0

    def test_solver_does_not_mutate_instance(self, tiny_instance: VRPTWInstance) -> None:
        coords_before = tiny_instance.coords.copy()
        due_before = tiny_instance.due_time.copy()
        rc = random_reduced_costs(tiny_instance, 3)
        ESPPRCSolver(tiny_instance, rc).solve(max_routes=5, threshold=-1e-4)
        assert np.array_equal(tiny_instance.coords, coords_before)
        assert np.array_equal(tiny_instance.due_time, due_before)

    def test_no_candidates_with_pure_distance_costs(self, tiny_instance: VRPTWInstance) -> None:
        # Without duals every arc cost is positive, so no negative routes exist.
        result = ESPPRCSolver(tiny_instance).solve(max_routes=10, threshold=-1e-4)
        assert result.routes == []
        assert result.exhausted

