"""Elementary shortest path problem with resource constraints (ESPPRC).

This module implements the pricing subproblem solver used by column
generation: a label-setting algorithm over elementary routes returning
paths from the start depot to the end depot whose *reduced cost* is below
a threshold.

The implementation fixes the defects of the legacy ``SPPRC.py`` port (see
``legacy/README.md``):

* **D1/D9** -- labels are processed best-first by reduced cost (a heap keyed
  on ``(cost, city, time, load, mask)``) and returned columns are the most
  negative ones first, instead of insertion-order processing/selection.
* **D2** -- ordering never relies on a pairwise comparator; ties break
  deterministically on the label key plus an insertion counter.
* **D8** -- the search is bounded by ``max_labels`` and an optional wall
  clock budget; hitting a bound degrades gracefully instead of hanging.
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass

import numpy as np

from ._util import get_logger
from .instance import VRPTWInstance

_logger = get_logger(__name__)

#: Numerical slack for resource comparisons.
_EPS = 1e-9


@dataclass(frozen=True)
class PricedRoute:
    """An elementary route produced by pricing, with its costs."""

    #: Full vertex sequence including both depots: ``(0, customers..., n-1)``.
    path: tuple[int, ...]
    #: Reduced cost under the dual values used for this pricing round.
    reduced_cost: float
    #: True travel cost (sum of distances along the path).
    true_cost: float


@dataclass(frozen=True)
class PricingResult:
    """Outcome of one pricing call."""

    #: Candidate routes with reduced cost below the threshold, most negative first.
    routes: list[PricedRoute]
    #: Number of labels created during the search.
    n_labels_explored: int
    #: True when the search terminated exhaustively (no cap hit).
    exhausted: bool
    elapsed_seconds: float


class _Label:
    """A partial path ending at ``city`` with its resource vector."""

    __slots__ = ("city", "parent", "cost", "time", "load", "mask")

    def __init__(
        self,
        city: int,
        parent: int | None,
        cost: float,
        time: float,
        load: float,
        mask: int,
    ) -> None:
        self.city = city
        self.parent = parent
        self.cost = cost
        self.time = time
        self.load = load
        self.mask = mask


def _dominates(
    cost_a: float, time_a: float, load_a: float, mask_a: int, idx_a: int,
    cost_b: float, time_b: float, load_b: float, mask_b: int, idx_b: int,
) -> bool:
    """Return True when label *a* dominates label *b*.

    Standard ESPPRC dominance: *a* reaches a subset of *b*'s vertices with
    each resource no worse, and is strictly better somewhere. Two labels
    that tie on everything (the permutation-equivalent case under symmetric
    distances) resolve to their insertion order, so duplicates die young.
    """
    if (mask_a & mask_b) != mask_a:
        return False
    weak = (
        cost_a <= cost_b + _EPS
        and time_a <= time_b + _EPS
        and load_a <= load_b + _EPS
    )
    if not weak:
        return False
    strict = (
        cost_a < cost_b - _EPS
        or time_a < time_b - _EPS
        or load_a < load_b - _EPS
        or mask_a != mask_b
    )
    if strict:
        return True
    # Full tie: the earlier label wins.
    return idx_a < idx_b


class ESPPRCSolver:
    """Best-first, bounded ESPPRC label-setting solver.

    Args:
        instance: The VRPTW instance to price on.
        reduced_costs: Optional arc cost matrix overriding ``instance.dist``
            as the arc objective (column generation passes ``dist - pi``).
    """
    def __init__(
        self,
        instance: VRPTWInstance,
        reduced_costs: np.ndarray | None = None,
        *,
        arc_allowed: np.ndarray | None = None,
    ) -> None:
        """Create a pricing solver.

        Args:
            instance: The VRPTW instance to price on.
            reduced_costs: Optional arc objective overriding ``instance.dist``
                (column generation passes ``dist - pi``).
            arc_allowed: Optional boolean matrix of admissible arcs (used by
                branch-and-price to encode forbidden arcs). When given,
                Feillet-style pruning is disabled: with forbidden arcs the
                triangle-inequality argument that makes pruning safe no
                longer holds.
        """
        self._instance = instance
        self._rc = instance.dist if reduced_costs is None else np.asarray(reduced_costs)
        # An all-True matrix is semantically "no restriction"; normalizing
        # it to None keeps Feillet pruning active at the root node.
        if arc_allowed is not None and bool(np.all(arc_allowed)):
            arc_allowed = None
        self._arc_allowed = arc_allowed

    def solve(
        self,
        *,
        max_routes: int = 10,
        threshold: float = -1e-6,
        max_labels: int = 2_000_000,
        time_limit_seconds: float | None = None,
    ) -> PricingResult:
        """Run the labeling search.

        Args:
            max_routes: Maximum number of routes to return.
            threshold: Collect only routes with reduced cost strictly below
                this value.
            max_labels: Hard cap on created labels; exceeding it stops the
                search gracefully (``exhausted=False``).
            time_limit_seconds: Optional wall-clock cap with the same graceful
                degradation.

        Returns:
            A :class:`PricingResult`; routes sorted by reduced cost ascending.
        """
        started = time.perf_counter()
        inst = self._instance
        n = inst.total_vertices
        rc = self._rc
        dist = inst.dist
        speed = inst.speed
        demand = inst.demand
        ready = inst.ready_time
        due = inst.due_time
        service = inst.service_time
        start = inst.start_depot
        end = inst.end_depot
        capacity = inst.capacity
        customer_range = range(1, n - 1)

        labels: list[_Label] = []
        counter = itertools.count()
        start_mask = 1 << start
        labels.append(_Label(start, None, 0.0, 0.0, 0.0, start_mask))

        # Heap entries: (cost, city, time, load, mask, tiebreak, label_index)
        heap: list[tuple[float, int, float, float, int, int, int]] = [
            (0.0, start, 0.0, 0.0, start_mask, next(counter), 0)
        ]

        # Per-city undominated label registry: (cost, time, load, mask, idx).
        buckets: list[list[tuple[float, float, float, int, int]]] = [[] for _ in range(n)]

        candidates: list[tuple[float, int]] = []
        seen_route_sets: dict[frozenset[int], int] = {}
        n_labels = 1
        exhausted = True

        def _prune_mask(mask: int, city: int, arrival: float, load: float) -> int:
            """Feillet-style: mark customers unreachable from here as visited."""
            if self._arc_allowed is not None:
                return mask  # unsafe under forbidden arcs; keep completeness
            for k in customer_range:
                if not (mask >> k) & 1:
                    earliest = arrival + float(dist[city, k]) / speed + service[city]
                    if earliest > due[k] + _EPS or load + demand[k] > capacity + _EPS:
                        mask |= 1 << k
            return mask

            for k in customer_range:
                if not (mask >> k) & 1:
                    earliest = arrival + float(dist[city, k]) / speed + service[city]
                    if earliest > due[k] + _EPS or load + demand[k] > capacity + _EPS:
                        mask |= 1 << k
            return mask

        while heap:
            if time_limit_seconds is not None:
                if time.perf_counter() - started > time_limit_seconds:
                    _logger.warning(
                        "pricing time limit (%.1fs) reached; returning partial result",
                        time_limit_seconds,
                    )
                    exhausted = False
                    break
            if n_labels >= max_labels:
                _logger.warning(
                    "pricing label cap (%d) reached; returning partial result", max_labels
                )
                exhausted = False
                break

            entry = heapq.heappop(heap)
            idx = entry[-1]
            label = labels[idx]
            bucket = buckets[label.city]

            # Re-check dominance at pop time (newer labels may dominate us).
            dominated = False
            kept: list[tuple[float, float, float, int, int]] = []
            for item in bucket:
                cost_o, time_o, load_o, mask_o, idx_o = item
                if idx_o != idx and _dominates(
                    cost_o, time_o, load_o, mask_o, idx_o,
                    label.cost, label.time, label.load, label.mask, idx,
                ):
                    dominated = True
                    kept = bucket  # do not purge on self-drop
                    break
                if not _dominates(
                    label.cost, label.time, label.load, label.mask, idx,
                    cost_o, time_o, load_o, mask_o, idx_o,
                ):
                    kept.append(item)
            if dominated:
                continue
            buckets[label.city] = kept
            kept.append((label.cost, label.time, label.load, label.mask, idx))

            # Extend to every admissible unvisited vertex.
            base_time = label.time
            base_load = label.load
            base_city = label.city
            for j in range(n):
                if j == base_city or j == start or (label.mask >> j) & 1:
                    continue
                if (
                    self._arc_allowed is not None
                    and not self._arc_allowed[base_city, j]
                ):
                    continue  # branching forbade this arc
                if base_city == start and j == end:
                    continue  # a route needs at least one customer
                arrival = base_time + float(dist[base_city, j]) / speed + service[base_city]
                if arrival < ready[j]:
                    arrival = float(ready[j])
                new_load = base_load + demand[j]
                if arrival > due[j] + _EPS or new_load > capacity + _EPS:
                    continue
                new_cost = label.cost + float(rc[base_city, j])
                new_mask = label.mask | (1 << j)

                if j == end:
                    key = frozenset(k for k in customer_range if (new_mask >> k) & 1)
                    prev = seen_route_sets.get(key)
                    if prev is not None and labels[prev].cost <= new_cost + _EPS:
                        continue  # permutation duplicate; keep the first
                    labels.append(_Label(j, idx, new_cost, arrival, new_load, new_mask))
                    child_idx = len(labels) - 1
                    seen_route_sets[key] = child_idx
                    n_labels += 1
                    if new_cost < threshold:
                        candidates.append((new_cost, child_idx))
                    continue

                child_mask = _prune_mask(new_mask, j, arrival, new_load)
                # Creation-time dominance filter against this city's bucket.
                # A huge tie-break index lets the incumbent win full ties,
                # which kills permutation-equivalent duplicates early.
                if any(
                    _dominates(
                        c, t, load, m, i,
                        new_cost, arrival, new_load, child_mask, 1 << 60,
                    )
                    for c, t, load, m, i in buckets[j]
                ):
                    continue
                labels.append(_Label(j, idx, new_cost, arrival, new_load, child_mask))
                child_idx = len(labels) - 1
                n_labels += 1
                heapq.heappush(
                    heap,
                    (new_cost, j, arrival, new_load, child_mask, next(counter), child_idx),
                )

        # Reconstruct the best `max_routes` candidates, most negative first.
        # Deduplicate permutation-equivalent routes again at extraction time
        # (a cheaper duplicate can replace an earlier candidate above).
        routes: list[PricedRoute] = []
        emitted: set[frozenset[int]] = set()
        for cost, idx in sorted(candidates, key=lambda pair: (pair[0], pair[1])):
            walk_path: list[int] = []
            walk: int | None = idx
            while walk is not None:
                walk_path.append(labels[walk].city)
                walk = labels[walk].parent
            walk_path.reverse()
            true_cost = sum(
                float(dist[a, b]) for a, b in zip(walk_path, walk_path[1:], strict=False)
            )
            key_set = frozenset(walk_path[1:-1])
            if key_set in emitted:
                continue
            emitted.add(key_set)
            routes.append(
                PricedRoute(path=tuple(walk_path), reduced_cost=float(cost), true_cost=true_cost)
            )
            if len(routes) >= max_routes:
                break

        elapsed = time.perf_counter() - started
        _logger.debug(
            "pricing done: %d labels, %d candidates, exhausted=%s, %.3fs",
            n_labels,
            len(candidates),
            exhausted,
            elapsed,
        )
        return PricingResult(
            routes=routes,
            n_labels_explored=n_labels,
            exhausted=exhausted,
            elapsed_seconds=elapsed,
        )
