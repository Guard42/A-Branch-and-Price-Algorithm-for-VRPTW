"""Column generation for the VRPTW master problem.

The restricted master problem (RMP) is maintained by a pluggable LP backend
(:mod:`bpvrptw.rmp`) that is built ONCE per node and extended incrementally
as pricing returns new columns -- no model rebuilding, full simplex warm
start between iterations (this replaces the legacy rebuild-everything loop,
defect D4).

Pricing uses the bounded ESPPRC solver in :mod:`bpvrptw.labeling` with arc
costs ``rc[i][j] = dist[i][j] - pi[i]`` where ``pi`` are the coverage duals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ._util import get_logger
from .instance import VRPTWInstance
from .labeling import ESPPRCSolver
from .rmp import make_backend
from .solution import RouteRecord

_logger = get_logger(__name__)

#: A pricing column must be at least this negative to be worth adding.
PRICING_THRESHOLD = -1e-4


class MasterInfeasibleError(RuntimeError):
    """Raised when even the seed columns cannot make the RMP feasible."""

@dataclass
class CGResult:
    """Outcome of one column-generation run."""

    objective: float
    iterations: int
    n_columns: int
    #: ``"optimal" | "iteration_limit" | "time_limit"``
    status: str
    #: Every column paired with its primal value in the final RMP solve.
    column_values: list[tuple[RouteRecord, float]] = field(default_factory=list)
    #: Valid global lower bound for the set-partitioning relaxation.
    lower_bound: float = 0.0


def default_seed_columns(
    instance: VRPTWInstance,
    arc_allowed: np.ndarray | None = None,
) -> list[RouteRecord]:
    """Single-customer routes ``0 -> c -> end`` that are feasible.

    When ``arc_allowed`` is given (branch-and-price mode), routes using a
    forbidden arc are skipped; the customer then relies on pricing.
    """
    seeds: list[RouteRecord] = []
    for customer in instance.customers:
        path = [0, customer, instance.end_depot]
        if arc_allowed is not None and not (
            arc_allowed[0, customer] and arc_allowed[customer, instance.end_depot]
        ):
            continue
        try:
            seeds.append(RouteRecord.from_path(instance, path))
        except ValueError:
            _logger.warning(
                "single-customer route through customer %d is infeasible; "
                "pricing must cover this customer",
                customer,
            )
    if not seeds:
        raise MasterInfeasibleError("no feasible single-customer route exists")
    return seeds

class ColumnGeneration:
    """Column generation over one fixed instance and one LP backend."""

    def __init__(
        self,
        instance: VRPTWInstance,
        *,
        lp_solver: str = "auto",
    ) -> None:
        self._instance = instance
        self._lp_solver = lp_solver

    def solve(
        self,
        *,
        seed_columns: list[RouteRecord] | None = None,
        max_iterations: int = 500,
        time_limit_seconds: float | None = None,
        pricing_max_routes: int | None = None,
        arc_allowed: np.ndarray | None = None,
    ) -> CGResult:
        """Run column generation until pricing finds no improving column.

        Args:
            seed_columns: Initial feasible routes; defaults to all feasible
                single-customer routes.
            max_iterations: Safety cap on pricing rounds.
            time_limit_seconds: Optional wall-clock budget.
            pricing_max_routes: Routes requested per pricing round; defaults
                to ``min(n_customers, 20)``.
            arc_allowed: Optional boolean matrix of admissible arcs; forbidden
                arcs are excluded from seeding, pricing and column acceptance
                (branch-and-price branching constraints).

        Returns:
            A :class:`CGResult`. At convergence ``objective`` equals the LP
            relaxation bound of the full (non-restricted) master problem and
            is therefore a valid global lower bound.
        """
        started = time.perf_counter()
        inst = self._instance
        seeds = (
            seed_columns
            if seed_columns is not None
            else default_seed_columns(inst, arc_allowed)
        )
        # Column order inside the backend: seeds first, then priced columns
        # in insertion order -- mirrored in ``records`` below.
        records: list[RouteRecord] = list(seeds)
        backend = make_backend(
            self._lp_solver, inst, [(r.cost, list(r.path[1:-1])) for r in seeds]
        )
        try:
            pricing_routes = (
                pricing_max_routes
                if pricing_max_routes is not None
                else min(inst.n_customers, 20)
            )

            iterations = 0
            status = "optimal"
            solution = backend.solve()

            while True:
                duals = solution.duals
                # rc[i][j] = dist[i][j] - duals[i-1] for interior i; depot
                # rows keep zero shift so their arcs retain distance cost.
                shift = np.concatenate(([0.0], duals[: inst.n_customers], [0.0]))
                rc_matrix = inst.dist - shift[:, None]

                remaining: float | None = None
                if time_limit_seconds is not None:
                    remaining = max(0.01, time_limit_seconds - (time.perf_counter() - started))
                priced = ESPPRCSolver(
                    inst, rc_matrix, arc_allowed=arc_allowed
                ).solve(
                    max_routes=pricing_routes,
                    threshold=PRICING_THRESHOLD,
                    time_limit_seconds=remaining,
                )
                if priced.routes and not priced.exhausted and (
                    time_limit_seconds is not None
                    and time.perf_counter() - started >= time_limit_seconds
                ):
                    status = "time_limit"
                    break
                fresh = priced.routes
                if not fresh:
                    break

                iterations += 1
                if iterations >= max_iterations:
                    status = "iteration_limit"
                    break
                if time_limit_seconds is not None and (
                    time.perf_counter() - started > time_limit_seconds
                ):
                    status = "time_limit"
                    break

                for route in fresh:
                    record = RouteRecord.from_path(inst, list(route.path))
                    records.append(record)
                    backend.add_column(record.cost, list(route.path[1:-1]))
                solution = backend.solve()
                _logger.debug(
                    "CG iter %d: objective %.6f (+%d columns)",
                    iterations,
                    solution.objective,
                    len(fresh),
                )

            objective = solution.objective
        finally:
            backend.close()

        _logger.info(
            "CG done: status=%s objective=%.6f iterations=%d columns=%d (%.2fs)",
            status,
            objective,
            iterations,
            len(records),
            time.perf_counter() - started,
        )
        return CGResult(
            objective=objective,
            iterations=iterations,
            n_columns=len(records),
            status=status,
            column_values=[
                (record, value)
                for record, value in zip(records, solution.primal, strict=False)
            ],
            lower_bound=objective,
        )
