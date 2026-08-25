"""Construction heuristics: fast feasible solutions to seed column generation.

The classic weakness of column generation implementations is a poor
starting RMP: with only single-customer seed columns the master problem
needs many pricing rounds to discover useful routes. This module provides
a deterministic parallel cheapest-feasible-insertion heuristic (in the
spirit of Solomon's I1, simplified) whose routes are added as initial
columns and whose solution doubles as a strong initial upper bound for
the branch-and-price tree.
"""

from __future__ import annotations

import numpy as np

from bpvrptw.instance import VRPTWInstance
from bpvrptw.solution import InfeasibleRouteError, RouteRecord


def greedy_insertion_routes(
    instance: VRPTWInstance,
    *,
    arc_allowed: np.ndarray | None = None,
) -> list[RouteRecord]:
    """Build a feasible solution by parallel cheapest feasible insertion.

    Customers are inserted one at a time at their globally cheapest
    feasible position (over all existing routes and all insertion slots);
    when nothing can be inserted, a new route is opened for the
    lowest-index unvisited customer that can be served alone. Customers
    that cannot be served by any constructed route are skipped - callers
    (column generation) cover them through pricing instead.

    Deterministic: ties break on customer index, then route index, then
    insertion slot.

    Args:
        instance: The instance to construct a solution for.
        arc_allowed: Optional boolean matrix of admissible arcs
            (branching constraints); forbidden arcs are never used.

    Returns:
        The constructed routes (possibly empty when no route at all is
        feasible under ``arc_allowed``).
    """
    end = instance.end_depot

    def ok(a: int, b: int) -> bool:
        return arc_allowed is None or bool(arc_allowed[a, b])

    def feasible(path: list[int]) -> RouteRecord | None:
        try:
            return RouteRecord.from_path(instance, path)
        except InfeasibleRouteError:
            return None

    routes: list[list[int]] = []
    unvisited: list[int] = list(instance.customers)

    def open_route() -> bool:
        """Open a solo route for the lowest-index servable customer."""
        for idx, c in enumerate(unvisited):
            if not ok(0, c) or not ok(c, end):
                continue
            record = feasible([0, c, end])
            if record is not None:
                routes.append([0, c, end])
                unvisited.pop(idx)
                return True
        return False

    if unvisited:
        open_route()

    while unvisited:
        best: tuple[float, int, int, int] | None = None
        # (delta_cost, customer, route_index, insertion_slot)
        for ri, path in enumerate(routes):
            base = sum(
                float(instance.dist[a, b])
                for a, b in zip(path, path[1:], strict=False)
            )
            for slot in range(1, len(path)):
                i, j = path[slot - 1], path[slot]
                for c in unvisited:
                    if c == i or c == j or not ok(i, c) or not ok(c, j):
                        continue
                    candidate = path[:slot] + [c] + path[slot:]
                    record = feasible(candidate)
                    if record is None:
                        continue
                    delta = record.cost - base
                    key = (delta, c, ri, slot)
                    if best is None or key < best:
                        best = key
        if best is None:
            # Nothing fits anywhere: open another route (or give up).
            if not open_route():
                break
            continue
        delta, c, ri, slot = best
        del delta
        routes[ri] = routes[ri][:slot] + [c] + routes[ri][slot:]
        unvisited.remove(c)

    records: list[RouteRecord] = []
    for path in routes:
        record = feasible(path)
        if record is not None:
            records.append(record)
    return records
