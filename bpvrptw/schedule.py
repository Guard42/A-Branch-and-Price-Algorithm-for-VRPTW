"""Schedule (Gantt) view: the time dimension of a solution.

Where :func:`plot_solution` shows the spatial routes, this function shows
*when* each vehicle serves its customers - including the waiting periods
that time windows force. Together they explain a VRPTW solution completely.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from matplotlib.figure import Figure

    from .instance import VRPTWInstance
    from .solution import Solution


def plot_schedule(
    instance: VRPTWInstance,
    solution: Solution,
    *,
    save_path: str | Path | None = None,
    show: bool = False,
    title: str | None = None,
) -> Figure:
    """Draw a Gantt-style schedule of the solution's routes.

    Each route is one lane; service intervals are solid blocks, waiting
    periods are hatched, and travel gaps appear as plain line segments.
    The depot time window bounds the chart.

    Args:
        instance: The solved instance.
        solution: A solution whose schedule will be drawn.
        save_path: Optional output file (parent dirs created).
        show: Open an interactive window; when False the Agg backend is
            forced before pyplot is imported (headless-safe).
        title: Plot title override.

    Returns:
        The matplotlib figure (closed unless ``show=True``).
    """
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    fig = plt.figure(figsize=(12, 1.2 + 0.8 * max(len(solution.routes), 1)))
    ax = fig.add_subplot(111)
    ax.set_title(
        title or f"Schedule for VRPTW on dataset {instance.name}", fontsize=14
    )

    cmap = plt.get_cmap("tab20")
    yticks: list[int] = []
    ylabels: list[str] = []

    for idx, route in enumerate(solution.routes):
        lane = idx
        color = cmap(idx % cmap.N)
        prev_city = route.path[0]
        departure = float(instance.ready_time[prev_city])
        for city in route.path[1:]:
            arrival = (
                departure
                + float(instance.dist[prev_city, city]) / instance.speed
                + float(instance.service_time[prev_city])
            )
            start_service = max(arrival, float(instance.ready_time[city]))
            wait = start_service - arrival
            service = float(instance.service_time[city])
            label = f"c{city}"
            if city == instance.end_depot:
                label = "end"
            if wait > 1e-9:
                ax.barh(
                    lane, wait, left=arrival, height=0.55,
                    color="none", edgecolor=color, hatch="///", linewidth=0.8,
                )
            ax.barh(
                lane, max(service, 0.4), left=start_service, height=0.55,
                color=color, edgecolor="black", linewidth=0.5,
            )
            ax.text(
                start_service + max(service, 0.4) / 2, lane, label,
                ha="center", va="center", fontsize=7,
                color="white" if service >= 2 else "black",
            )
            departure = start_service + service
            prev_city = city
        yticks.append(lane)
        ylabels.append(f"Route {idx + 1}")

    horizon_lo = float(instance.ready_time[instance.start_depot])
    horizon_hi = float(instance.due_time[instance.end_depot])
    ax.axvline(horizon_lo, color="black", linestyle="--", linewidth=1)
    ax.axvline(horizon_hi, color="black", linestyle="--", linewidth=1)
    ax.text(horizon_hi, len(solution.routes) - 0.3, "depot due",
            fontsize=8, ha="right")

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.invert_yaxis()
    ax.set_xlabel("Time", fontsize=12)
    ax.set_xlim(left=horizon_lo)
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)

    legend_items = [
        Patch(facecolor="gray", edgecolor="black", label="service"),
        Patch(facecolor="none", edgecolor="gray", hatch="///", label="waiting"),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=8)
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
