"""Command-line interface: ``python -m bpvrptw solve|bench``."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from ._util import setup_logging
from .branch_and_price import BranchAndPrice
from .instance import InstanceFormatError, VRPTWInstance
from .solution import Solution, SolutionStatus


def _solve_one(
    instance_path: Path,
    *,
    lp_solver: str,
    time_limit: float | None,
    gap: float,
    quiet: bool,
) -> tuple[VRPTWInstance | None, Solution | None, int]:
    """Solve one instance; returns (instance, Solution, exit_code)."""
    try:
        instance = VRPTWInstance.from_solomon(instance_path)
    except InstanceFormatError as exc:
        if not quiet:
            print(f"[skip] {instance_path}: {exc}", file=sys.stderr)
        return None, None, 2
    try:
        instance = VRPTWInstance.from_solomon(instance_path)
    except InstanceFormatError as exc:
        if not quiet:
            print(f"[skip] {instance_path}: {exc}", file=sys.stderr)
        return None, None, 2  # type: ignore[return-value]
    solver = BranchAndPrice(
        instance, lp_solver=lp_solver, gap=gap, time_limit_seconds=time_limit
    )
    solution = solver.solve()
    ok = solution.status in {
        SolutionStatus.SOLVED_OPTIMAL,
        SolutionStatus.SOLVED_FEASIBLE,
        SolutionStatus.TIME_LIMIT,
    }
    if not quiet:
        lb = f"{solution.lower_bound:.4f} " if solution.lower_bound is not None else ""
        print(
            f"[done] {instance.name}: status={solution.status.value} "
            f"cost={solution.total_cost:.4f} {lb}routes={len(solution.routes)} "
            f"nodes={solution.meta.get('bb_nodes')}"
        )
    return instance, solution, 0 if ok else 2


def _cmd_solve(args: argparse.Namespace) -> int:
    setup_logging()
    path = Path(args.instance)
    instance, solution, code = _solve_one(
        path,
        lp_solver=args.lp_solver,
        time_limit=args.time_limit,
        gap=args.gap,
        quiet=False,
    )
    if solution is None:
        return 2

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = solution.to_dict()
        payload["version"] = __version__
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.save_fig:
        from .visualization import plot_solution  # lazy: optional extra

        assert instance is not None and solution is not None  # narrowed above
        plot_solution(instance, solution, save_path=args.save_fig, show=False)
        if not args.quiet:
            print(f"[fig] saved to {args.save_fig}")
    return code


def _iter_instance_files(directory: Path, pattern: str) -> list[Path]:
    files = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() == ".txt" and p.match(pattern)
    ]
    return sorted(files)


def _cmd_bench(args: argparse.Namespace) -> int:
    setup_logging()
    directory = Path(args.dataset_dir)
    files = _iter_instance_files(directory, args.pattern)
    if not files:
        print(f"no instance files matching {args.pattern!r} under {directory}", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    for path in files:
        started = time.perf_counter()
        instance, solution, _code = _solve_one(
            path,
            lp_solver=args.lp_solver,
            time_limit=args.time_limit,
            gap=1e-6,
            quiet=args.quiet,
        )
        elapsed = time.perf_counter() - started
        if solution is None:
            rows.append(
                {
                    "instance": path.name,
                    "status": "ERROR",
                    "total_cost": None,
                    "routes": None,
                    "lower_bound": None,
                    "solve_time_seconds": round(elapsed, 3),
                }
            )
            continue
        rows.append(
            {
                "instance": path.name,
                "status": solution.status.value,
                "total_cost": (
                    None if solution.total_cost is None else round(solution.total_cost, 6)
                ),
                "routes": len(solution.routes),
                "lower_bound": solution.lower_bound,
                "solve_time_seconds": round(elapsed, 3),
            }
        )

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "bpvrptw_version": __version__,
                "time_limit_s": args.time_limit,
                "lp_solver": args.lp_solver,
            },
            "rows": rows,
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.csv:
        out_csv = Path(args.csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "instance", "status", "total_cost", "routes", "lower_bound",
            "solve_time_seconds",
        ]
        with out_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    n_optimal = sum(1 for r in rows if r["status"] == "SOLVED_OPTIMAL")
    print(f"\nbench summary: {len(rows)} instances, {n_optimal} proven optimal")
    for row in rows:
        cost = row["total_cost"]
        print(f"  {row['instance']:<18} {row['status']:<16} "
              f"{cost if cost is not None else '-':>10}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bpvrptw",
        description="Branch-and-Price exact solver for VRPTW (educational).",
    )
    parser.add_argument("--version", action="version", version=f"bpvrptw {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    solve_p = subparsers.add_parser("solve", help="solve a single Solomon instance")
    solve_p.add_argument("instance", help="path to the instance file")
    solve_p.add_argument("--time-limit", type=float, default=None, help="seconds")
    solve_p.add_argument("--gap", type=float, default=1e-6)
    solve_p.add_argument("--lp-solver", choices=["auto", "highs", "gurobi"], default="auto")
    solve_p.add_argument("--output-json", default=None, help="write the Solution as JSON")
    solve_p.add_argument("--save-fig", default=None, help="save a route figure (needs [plot])")
    solve_p.add_argument("--quiet", action="store_true")
    solve_p.set_defaults(func=_cmd_solve)

    bench_p = subparsers.add_parser("bench", help="solve every instance in a directory")
    bench_p.add_argument("dataset_dir")
    bench_p.add_argument("--pattern", default="*.txt")
    bench_p.add_argument("--time-limit", type=float, default=60.0)
    bench_p.add_argument("--lp-solver", choices=["auto", "highs", "gurobi"], default="auto")
    bench_p.add_argument("--json", default=None)
    bench_p.add_argument("--csv", default=None)
    bench_p.add_argument("--quiet", action="store_true")
    bench_p.set_defaults(func=_cmd_bench)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
