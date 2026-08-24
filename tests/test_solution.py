"""Tests for :mod:`bpvrptw.solution` (RouteRecord / Solution)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import TINY_CUSTOMERS, TINY_DEPOT, make_instance_from_rows

from bpvrptw.instance import VRPTWInstance
from bpvrptw.solution import InfeasibleRouteError, RouteRecord, Solution, SolutionStatus


class TestRouteRecord:
    def test_valid_single_customer_route(self, tiny_instance: VRPTWInstance) -> None:
        route = RouteRecord.from_path(tiny_instance, [0, 1, 7])
        assert route.path == [0, 1, 7]
        expected_cost = float(
            tiny_instance.dist[0, 1] + tiny_instance.dist[1, 7]
        )
        assert route.cost == pytest.approx(expected_cost)
        assert route.load == pytest.approx(5.0)

    def test_duration_includes_wait_and_service(self, tiny_instance: VRPTWInstance) -> None:
        # Customer 3 has ready time 50 and service time 10; depot->3 travel
        # time is short, so waiting must push the clock to 50 before serving.
        route = RouteRecord.from_path(tiny_instance, [0, 3, 7])
        arrive3 = float(tiny_instance.dist[0, 3]) + float(tiny_instance.service_time[0])
        expected = max(arrive3, float(tiny_instance.ready_time[3]))
        expected += float(tiny_instance.service_time[3])
        expected += float(tiny_instance.dist[3, 7])
        assert route.duration == pytest.approx(expected)

    def test_capacity_violation_raises(self, tmp_path: Path) -> None:
        inst = make_instance_from_rows(tmp_path, "CAP", 4, 20.0, TINY_DEPOT, TINY_CUSTOMERS)
        # Customers 1+2+4 alone weigh 24 > 20 regardless of the tail.
        with pytest.raises(InfeasibleRouteError, match="capacity"):
            RouteRecord.from_path(inst, [0, 1, 2, 4, 7])

    def test_tw_violation_raises(self, tmp_path: Path) -> None:
        tight = [(1, 45.0, 68.0, 5.0, 0.0, 5.0, 0.0)]  # unreachable deadline
        inst = make_instance_from_rows(tmp_path, "TW", 2, 100.0, TINY_DEPOT, tight)
        with pytest.raises(InfeasibleRouteError, match="due time"):
            RouteRecord.from_path(inst, [0, 1, 2])

    def test_duplicate_customer_raises(self, tiny_instance: VRPTWInstance) -> None:
        with pytest.raises(InfeasibleRouteError, match="twice"):
            RouteRecord.from_path(tiny_instance, [0, 1, 1, 7])

    def test_missing_depot_endpoints_raise(self, tiny_instance: VRPTWInstance) -> None:
        with pytest.raises(InfeasibleRouteError):
            RouteRecord.from_path(tiny_instance, [1, 7])
        with pytest.raises(InfeasibleRouteError):
            RouteRecord.from_path(tiny_instance, [0, 1])

    def test_too_short_route_raises(self, tiny_instance: VRPTWInstance) -> None:
        with pytest.raises(InfeasibleRouteError):
            RouteRecord.from_path(tiny_instance, [0, 7])

    def test_non_customer_vertex_raises(self, tiny_instance: VRPTWInstance) -> None:
        with pytest.raises(InfeasibleRouteError, match="not a customer"):
            RouteRecord.from_path(tiny_instance, [0, 0, 7])

    def test_dict_round_trip(self, tiny_instance: VRPTWInstance) -> None:
        route = RouteRecord.from_path(tiny_instance, [0, 1, 2, 7])
        restored = RouteRecord.from_dict(route.to_dict())
        assert restored == route


class TestSolution:
    @staticmethod
    def _full_solution(tiny: VRPTWInstance) -> Solution:
        # One dedicated vehicle per customer; trivially feasible.
        routes = [RouteRecord.from_path(tiny, [0, k, 7]) for k in range(1, 7)]
        return Solution(
            status=SolutionStatus.SOLVED_OPTIMAL,
            routes=routes,
            total_cost=sum(r.cost for r in routes),
            instance_name=tiny.name,
        )

    def test_feasible_solution_passes(self, tiny_instance: VRPTWInstance) -> None:
        solution = self._full_solution(tiny_instance)
        assert solution.is_feasible(tiny_instance)
        assert solution.total_cost == pytest.approx(sum(r.cost for r in solution.routes))

    def test_missing_customer_detected(self, tiny_instance: VRPTWInstance) -> None:
        solution = self._full_solution(tiny_instance)
        solution.routes.pop()
        assert not solution.is_feasible(tiny_instance)

    def test_duplicated_customer_detected(self, tiny_instance: VRPTWInstance) -> None:
        solution = self._full_solution(tiny_instance)
        solution.routes.append(RouteRecord.from_path(tiny_instance, [0, 5, 7]))
        assert not solution.is_feasible(tiny_instance)

    def test_tampered_resources_detected(self, tiny_instance: VRPTWInstance) -> None:
        solution = self._full_solution(tiny_instance)
        broken = RouteRecord.from_path(tiny_instance, [0, 4, 7])
        broken.load += 1000.0
        solution.routes[3] = broken
        assert not solution.is_feasible(tiny_instance)

    def test_empty_solution_is_not_feasible(self, tiny_instance: VRPTWInstance) -> None:
        assert not Solution(status=SolutionStatus.INFEASIBLE).is_feasible(tiny_instance)

    def test_json_round_trip(self, tiny_instance: VRPTWInstance) -> None:
        solution = self._full_solution(tiny_instance)
        solution.lower_bound = solution.total_cost - 0.5
        solution.solve_time_seconds = 1.23
        solution.meta = {"bb_nodes": 7}
        restored = Solution.from_dict(solution.to_dict())
        assert restored.status is solution.status
        assert restored.routes == solution.routes
        assert restored.total_cost == pytest.approx(solution.total_cost)
        assert restored.lower_bound == pytest.approx(solution.lower_bound)
        assert restored.meta == solution.meta
