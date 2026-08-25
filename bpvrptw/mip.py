"""Direct Gurobi MIP formulation of the VRPTW (the textbook baseline).

Arc-based binary formulation with big-M time and load propagation:

    min  sum_{i != j} d_ij * x_ij
    s.t. sum_j x_0j <= K                          (fleet bound)
         sum_i x_ij == 1          j customers     (arrive once)
         sum_j x_ij == 1          i customers     (leave once)
         a_j <= t_j <= b_j        j customers     (time windows)
         t_j >= t_i + s_i + tt_ij - M(1-x_ij)     (time propagation)
         w_i + q_j <= w_j + M(1-x_ij);  w_c in [q_c, Q]   (capacity)
         x binary

The time propagation eliminates any customer-only subtour (service and
travel times are strictly positive along used arcs), so no separate
subtour constraints are needed.

This is NOT the algorithm this library teaches - it exists so benchmarks
can compare the branch-and-price approach against a plain commercial-solver
model on identical instances.
"""

from __future__ import annotations

import time

import numpy as np

from ._util import get_logger
from .instance import VRPTWInstance
from .solution import RouteRecord, Solution, SolutionStatus

_logger = get_logger(__name__)


def solve_mip(
    instance: VRPTWInstance,
    *,
    time_limit_seconds: float | None = None,
    verbose: bool = False,
) -> Solution:
    """Solve the VRPTW with a direct arc-based Gurobi MIP model.

    Args:
        instance: The instance to solve.
        time_limit_seconds: Optional solver wall-clock budget.
        verbose: Let Gurobi print its log to stdout.

    Returns:
        A :class:`Solution` built from the MIP routes.
    """
    import gurobipy as gp
    from gurobipy import GRB

    started = time.perf_counter()
    inst = instance
    n = inst.total_vertices
    end = inst.end_depot

    arcs = [
        (i, j)
        for i in range(n)
        for j in range(n)
        if i != j
        and i != end
        and j != 0
        and not (i == 0 and j == end)
    ]
    dist = inst.dist
    tt = dist / inst.speed
    service = inst.service_time
    demand = inst.demand
    customers = list(inst.customers)

    # Sufficiently large constants for the two propagations.
    big_m_time = float(np.max(inst.due_time) + np.max(tt) + np.max(service))
    big_m_load = float(inst.capacity)

    model = gp.Model("bpvrptw-mip")
    if not verbose:
        model.setParam("OutputFlag", 0)

    x = model.addVars(arcs, vtype=GRB.BINARY, name="x")
    t = model.addVars(range(n), lb=0.0, name="t")
    load = model.addVars(customers, lb=0.0, ub=inst.capacity, name="w")

    model.setObjective(
        gp.quicksum(float(dist[i, j]) * x[i, j] for i, j in arcs),
        GRB.MINIMIZE,
    )

    model.addConstr(
        gp.quicksum(x[0, j] for _, j in arcs if _ == 0) <= inst.vehicle_count,
        name="depot_out",
    )
    model.addConstr(
        gp.quicksum(x[i, end] for i, _ in arcs if _ == end) <= inst.vehicle_count,
        name="depot_in",
    )

    for c in customers:
        model.addConstr(
            gp.quicksum(x[i, c] for i, _ in arcs if _ == c) == 1, name=f"in_{c}"
        )
        model.addConstr(
            gp.quicksum(x[c, j] for _, j in arcs if _ == c) == 1, name=f"out_{c}"
        )
        model.addConstr(t[c] >= float(inst.ready_time[c]), name=f"ready_{c}")
        model.addConstr(t[c] <= float(inst.due_time[c]), name=f"due_{c}")
        model.addConstr(load[c] >= float(inst.demand[c]), name=f"minload_{c}")

    for i, j in arcs:
        if j == 0:
            continue  # customers never enter the start depot
        if i == 0:
            # Departure from the start depot: clock starts at the depot's
            # ready time.
            model.addConstr(
                t[j]
                >= float(inst.ready_time[0]) + float(tt[0, j])
                - big_m_time * (1 - x[0, j]),
                name=f"time_0_{j}",
            )
            continue
        arrival_j = t[i] + float(service[i]) + float(tt[i, j])
        model.addConstr(
            t[j] >= arrival_j - big_m_time * (1 - x[i, j]),
            name=f"time_{i}_{j}",
        )
        if j != end:
            model.addConstr(
                load[j] >= load[i] + float(demand[j])
                - big_m_load * (1 - x[i, j]),
                name=f"load_{i}_{j}",
            )

    # End-depot arrival window.
    model.addConstr(t[end] >= float(inst.ready_time[end]))
    model.addConstr(t[end] <= float(inst.due_time[end]))

    model.optimize()

    status_map = {
        GRB.OPTIMAL: SolutionStatus.SOLVED_OPTIMAL,
        GRB.TIME_LIMIT: SolutionStatus.TIME_LIMIT,
        GRB.INFEASIBLE: SolutionStatus.INFEASIBLE,
    }
    status = status_map.get(model.Status, SolutionStatus.ERROR)
    total_cost = float(model.ObjVal) if model.SolCount > 0 else 0.0

    routes: list[RouteRecord] = []
    if model.SolCount > 0:
        used = [a for a in arcs if x[a].X > 0.5]
        successors: dict[int, int] = {}
        depot_starts: list[int] = []
        for i, j in used:
            if i == 0:
                depot_starts.append(j)
            else:
                successors[i] = j
        for first in sorted(depot_starts):
            path = [0, first]
            city = first
            while city != end:
                city = successors[city]
                path.append(city)
            try:
                routes.append(RouteRecord.from_path(inst, path))
            except ValueError as exc:
                _logger.warning("MIP produced an invalid route: %s (%s)",
                                path, exc)

    lower_bound: float | None = None
    if model.SolCount > 0:
        lower_bound = float(model.ObjBound)

    return Solution(
        status=status,
        routes=routes,
        total_cost=total_cost,
        lower_bound=lower_bound,
        solve_time_seconds=time.perf_counter() - started,
        instance_name=inst.name,
        meta={
            "method": "mip",
            "gurobi_status": int(model.Status),
            "nodes": int(model.NodeCount),
        },
    )
