"""Tests for :mod:`bpvrptw.visualization`."""

from __future__ import annotations

from pathlib import Path

import pytest

from bpvrptw.instance import VRPTWInstance
from bpvrptw.solution import RouteRecord, Solution, SolutionStatus

pytest.importorskip("matplotlib")


def _solution(instance: VRPTWInstance) -> Solution:
    end = instance.end_depot
    routes = [
        RouteRecord.from_path(instance, [0, 1, 2, end]),
        RouteRecord.from_path(
            instance, [0, *[c for c in range(3, instance.n_customers + 1)], end]
        ),
    ]
    return Solution(
        status=SolutionStatus.SOLVED_OPTIMAL,
        routes=routes,
        total_cost=sum(r.cost for r in routes),
        solve_time_seconds=1.23,
        instance_name=instance.name,
    )


def test_plot_saves_png(tmp_path: Path, tiny_instance: VRPTWInstance) -> None:
    from bpvrptw.visualization import plot_solution

    out = tmp_path / "art" / "sol.png"
    fig = plot_solution(tiny_instance, _solution(tiny_instance), save_path=out)
    assert fig is not None
    assert out.exists() and out.stat().st_size > 1000


def test_plot_headless_does_not_open_window(
    tmp_path: Path, tiny_instance: VRPTWInstance,
) -> None:
    import matplotlib

    from bpvrptw.visualization import plot_solution

    plot_solution(tiny_instance, _solution(tiny_instance),
                  save_path=tmp_path / "x.png", show=False)
    assert matplotlib.get_backend().lower() == "agg"


def test_public_lazy_proxy(tmp_path: Path, tiny_instance: VRPTWInstance) -> None:
    import bpvrptw

    out = tmp_path / "p.png"
    bpvrptw.plot_solution(tiny_instance, _solution(tiny_instance), save_path=out)
    assert out.exists()


def test_schedule_saves_png(tmp_path: Path, tiny_instance: VRPTWInstance) -> None:
    from bpvrptw.schedule import plot_schedule

    out = tmp_path / "art" / "sched.png"
    fig = plot_schedule(
        tiny_instance, _solution(tiny_instance), save_path=out
    )
    assert fig is not None
    assert out.exists() and out.stat().st_size > 1000
