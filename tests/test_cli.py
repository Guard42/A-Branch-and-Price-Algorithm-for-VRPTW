"""Tests for the CLI (solve/bench) and visualization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import TINY_CUSTOMERS, TINY_DEPOT, write_solomon

from bpvrptw.cli import main as cli_main


@pytest.fixture()
def tiny_file(tmp_path: Path) -> Path:
    return write_solomon(
        tmp_path, "CLI_TINY", 6, 100.0, TINY_DEPOT, TINY_CUSTOMERS,
    )


class TestSolveCommand:
    def test_solve_writes_json(self, tiny_file: Path, tmp_path: Path) -> None:
        out = tmp_path / "out" / "result.json"
        code = cli_main(
            ["solve", str(tiny_file), "--lp-solver", "highs",
             "--time-limit", "60", "--output-json", str(out)]
        )
        assert code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["status"] == "SOLVED_OPTIMAL"
        assert data["total_cost"] > 0
        assert len(data["routes"]) >= 1

    def test_solve_missing_instance_returns_error(self, tmp_path: Path) -> None:
        code = cli_main(["solve", str(tmp_path / "NOPE.txt"), "--quiet"])
        assert code != 0

    def test_save_fig_creates_png(self, tiny_file: Path, tmp_path: Path) -> None:
        pytest.importorskip("matplotlib")
        fig_path = tmp_path / "figs" / "sol.png"
        code = cli_main(
            ["solve", str(tiny_file), "--lp-solver", "highs",
             "--save-fig", str(fig_path), "--quiet"]
        )
        assert code == 0
        assert fig_path.exists() and fig_path.stat().st_size > 1000


class TestBenchCommand:
    def test_bench_two_instances(self, tmp_path: Path) -> None:
        d = tmp_path / "ds"
        write_solomon(d, "A01", 4, 100.0, TINY_DEPOT, TINY_CUSTOMERS)
        # Uppercase extension variant must also be picked up.
        p2 = write_solomon(d / "up", "B02", 4, 100.0, TINY_DEPOT, TINY_CUSTOMERS[:3])
        p2_up = d / "B02.TXT"
        p2_up.write_text(p2.read_text(encoding="utf-8"), encoding="utf-8")
        json_out = tmp_path / "res" / "bench.json"
        csv_out = tmp_path / "res" / "bench.csv"
        code = cli_main(
            ["bench", str(d), "--lp-solver", "highs", "--time-limit", "30",
             "--json", str(json_out), "--csv", str(csv_out), "--quiet"]
        )
        assert code == 0
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert len(data["rows"]) == 2
        assert data["meta"]["bpvrptw_version"]
        rows = {r["instance"] for r in data["rows"]}
        assert rows == {"A01.txt", "B02.TXT"}
        csv_text = csv_out.read_text(encoding="utf-8")
        assert "instance" in csv_text and "A01" in csv_text

    def test_bench_empty_dir_errors(self, tmp_path: Path) -> None:
        code = cli_main(["bench", str(tmp_path), "--quiet"])
        assert code == 2


class TestParser:
    def test_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            cli_main(["--help"])
        assert exc.value.code == 0
        assert "solve" in capsys.readouterr().out

    def test_version(self) -> None:
        with pytest.raises(SystemExit) as exc:
            cli_main(["--version"])
        assert exc.value.code == 0
