"""Shared fixtures and Solomon-format helpers for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from bpvrptw.instance import VRPTWInstance

Row = tuple[int, float, float, float, float, float, float]

#: Depot row used by the synthetic tiny instance: (cust_no, x, y, demand,
#: ready, due, service).
TINY_DEPOT: Row = (0, 40.0, 50.0, 0.0, 0.0, 2000.0, 0.0)

#: Six well-spread customers with wide time windows so that every
#: single-customer route is feasible on its own.
TINY_CUSTOMERS: list[Row] = [
    (1, 45.0, 68.0, 5.0, 0.0, 1500.0, 10.0),
    (2, 52.0, 64.0, 7.0, 0.0, 1600.0, 10.0),
    (3, 55.0, 40.0, 6.0, 50.0, 1550.0, 10.0),
    (4, 40.0, 60.0, 12.0, 0.0, 1450.0, 10.0),
    (5, 35.0, 45.0, 8.0, 30.0, 1500.0, 10.0),
    (6, 50.0, 30.0, 11.0, 0.0, 1400.0, 10.0),
]


def write_solomon(
    directory: Path,
    name: str,
    vehicle_count: int,
    capacity: float,
    depot_row: Row,
    customers_rows: list[Row],
    *,
    trailing_end_depot: bool = False,
) -> Path:
    """Write a Solomon-format instance file and return its path.

    Args:
        directory: Target directory (created if missing).
        name: Instance/file base name.
        vehicle_count: Fleet size for the header.
        capacity: Vehicle capacity for the header.
        depot_row: The start-depot data row (customer number 0).
        customers_rows: The customer data rows.
        trailing_end_depot: If true, append an explicit duplicated end-depot
            row (some full-size Solomon files do this).

    Returns:
        Path of the written file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = [
        name,
        "",
        "VEHICLE",
        "NUMBER     CAPACITY",
        f"  {vehicle_count}         {capacity:g}",
        "",
        "CUSTOMER",
        "CUST NO.  XCOORD.   YCOORD.    DEMAND   READY TIME  DUE DATE   SERVICE TIME",
        " ",
    ]
    rows = [depot_row, *customers_rows]
    if trailing_end_depot:
        rows.append(
            (
                customers_rows[-1][0] + 1,
                depot_row[1],
                depot_row[2],
                0.0,
                depot_row[4],
                depot_row[5],
                0.0,
            )
        )
    for row in rows:
        lines.append(
            f"{row[0]:>4}  {row[1]:7.1f}  {row[2]:7.1f}  {row[3]:5.1f}"
            f"  {row[4]:8.1f}  {row[5]:8.1f}  {row[6]:6.1f}"
        )
    path = directory / f"{name}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_instance_from_rows(
    directory: Path,
    name: str,
    vehicle_count: int,
    capacity: float,
    depot_row: Row,
    customers_rows: list[Row],
) -> VRPTWInstance:
    """Convenience: write a synthetic file then parse it back."""
    path = write_solomon(directory, name, vehicle_count, capacity, depot_row, customers_rows)
    return VRPTWInstance.from_solomon(path)


@pytest.fixture()
def tiny_instance(tmp_path: Path) -> VRPTWInstance:
    """A six-customer instance with wide time windows."""
    return make_instance_from_rows(
        tmp_path, "TINY", vehicle_count=6, capacity=100.0,
        depot_row=TINY_DEPOT, customers_rows=TINY_CUSTOMERS,
    )
