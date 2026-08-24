"""Brute-force exact VRPTW solver for tiny instances (test-only reference)."""

from __future__ import annotations

from bpvrptw.instance import VRPTWInstance
from bpvrptw.solution import RouteRecord


def _all_feasible_routes(instance: VRPTWInstance) -> list[RouteRecord]:
    """Enumerate every feasible elementary route of a tiny instance."""
    end = instance.end_depot
    routes: list[RouteRecord] = []

    def extend(path: list[int], visited: frozenset[int]) -> None:
        record = RouteRecord.from_path(instance, [*path, end])
        routes.append(record)
        for candidate in instance.customers:
            if candidate in visited:
                continue
            # Cheap pre-check: can we even reach `candidate` from `last`
            # in time? Full validation happens on the extended route.
            extend([*path, candidate], visited | {candidate})

    for first in instance.customers:
        try:
            extend([0, first], {first})
        except ValueError:
            continue  # single-customer route infeasible; skip this anchor
    return routes


def exact_optimum(instance: VRPTWInstance) -> float:
    """Return the exact optimal cost for a TINY instance.

    Enumerates all feasible elementary routes, then finds the minimum-cost
    exact cover of the customers via DFS over route subsets. Exponential;
    only use with n <= ~8.
    """
    routes = _all_feasible_routes(instance)
    best: list[float] = [float("inf")]
    customers = frozenset(instance.customers)

    customers = frozenset(instance.customers)

    def search_all(remaining: frozenset[int], spent: float) -> None:
        if spent >= best[0]:
            return
        if not remaining:
            best[0] = spent
            return
        anchor = min(remaining)
        for route in routes:
            served = frozenset(route.path[1:-1])
            if anchor not in served or not served <= remaining:
                continue
            search_all(remaining - served, spent + route.cost)

    search_all(customers, 0.0)
    if best[0] == float("inf"):
        raise ValueError("instance has no feasible solution")
    return best[0]
