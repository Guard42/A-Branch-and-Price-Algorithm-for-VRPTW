"""Tests for :mod:`bpvrptw.instance` (Solomon parsing + matrices)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from conftest import TINY_CUSTOMERS, TINY_DEPOT, make_instance_from_rows, write_solomon

from bpvrptw.instance import InstanceFormatError, VRPTWInstance

DATASET_C101_25 = Path(__file__).resolve().parents[1] / "dataset" / "C101_25.txt"


@pytest.fixture()
def c101_25() -> VRPTWInstance:
    return VRPTWInstance.from_solomon(DATASET_C101_25)


class TestParseC10125:
    def test_header(self, c101_25: VRPTWInstance) -> None:
        assert c101_25.name == "C101"
        assert c101_25.n_customers == 25
        assert c101_25.vehicle_count == 10
        assert c101_25.capacity == 200.0
        assert c101_25.total_vertices == 27
        assert c101_25.start_depot == 0
        assert c101_25.end_depot == 26
        assert list(c101_25.customers) == list(range(1, 26))

    def test_customer_values(self, c101_25: VRPTWInstance) -> None:
        assert tuple(c101_25.coords[1]) == (45.0, 68.0)
        assert c101_25.demand[1] == 10.0
        assert c101_25.ready_time[1] == 912.0
        assert c101_25.due_time[1] == 967.0
        assert c101_25.service_time[1] == 90.0

    def test_depots(self, c101_25: VRPTWInstance) -> None:
        assert tuple(c101_25.coords[0]) == (40.0, 50.0)
        assert c101_25.demand[0] == 0.0
        assert c101_25.service_time[0] == 0.0
        assert c101_25.due_time[0] == 1236.0
        # End depot mirrors the start depot.
        assert np.allclose(c101_25.coords[-1], c101_25.coords[0])
        assert c101_25.demand[-1] == 0.0
        assert c101_25.service_time[-1] == 0.0
        assert c101_25.due_time[-1] == c101_25.due_time[0]

    def test_distance_convention(self, c101_25: VRPTWInstance) -> None:
        # sqrt((45-40)^2 + (68-50)^2) = sqrt(349) ~= 18.68 -> one decimal 18.7
        assert c101_25.dist[0, 1] == pytest.approx(18.7)
        assert np.allclose(c101_25.dist, c101_25.dist.T)
        assert c101_25.dist[5, 5] == pytest.approx(0.0)
        # Cached: second access returns the identical array object.
        assert c101_25.dist is c101_25.dist

    def test_travel_time_uses_speed(self, c101_25: VRPTWInstance) -> None:
        fast = VRPTWInstance.from_solomon(DATASET_C101_25, speed=2.0)
        assert fast.travel_time(0, 1) == pytest.approx(fast.dist[0, 1] / 2.0)

    def test_summary_mentions_name(self, c101_25: VRPTWInstance) -> None:
        assert "C101" in c101_25.summary()
        assert "25 customers" in c101_25.summary()


class TestParsingVariants:
    def test_explicit_trailing_end_depot_row_is_dropped(self, tmp_path: Path) -> None:
        plain = make_instance_from_rows(
            tmp_path, "PLAIN", 3, 100.0, TINY_DEPOT, TINY_CUSTOMERS
        )
        dup_path = write_solomon(
            tmp_path / "dup",
            "DUP",
            3,
            100.0,
            TINY_DEPOT,
            TINY_CUSTOMERS,
            trailing_end_depot=True,
        )
        duplicated = VRPTWInstance.from_solomon(dup_path)
        assert duplicated.total_vertices == plain.total_vertices
        assert np.allclose(duplicated.coords, plain.coords)

    def test_service_in_tw_shifts_due_dates(self, tmp_path: Path) -> None:
        inst = make_instance_from_rows(tmp_path, "S", 2, 50.0, TINY_DEPOT, TINY_CUSTOMERS[:2])
        shifted = VRPTWInstance.from_solomon(
            write_solomon(
                tmp_path / "s3", "S3", 2, 50.0, TINY_DEPOT, TINY_CUSTOMERS[:2]
            ),
            service_in_tw=True,
        )
        assert inst.due_time[1] == 1500.0  # default leaves the deadline alone
        assert shifted.due_time[1] == 1500.0 - 10.0

    def _mutated_copy(self, tmp_path: Path, name: str, lineno: int, replacement: str) -> Path:
        good = write_solomon(tmp_path, "SRC", 2, 10.0, TINY_DEPOT, TINY_CUSTOMERS[:2])
        lines = good.read_text().splitlines()
        lines[lineno] = replacement
        bad = tmp_path / name
        bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return bad

    def test_missing_capacity_column_raises(self, tmp_path: Path) -> None:
        bad = self._mutated_copy(tmp_path, "BAD.txt", 4, "  2")
        with pytest.raises(InstanceFormatError):
            VRPTWInstance.from_solomon(bad)

    def test_garbage_number_raises_with_line_info(self, tmp_path: Path) -> None:
        bad = self._mutated_copy(tmp_path, "G_BAD.txt", 10, "1  abc  68  5  0  1500  10")
        with pytest.raises(InstanceFormatError, match="line 11"):
            VRPTWInstance.from_solomon(bad)

    def test_wrong_column_count_raises(self, tmp_path: Path) -> None:
        bad = self._mutated_copy(tmp_path, "G_SHORT.txt", 10, "1  45  68  5  0  1500")
        with pytest.raises(InstanceFormatError, match="expected 7 columns, got 6"):
            VRPTWInstance.from_solomon(bad)

    def test_nonpositive_fleet_raises(self, tmp_path: Path) -> None:
        path = write_solomon(tmp_path, "Z", 0, 10.0, TINY_DEPOT, TINY_CUSTOMERS[:2])
        with pytest.raises(InstanceFormatError):
            VRPTWInstance.from_solomon(path)

    def test_due_before_ready_raises(self, tmp_path: Path) -> None:
        rows = [(1, 45.0, 68.0, 5.0, 900.0, 800.0, 0.0)]
        path = write_solomon(tmp_path, "TW", 2, 10.0, TINY_DEPOT, rows)
        with pytest.raises(InstanceFormatError, match="ready_time"):
            VRPTWInstance.from_solomon(path)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(InstanceFormatError):
            VRPTWInstance.from_solomon(tmp_path / "NOPE.txt")


class TestValidationDirect:
    def test_constructor_rejects_bad_shapes(self) -> None:
        coords = np.zeros((4, 2))
        with pytest.raises(ValueError, match="shape"):
            VRPTWInstance(
                name="X",
                vehicle_count=1,
                capacity=10.0,
                coords=coords,
                demand=np.zeros(5),
                ready_time=np.zeros(4),
                due_time=np.ones(4) * 10,
                service_time=np.zeros(4),
            )
