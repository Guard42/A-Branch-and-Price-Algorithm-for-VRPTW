"""Solution plotting with a headless-friendly API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from matplotlib.figure import Figure

    from .instance import VRPTWInstance
    from .solution import Solution


def plot_solution(
    instance: VRPTWInstance,
    solution: Solution,
    *,
    save_path: str | Path | None = None,
    show: bool = False,
    title: str | None = None,
) -> Figure:
    """Plot the routes of a solution over the instance geometry.

    Args:
        instance: The solved instance (coordinates are read from it).
        solution: A solution whose routes will be drawn.
        save_path: Optional file path; parent directories are created.
            PNG/SVG etc. follow the extension.
        show: Open an interactive window. When False, a non-interactive
            backend is forced *before* pyplot is imported, so this function
            is safe on headless machines and in CI.
        title: Plot title; defaults to ``B&P Solution for <name>``.

    Returns:
        The matplotlib figure (closed unless ``show=True``).
    """
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111)
    ax.set_title(title or f"B&P Solution for VRPTW on dataset {instance.name}", fontsize=16)

    depot_x, depot_y = float(instance.coords[0, 0]), float(instance.coords[0, 1])
    customers = list(instance.customers)
    ax.scatter([depot_x], [depot_y], color="black", s=100, label="Depot", zorder=5)
    ax.text(depot_x, depot_y, "Depot", fontsize=12, ha="right", va="bottom", color="black")

    xs = [float(instance.coords[c, 0]) for c in customers]
    ys = [float(instance.coords[c, 1]) for c in customers]
    ax.scatter(xs, ys, color="gray", s=50, label="Customers", zorder=5)
    for c in customers:
        ax.annotate(
            str(c),
            (float(instance.coords[c, 0]), float(instance.coords[c, 1])),
            fontsize=9,
            ha="right",
            va="bottom",
            color="dimgray",
        )

    cmap = plt.get_cmap("tab20")
    for idx, route in enumerate(solution.routes):
        path = route.path
        rx = [float(instance.coords[v, 0]) for v in path]
        ry = [float(instance.coords[v, 1]) for v in path]
        color = cmap(idx % cmap.N)
        ax.plot(rx, ry, color=color, linewidth=2, label=f"Route {idx + 1}", zorder=2)
        for k in range(len(path) - 1):
            ax.annotate(
                "",
                xy=((rx[k] + rx[k + 1]) / 2, (ry[k] + ry[k + 1]) / 2),
                xytext=(rx[k], ry[k]),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
            )

    info_text = f"Optimal Cost: {solution.total_cost:.2f}\nRoutes: {len(solution.routes)}"
    if solution.solve_time_seconds is not None:
        info_text += f"\nTotal Time: {solution.solve_time_seconds:.2f} seconds"
    ax.text(
        0.98,
        0.02,
        info_text,
        transform=ax.transAxes,
        fontsize=11,
        ha="right",
        va="bottom",
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.5"),
    )

    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.7)
    ax.set_xlabel("X Coordinate", fontsize=13)
    ax.set_ylabel("Y Coordinate", fontsize=13)
    fig.tight_layout()

    if save_path is not None:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out)
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig
