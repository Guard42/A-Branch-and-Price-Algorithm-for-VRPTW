"""Typed representation of a Solomon-format VRPTW instance.

The class in this module is the immutable-ish data backbone of the library:
vertices are indexed ``0 .. n-1`` where ``0`` is the start depot, ``n-1`` a
copy of the depot acting as route end, and ``1 .. n-2`` are the customers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ._util import get_logger

_logger = get_logger(__name__)
#: Distance values are rounded to one decimal, matching the Solomon benchmark
#: convention (and the legacy implementation this package replaces).
_DISTANCE_DECIMALS_SCALE = 10.0


class InstanceFormatError(ValueError):
    """Raised when a Solomon instance file cannot be parsed or validated."""


class VRPTWInstance:
    """A vehicle routing problem with time windows.

    Attributes:
        name: Instance name (first line of the Solomon file).
        vehicle_count: Size of the homogeneous vehicle fleet.
        capacity: Identical capacity of every vehicle.
        speed: Uniform travel speed; travel time equals distance / speed.
        coords: ``(n, 2)`` float array of vertex coordinates.
        demand: Length-``n`` float array of vertex demands (depots are 0).
        ready_time: Length-``n`` float array of time-window openings.
        due_time: Length-``n`` float array of time-window deadlines.
        service_time: Length-``n`` float array of service durations.
    """

    def __init__(
        self,
        *,
        name: str,
        vehicle_count: int,
        capacity: float,
        coords: np.ndarray,
        demand: np.ndarray,
        ready_time: np.ndarray,
        due_time: np.ndarray,
        service_time: np.ndarray,
        speed: float = 1.0,
    ) -> None:
        n = coords.shape[0]
        if coords.ndim != 2 or coords.shape[1] != 2:
            raise ValueError(f"coords must have shape (n, 2), got {coords.shape}")
        expected = (n,)
        for field_name, arr in (
            ("demand", demand),
            ("ready_time", ready_time),
            ("due_time", due_time),
            ("service_time", service_time),
        ):
            if arr.shape != expected:
                raise ValueError(f"{field_name} must have shape {expected}, got {arr.shape}")
        if n < 3:
            raise ValueError(f"an instance needs at least depot + 2 customers, got n={n}")
        if vehicle_count <= 0:
            raise InstanceFormatError(f"vehicle_count must be positive, got {vehicle_count}")
        if capacity <= 0:
            raise InstanceFormatError(f"capacity must be positive, got {capacity}")
        if speed <= 0:
            raise InstanceFormatError(f"speed must be positive, got {speed}")
        if np.any(demand < 0):
            raise InstanceFormatError("demands must be non-negative")
        if np.any(due_time < ready_time - 1e-9):
            bad = int(np.argmin(due_time - ready_time))
            raise InstanceFormatError(
                f"vertex {bad}: due_time {due_time[bad]} precedes ready_time {ready_time[bad]}"
            )
        self.name: str = name
        self.vehicle_count: int = int(vehicle_count)
        self.capacity: float = float(capacity)
        self.speed: float = float(speed)
        self.coords: np.ndarray = np.asarray(coords, dtype=np.float64)
        self.demand: np.ndarray = np.asarray(demand, dtype=np.float64)
        self.ready_time: np.ndarray = np.asarray(ready_time, dtype=np.float64)
        self.due_time: np.ndarray = np.asarray(due_time, dtype=np.float64)
        self.service_time: np.ndarray = np.asarray(service_time, dtype=np.float64)
        self._dist: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------
    @property
    def total_vertices(self) -> int:
        """Number of vertices including both depot copies."""
        return self.coords.shape[0]

    @property
    def n_customers(self) -> int:
        """Number of real customers (both depots excluded)."""
        return self.total_vertices - 2

    @property
    def start_depot(self) -> int:
        """Index of the start depot (always ``0``)."""
        return 0

    @property
    def end_depot(self) -> int:
        """Index of the end depot (always ``total_vertices - 1``)."""
        return self.total_vertices - 1

    @property
    def customers(self) -> range:
        """Indices of the customer vertices."""
        return range(1, self.total_vertices - 1)

    # ------------------------------------------------------------------
    # Matrices
    # ------------------------------------------------------------------
    @property
    def dist(self) -> np.ndarray:
        """Symmetric distance matrix rounded to one decimal (Solomon style)."""
        if self._dist is None:
            diff = self.coords[:, None, :] - self.coords[None, :, :]
            self._dist = (
                np.round(_DISTANCE_DECIMALS_SCALE * np.sqrt((diff**2).sum(-1)))
                / _DISTANCE_DECIMALS_SCALE
            )
            _logger.debug("computed %s distance matrix for %s", self._dist.shape, self.name)
        return self._dist

    def travel_time(self, i: int, j: int) -> float:
        """Travel time from vertex ``i`` to vertex ``j``."""
        return float(self.dist[i, j]) / self.speed

    # ------------------------------------------------------------------
    # Construction / misc
    # ------------------------------------------------------------------
    @classmethod
    def from_solomon(
        cls,
        path: str | Path,
        *,
        speed: float = 1.0,
        service_in_tw: bool = False,
    ) -> VRPTWInstance:
        """Parse a Solomon-format instance file.

        The parser accepts both common flavours of the format: files whose
        final data row duplicates the depot as an explicit end depot, and
        files that simply stop after the last customer. In either case the
        end depot of the constructed instance is built by copying the start
        depot row with zero demand and zero service time.

        Args:
            path: Path to the instance file.
            speed: Uniform travel speed (distance units per time unit).
            service_in_tw: If true, subtract each vertex's service time from
                its deadline, modelling "service must *start* within the
                time window" instead of "everything must be finished".

        Returns:
            The parsed instance.

        Raises:
            InstanceFormatError: On any structural or value violation.
        """
        path = Path(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise InstanceFormatError(f"cannot read {path}: {exc}") from exc
        if len(lines) < 10:
            raise InstanceFormatError(
                f"{path}: expected at least 10 lines (9 header + data), got {len(lines)}"
            )

        name = lines[0].strip()
        vehicle_line = lines[4].split()
        if len(vehicle_line) < 2:
            raise InstanceFormatError(
                f"{path}: line 5 must contain '<vehicles> <capacity>', got {lines[4]!r}"
            )
        try:
            vehicle_count = int(vehicle_line[0])
            capacity = float(vehicle_line[1])
        except ValueError as exc:
            raise InstanceFormatError(f"{path}: line 5 is not '<int> <number>': {exc}") from exc

        rows: list[tuple[int, float, float, float, float, float, float]] = []
        for lineno, raw in enumerate(lines[9:], start=10):
            stripped = raw.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) != 7:
                raise InstanceFormatError(
                    f"{path}: line {lineno}: expected 7 columns, got {len(parts)}: {stripped!r}"
                )
            try:
                row = (
                    int(parts[0]),
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                    float(parts[4]),
                    float(parts[5]),
                    float(parts[6]),
                )
            except ValueError as exc:
                raise InstanceFormatError(f"{path}: line {lineno}: {exc}") from exc
            rows.append(row)

        if not rows:
            raise InstanceFormatError(f"{path}: no customer data rows found")

        depot = rows[0]
        # Some Solomon files repeat the depot as an explicit end-depot row;
        # detect it by position/demand rather than trusting the layout.
        if len(rows) >= 2:
            last = rows[-1]
            if (
                abs(last[1] - depot[1]) < 1e-9
                and abs(last[2] - depot[2]) < 1e-9
                and last[3] == 0
            ):
                _logger.debug("%s: dropped explicit duplicated end-depot row", name)
                rows = rows[:-1]

        customer_rows = rows[1:]
        n = len(customer_rows) + 2
        coords = np.zeros((n, 2))
        demand = np.zeros(n)
        ready = np.zeros(n)
        due = np.zeros(n)
        service = np.zeros(n)

        coords[0] = (depot[1], depot[2])
        demand[0] = 0.0
        ready[0] = depot[4]
        due[0] = depot[5]
        service[0] = depot[6]

        for idx, row in enumerate(customer_rows, start=1):
            coords[idx] = (row[1], row[2])
            demand[idx] = row[3]
            ready[idx] = row[4]
            due[idx] = row[5]
            service[idx] = row[6]

        # End depot mirrors the start depot but cannot store anything and
        # takes no time to "serve".
        coords[n - 1] = coords[0]
        ready[n - 1] = ready[0]
        due[n - 1] = due[0]
        service[n - 1] = 0.0

        if service_in_tw:
            due -= service

        _logger.info(
            "loaded %s: %d customers, fleet=%d, capacity=%.0f",
            name,
            len(customer_rows),
            vehicle_count,
            capacity,
        )
        return cls(
            name=name,
            vehicle_count=vehicle_count,
            capacity=capacity,
            coords=coords,
            demand=demand,
            ready_time=ready,
            due_time=due,
            service_time=service,
            speed=speed,
        )

    def summary(self) -> str:
        """Return a one-line human-readable description."""
        horizon = float(np.max(self.due_time))
        return (
            f"VRPTWInstance({self.name!r}: {self.n_customers} customers, "
            f"fleet={self.vehicle_count}, capacity={self.capacity:g}, "
            f"horizon={horizon:g}, speed={self.speed:g})"
        )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return self.summary()
