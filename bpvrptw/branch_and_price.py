"""Branch-and-bound tree for exact VRPTW solving via column generation.

The class below OWNS the search tree -- the LP backends in
:mod:`bpvrptw.rmp` are pure oracles. This is the classical branch-and-price
architecture (the same one the legacy Java port follows): embedding column
generation inside a solver's own MIP tree is not possible with Gurobi/CPLEX
callbacks, so we branch ourselves and call the LP once per node.

Fixes relative to ``legacy/branchBound.py``:

* **D3** -- under the Python vertex indexing the end depot is ``n-1``, not
  ``n+1``. The old guard ``branch_to != nbclients + 1`` was always true, so
  imposing an arc INTO the depot wrongly deleted every other route's return
  arc. :func:`apply_branching` restores the intended semantics.
* **D5** -- the branching score ``routes[i].get_cost()`` (inherited from the
  upstream Java quirk) indexed a route list by *vertex id*. We use a
  principled Ryan-Foster-style score instead: among fractional edges pick
  the one closest to 0.5, tie-broken by larger true edge cost and then
  lexicographically.
* Edge integrality now accepts any integer flow (an arc into the depot may
  legitimately carry flow > 1), which the upstream window test mishandled.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

import numpy as np

from ._util import get_logger
from .column_generation import PRICING_THRESHOLD, CGResult, ColumnGeneration
from .construction import greedy_insertion_routes
from .instance import VRPTWInstance
from .solution import RouteRecord, Solution, SolutionStatus

_logger = get_logger(__name__)

_FORBIDDEN = 1e10


@dataclass
class _TreeNode:
    """One node of the branching tree."""

    father: _TreeNode | None = None
    son0: _TreeNode | None = None
    branch_from: int = -1
    branch_to: int = -1
    branch_value: int = -1
    lowest_value: float = -1e10
    toplevel: bool = False


def apply_branching(
    dist_matrix: np.ndarray,
    base_dist: np.ndarray,
    branch_from: int,
    branch_to: int,
    branch_value: int,
    *,
    end_depot: int,
    start_depot: int = 0,
) -> None:
    """Apply one branching decision to ``dist_matrix`` **in place**.

    Args:
        dist_matrix: Current working distance matrix (mutated).
        base_dist: Pristine distances used to restore arcs when needed.
        branch_from: Tail vertex of the branched arc.
        branch_to: Head vertex of the branched arc.
        branch_value: 0 forbids the arc, 1 imposes it.
        end_depot: Index of the end depot.
        start_depot: Index of the start depot.

    Semantics (mirroring the upstream design, with D3 fixed):

    * value 0 -- forbid exactly this directed arc;
    * value 1 -- from ``branch_from`` only ``branch_to`` remains reachable
      (unless branching out of the start depot: many routes may leave it),
      and into ``branch_to`` only ``branch_from`` may arrive (**unless**
      ``branch_to`` is the end depot: many routes may return there). The
      reverse arc is always forbidden.
    """
    if branch_value == 0:
        dist_matrix[branch_from, branch_to] = _FORBIDDEN
        return

    if branch_from != start_depot:
        row = dist_matrix[branch_from]
        row[:] = _FORBIDDEN
        dist_matrix[branch_from, branch_to] = float(base_dist[branch_from, branch_to])
    if branch_to != end_depot:
        col = dist_matrix[:, branch_to]
        col[:] = _FORBIDDEN
        dist_matrix[branch_from, branch_to] = float(base_dist[branch_from, branch_to])
    dist_matrix[branch_to, branch_from] = _FORBIDDEN


def _select_branch_edge(
    edges: np.ndarray,
    true_dist: np.ndarray,
) -> tuple[int, int] | None:
    """Pick the fractional edge closest to 0.5 (Ryan-Foster style).

    Ties break toward larger true edge cost and then lexicographically so
    the search stays deterministic. Returns ``None`` when integral.

    Note: flows above 1 are legitimate (several selected routes may share an
    arc into the end depot), so integrality means "within tolerance of SOME
    nonnegative integer", not just 0/1.
    """
    best_score = -1.0
    best_cost = -1.0
    best_edge: tuple[int, int] | None = None
    n = edges.shape[0]
    for i in range(n):
        for j in range(n):
            coef = edges[i, j]
            if coef <= 1e-6:
                continue
            if abs(coef - round(coef)) < 1e-8:
                continue
            frac_floor = float(coef - np.floor(coef))
            score = min(frac_floor, 1.0 - frac_floor)
            cost_ij = float(true_dist[i, j])
            if (
                score > best_score + 1e-12
                or (abs(score - best_score) <= 1e-12 and cost_ij > best_cost + 1e-12)
            ):
                best_score = float(score)
                best_cost = cost_ij
                best_edge = (i, j)
    return best_edge


def _maybe_record_incumbent(
    ctx: _BPContext,
    result: CGResult,
    verbose: bool,
    depth: int,
) -> bool:
    """Record the node's primal solution as incumbent when integral.

    Returns True when an incumbent was recorded. Used both for fully
    converged integer nodes and for partially converged nodes whose primal
    happens to be integral (the solution itself is feasible; only its
    *bound* would be unsound).
    """
    n = ctx.instance.total_vertices
    edges = np.zeros((n, n))
    for record, value in result.column_values:
        if value > 1e-6:
            for a, b in zip(record.path, record.path[1:], strict=False):
                edges[a, b] += value
    fractional = [
        (i, j)
        for i in range(n)
        for j in range(n)
        if edges[i, j] > 1e-6 and abs(edges[i, j] - round(edges[i, j])) >= 1e-8
    ]
    if fractional:
        return False
    selected = [r for r, v in result.column_values if v > 1e-6]
    total = sum(r.cost for r in selected)
    if total < ctx.upperbound:
        ctx.upperbound = total
        ctx.best_routes = [copy.deepcopy(r) for r in selected]
        if verbose:
            _logger.info(
                "INCUMBENT | UB=%.6f depth=%d nodes=%d",
                ctx.upperbound, depth, ctx.nodes_visited,
            )
    elif verbose:
        _logger.info("FEAS | UB=%.6f depth=%d", ctx.upperbound, depth)
    return True


def _path_uses_arc(route: RouteRecord, i: int, j: int) -> bool:
    return any(a == i and b == j for a, b in zip(route.path, route.path[1:], strict=False))


@dataclass
class _BPContext:
    """Mutable context threaded through the recursion."""

    instance: VRPTWInstance
    gap: float
    deadline: float | None
    started: float
    lp_solver: str
    lowerbound: float = -1e10
    upperbound: float = 1e10
    best_routes: list[RouteRecord] = field(default_factory=list)
    nodes_visited: int = 0


class BranchAndPrice:
    """Exact branch-and-price solver for VRPTW instances."""

    def __init__(
        self,
        instance: VRPTWInstance,
        *,
        lp_solver: str = "auto",
        gap: float = 1e-6,
        time_limit_seconds: float | None = None,
        verbose: bool = False,
    ) -> None:
        self._instance = instance
        self._lp_solver = lp_solver
        self._gap = gap
        self._time_limit = time_limit_seconds
        self._verbose = verbose

    def solve(self) -> Solution:
        """Run branch-and-price and return the best solution found."""
        inst = self._instance
        ctx = _BPContext(
            instance=inst,
            gap=self._gap,
            deadline=(
                time.perf_counter() + self._time_limit
                if self._time_limit is not None
                else None
            ),
            started=time.perf_counter(),
            lp_solver=self._lp_solver,
        )
        # Upper bound on any single-route length; used for the legacy-style
        # "relaxation became infeasible because arcs got forbidden" test.
        maxlength = float(np.sum(np.max(inst.dist, axis=1)))

        seed_routes: list[RouteRecord] = []
        for c in inst.customers:
            try:
                seed_routes.append(
                    RouteRecord.from_path(inst, [0, c, inst.end_depot])
                )
            except ValueError:
                continue  # this customer relies on multi-customer routes
        if not seed_routes:
            # Not even one customer can be served alone -> no feasible
            # solution exists.
            return Solution(
                status=SolutionStatus.INFEASIBLE,
                routes=[],
                total_cost=0.0,
                lower_bound=None,
                solve_time_seconds=time.perf_counter() - ctx.started,
                instance_name=inst.name,
                meta={"bb_nodes": 0, "lp_solver": ctx.lp_solver,
                      "gap_closed": False, "gap_pct": None},
            )

        def _node(
            node: _TreeNode,
            dist_matrix: np.ndarray,
            routes: list[RouteRecord],
            depth: int,
        ) -> bool:
            ctx.nodes_visited += 1
            if ctx.deadline is not None and time.perf_counter() > ctx.deadline:
                _logger.warning("time limit hit at depth %d; stopping search", depth)
                return True

            if (ctx.upperbound - ctx.lowerbound) / max(ctx.upperbound, 1e-10) < ctx.gap:
                return True

            arc_allowed = dist_matrix < (_FORBIDDEN - 1e6)
            cg = ColumnGeneration(inst, lp_solver=ctx.lp_solver)
            remaining: float | None = None
            if ctx.deadline is not None:
                remaining = max(0.01, ctx.deadline - time.perf_counter())
            try:
                result = cg.solve(
                    seed_columns=list(routes),
                    arc_allowed=arc_allowed,
                    time_limit_seconds=remaining,
                )
            except RuntimeError as exc:
                # The master problem cannot even be seeded under these
                # branching constraints -> this subtree is infeasible.
                _logger.debug("node infeasible at depth %d: %s", depth, exc)
                node.lowest_value = 1e11
                return True

            # Infeasible relaxation detection (same convention as legacy):
            # forbidden arcs inflate column costs beyond any real solution.
            if result.objective > 2 * maxlength or result.objective < PRICING_THRESHOLD:
                if self._verbose:
                    _logger.info(
                        "RELAX INFEASIBLE | depth=%d obj=%.4f", depth, result.objective
                    )
                node.lowest_value = 1e11
                return True

            if result.status != "optimal":
                # Pricing did not run to exhaustion: the current RMP objective
                # is NOT a valid global lower bound. Record an integral
                # incumbent if the partial solution happens to be integral,
                # then stop descending -- branching on unproven bounds would
                # make every downstream claim unsound.
                _maybe_record_incumbent(ctx, result, self._verbose, depth)
                return True

            node.lowest_value = result.objective
            # Global lower-bound bookkeeping (identical structure to legacy).
            if (
                node.father is not None
                and node.father.son0 is not None
                and node.father.toplevel
            ):
                ctx.lowerbound = min(node.lowest_value, node.father.son0.lowest_value)
                node.toplevel = True
            elif node.father is None:
                ctx.lowerbound = result.objective

            if node.lowest_value > ctx.upperbound:
                if self._verbose:
                    _logger.info(
                        "CUT | LB=%.6f UB=%.6f depth=%d",
                        ctx.lowerbound, ctx.upperbound, depth,
                    )
                return True

            # Edge-usage matrix of this node's LP solution.
            n = inst.total_vertices
            edges = np.zeros((n, n))
            for record, value in result.column_values:
                if value > 1e-6:
                    for a, b in zip(record.path, record.path[1:], strict=False):
                        edges[a, b] += value

            fractional = [
                (i, j)
                for i in range(n)
                for j in range(n)
                if edges[i, j] > 1e-6 and abs(edges[i, j] - round(edges[i, j])) >= 1e-8
            ]
            if not fractional:
                _maybe_record_incumbent(ctx, result, self._verbose, depth)
                return True
            bf, bt = _select_branch_edge(edges, inst.dist) or fractional[0]
            coef = edges[bf, bt]
            best_val = 0 if abs(1.0 - coef) > coef else 1
            if self._verbose:
                _logger.info(
                    "INTEG INFEAS | LB=%.6f UB=%.6f depth=%d branch %d->%d val=%d",
                    ctx.lowerbound, ctx.upperbound, depth, bf, bt, best_val,
                )

            # ---- Child 1 -------------------------------------------------
            child1 = _TreeNode(
                father=node, branch_from=bf, branch_to=bt, branch_value=best_val
            )
            dist1 = dist_matrix.copy()
            apply_branching(
                dist1, inst.dist, bf, bt, best_val,
                end_depot=inst.end_depot, start_depot=inst.start_depot,
            )
            keep1 = [
                r for r in routes if len(r.path) <= 3 or not _path_uses_arc(r, bf, bt)
            ]
            ok1 = _node(child1, dist1, keep1, depth + 1)
            node.son0 = child1
            if not ok1:
                return False

            # ---- Child 2: rebuild constraints from the pristine matrix ---
            child2 = _TreeNode(
                father=node, branch_from=bf, branch_to=bt, branch_value=1 - best_val
            )
            dist2 = inst.dist.copy()
            chain: list[_TreeNode] = []
            walker: _TreeNode | None = node
            while walker is not None and walker.branch_from >= 0:
                chain.append(walker)
                walker = walker.father
            for anc in reversed(chain):
                apply_branching(
                    dist2, inst.dist, anc.branch_from, anc.branch_to, anc.branch_value,
                    end_depot=inst.end_depot, start_depot=inst.start_depot,
                )
            apply_branching(
                dist2, inst.dist, bf, bt, 1 - best_val,
                end_depot=inst.end_depot, start_depot=inst.start_depot,
            )
            keep2 = [
                r
                for r in routes
                if len(r.path) <= 3
                or all(
                    dist2[a, b] < _FORBIDDEN - 1e-6
                    for a, b in zip(r.path, r.path[1:], strict=False)
                )
            ]
            ok2 = _node(child2, dist2, keep2, depth + 1)
            node.lowest_value = min(child1.lowest_value, child2.lowest_value)
            return ok2

        root = _TreeNode(toplevel=True)

        # Initial incumbent: prefer the construction heuristic's solution
        # (much tighter than all-single-customer routes); extend it with
        # solo routes for any customer the heuristic could not place, and
        # fall back to the pure singles solution when construction found
        # nothing. Guarantees a feasible UB even for starved runs.
        initial_pool = list(seed_routes)
        constructed = greedy_insertion_routes(inst)
        if constructed:
            covered: set[int] = set()
            for route in constructed:
                covered.update(route.path[1:-1])
                initial_pool.append(route)
            for c in inst.customers:
                if c not in covered:
                    try:
                        initial_pool.append(
                            RouteRecord.from_path(inst, [0, c, inst.end_depot])
                        )
                    except ValueError:
                        continue
            missing = [
                c for c in inst.customers
                if all(c not in r.path[1:-1] for r in constructed)
            ]
            if not missing and sum(
                r.load for r in constructed
            ) <= inst.capacity * inst.vehicle_count + 1e-9:
                # The heuristic covers everyone -> a valid incumbent.
                ctx.upperbound = sum(r.cost for r in constructed)
                ctx.best_routes = [copy.deepcopy(r) for r in constructed]
        elif seed_routes:
            ctx.upperbound = sum(r.cost for r in seed_routes)
            ctx.best_routes = list(seed_routes)
            ctx.upperbound = sum(r.cost for r in seed_routes)
            ctx.best_routes = list(seed_routes)

        _node(root, inst.dist.copy(), list(initial_pool), 0)

        timed_out = ctx.deadline is not None and time.perf_counter() > ctx.deadline
        lb_valid = ctx.lowerbound > -1e9
        gap_closed = (
            lb_valid
            and bool(ctx.best_routes)
            and (ctx.upperbound - ctx.lowerbound) / max(abs(ctx.upperbound), 1e-10)
            < self._gap
        )
        if not ctx.best_routes:
            status = SolutionStatus.INFEASIBLE
        elif gap_closed and not timed_out:
            status = SolutionStatus.SOLVED_OPTIMAL
        elif timed_out:
            status = SolutionStatus.TIME_LIMIT
        else:
            status = SolutionStatus.SOLVED_FEASIBLE
        return Solution(
            status=status,
            routes=list(ctx.best_routes),
            total_cost=sum(r.cost for r in ctx.best_routes),
            lower_bound=ctx.lowerbound if lb_valid else None,
            solve_time_seconds=time.perf_counter() - ctx.started,
            instance_name=inst.name,
            meta={
                "bb_nodes": ctx.nodes_visited,
                "lp_solver": ctx.lp_solver,
                "gap_closed": gap_closed,
                "gap_pct": (
                    None
                    if not lb_valid or not ctx.best_routes
                    else max(
                        0.0,
                        (ctx.upperbound - ctx.lowerbound)
                        / max(abs(ctx.upperbound), 1e-10)
                        * 100.0,
                    )
                ),
            },
        )
