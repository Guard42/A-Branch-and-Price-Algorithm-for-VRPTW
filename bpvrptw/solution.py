"""Solution model: routes, statuses, feasibility checks and JSON round-trip."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .instance import VRPTWInstance

_TOL = 1e-6


class SolutionStatus(str, Enum):
    """Outcome of a solver run."""

    SOLVED_OPTIMAL = "SOLVED_OPTIMAL"
    SOLVED_FEASIBLE = "SOLVED_FEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


class InfeasibleRouteError(ValueError):
    """Raised when a route violates capacity or time-window constraints."""


@dataclass(eq=True)
class RouteRecord:
    """A single vehicle route with its computed resources.

    Attributes:
        path: Vertex sequence ``[start_depot, customers..., end_depot]``.
        cost: Sum of travel distances along the path.
        load: Total demand of the interior customers.
        duration: Arrival time at the end depot (waiting allowed).
    """

    path: list[int]
    cost: float
    load: float
    duration: float

    @classmethod
    def from_path(cls, instance: VRPTWInstance, path: list[int]) -> RouteRecord:
        """Build a record by recomputing resources from the instance.

        Args:
            instance: The instance the path refers to.
            path: ``[0, customer..., n-1]`` vertex sequence.

        Returns:
            The validated route record.

        Raises:
            InfeasibleRouteError: If the path is structurally invalid,
                exceeds capacity or breaks any time window.
        """
        if len(path) < 3:
            raise InfeasibleRouteError(
                f"route must contain start depot, at least one customer, end depot; got {path}"
            )
        if path[0] != instance.start_depot or path[-1] != instance.end_depot:
            raise InfeasibleRouteError(
                f"route must start at {instance.start_depot} and end at "
                f"{instance.end_depot}; got {path}"
            )
        interior = path[1:-1]
        if len(set(interior)) != len(interior):
            raise InfeasibleRouteError(f"route visits a customer twice: {path}")
        for city in interior:
            if city not in instance.customers:
                raise InfeasibleRouteError(f"vertex {city} is not a customer of this instance")

        cost = sum(float(instance.dist[a, b]) for a, b in zip(path, path[1:], strict=False))
        load = float(sum(instance.demand[c] for c in interior))
        if load > instance.capacity + _TOL:
            raise InfeasibleRouteError(
                f"route {path} load {load:g} exceeds capacity {instance.capacity:g}"
            )

        t = 0.0
        prev = path[0]
        for city in path[1:]:
            t += instance.travel_time(prev, city) + float(instance.service_time[prev])
            t = max(t, float(instance.ready_time[city]))
            if t > float(instance.due_time[city]) + 1e-9:
                raise InfeasibleRouteError(
                    f"route {path}: arrival {t:.3f} at vertex {city} exceeds due time "
                    f"{float(instance.due_time[city]):.3f}"
                )
            prev = city

        return cls(path=list(path), cost=cost, load=load, duration=t)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict."""
        return {"path": list(self.path), "cost": self.cost, "load": self.load,
                "duration": self.duration}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouteRecord:
        return cls(
            path=[int(v) for v in data["path"]],  # type: ignore[attr-defined]
            cost=float(data["cost"]),
            load=float(data["load"]),
            duration=float(data["duration"]),
        )

@dataclass(eq=True)
class Solution:
    """The outcome of one solver run over one instance.

    Attributes:
        status: Terminal status of the run.
        routes: Selected routes (empty unless a feasible solution exists).
        total_cost: Sum of the route costs.
        lower_bound: Best proven lower bound, when available.
        solve_time_seconds: Wall-clock time of the run.
        instance_name: Name of the solved instance, if known.
        meta: Free-form solver bookkeeping (iteration counts etc.).
    """

    status: SolutionStatus
    routes: list[RouteRecord] = field(default_factory=list)
    total_cost: float = 0.0
    lower_bound: float | None = None
    solve_time_seconds: float | None = None
    instance_name: str | None = None
    meta: dict[str, object] = field(default_factory=dict)

    def is_feasible(self, instance: VRPTWInstance) -> bool:
        """Check full feasibility against ``instance``.

        A solution is feasible when every interior customer appears exactly
        once across all routes and each route individually satisfies the
        capacity and time-window constraints.
        """
        served: list[int] = []
        for route in self.routes:
            served.extend(route.path[1:-1])
            try:
                recomputed = RouteRecord.from_path(instance, route.path)
            except InfeasibleRouteError:
                return False
            if (
                abs(recomputed.cost - route.cost) > _TOL
                or abs(recomputed.load - route.load) > _TOL
                or abs(recomputed.duration - route.duration) > _TOL
            ):
                return False
        return sorted(served) == list(instance.customers)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict."""
        return {
            "status": self.status.value,
            "routes": [r.to_dict() for r in self.routes],
            "total_cost": self.total_cost,
            "lower_bound": self.lower_bound,
            "solve_time_seconds": self.solve_time_seconds,
            "instance_name": self.instance_name,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Solution:
        return cls(
            status=SolutionStatus(str(data["status"])),
            routes=[
                RouteRecord.from_dict(r)  # type: ignore[arg-type]
                for r in data.get("routes", [])
            ],
            total_cost=float(data.get("total_cost", 0.0)),
            lower_bound=(
                None if data.get("lower_bound") is None
                else float(data["lower_bound"])
            ),
            solve_time_seconds=(
                None if data.get("solve_time_seconds") is None
                else float(data["solve_time_seconds"])
            ),
            instance_name=(
                None if data.get("instance_name") is None
                else str(data["instance_name"])
            ),
            meta=dict(data.get("meta", {})),  # type: ignore[arg-type]
        )


#: Friendlier public alias for :class:`RouteRecord`.
Route = RouteRecord
