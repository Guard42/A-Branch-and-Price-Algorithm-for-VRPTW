"""bpvrptw: Branch-and-Price exact solver for the Vehicle Routing Problem
with Time Windows.

Educational, library-grade reimplementation; the original flat scripts are
preserved unmodified under ``legacy/``.

Public API::

    import bpvrptw

    instance = bpvrptw.VRPTWInstance.from_solomon("dataset/C101_25.txt")
    solution = bpvrptw.solve(instance, time_limit_seconds=300)
    print(solution.status, solution.total_cost)
"""

from .branch_and_price import BranchAndPrice, apply_branching
from .column_generation import CGResult, ColumnGeneration
from .instance import InstanceFormatError, VRPTWInstance
from .labeling import ESPPRCSolver, PricedRoute, PricingResult
from .solution import (
    InfeasibleRouteError,
    Route,
    RouteRecord,
    Solution,
    SolutionStatus,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BranchAndPrice",
    "CGResult",
    "ColumnGeneration",
    "ESPPRCSolver",
    "InfeasibleRouteError",
    "InstanceFormatError",
    "PricedRoute",
    "PricingResult",
    "Route",
    "RouteRecord",
    "Solution",
    "SolutionStatus",
    "VRPTWInstance",
    "apply_branching",
    "plot_solution",
    "solve",
]


def solve(
    source: str | VRPTWInstance,
    *,
    lp_solver: str = "auto",
    gap: float = 1e-6,
    time_limit_seconds: float | None = None,
    verbose: bool = False,
) -> Solution:
    """Convenience one-shot solver.

    Args:
        source: A path to a Solomon file or a :class:`VRPTWInstance`.
        lp_solver: ``"auto" | "highs" | "gurobi"``.
        gap: Relative optimality gap.
        time_limit_seconds: Optional wall-clock budget.
        verbose: Emit INFO logs about the search progress.

    Returns:
        The resulting :class:`Solution`.
    """
    instance = source if isinstance(source, VRPTWInstance) else VRPTWInstance.from_solomon(source)
    return BranchAndPrice(
        instance,
        lp_solver=lp_solver,
        gap=gap,
        time_limit_seconds=time_limit_seconds,
        verbose=verbose,
    ).solve()


class SolveError(RuntimeError):
    """Placeholder alias kept so CLI errors can be distinguished later."""


def plot_solution(*args: object, **kwargs: object) -> object:
    """Lazy proxy for :func:`bpvrptw.visualization.plot_solution`.

    Keeps ``import bpvrptw`` free of any matplotlib requirement; the real
    function is imported on first call and raises a helpful error when the
    ``plot`` extra is missing.
    """
    try:
        from .visualization import plot_solution as _impl
    except ImportError as exc:  # pragma: no cover - environment specific
        raise ImportError(
            "plotting requires matplotlib; install with: pip install bpvrptw[plot]"
        ) from exc
    return _impl(*args, **kwargs)  # type: ignore[arg-type]
