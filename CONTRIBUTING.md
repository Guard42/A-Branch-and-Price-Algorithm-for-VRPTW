# Contributing to bpvrptw

Thanks for considering a contribution! This is an educational OR project,
so clarity and correctness matter more than cleverness.

## Development setup

```bash
git clone https://github.com/Guard42/A-Branch-and-Price-Algorithm-for-VRPTW
cd A-Branch-and-Price-Algorithm-for-VRPTW
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev,plot]"
```

Optional: `pip install -e ".[gurobi]"` adds the Gurobi backend (license
required). Everything else — including the full test suite — runs on the
license-free HiGHS backend.

## The referees

Every change must keep all of these green:

| Check | Command |
|---|---|
| Lint | `python -m ruff check .` |
| Types | `python -m mypy bpvrptw` |
| Tests | `python -m pytest -q` |
| README snippets | `python scripts/check_readme_snippets.py` |
| Docs links | `python scripts/check_docs_links.py` |

CI runs exactly these on Python 3.11 and 3.12, plus an end-to-end smoke
solve of `dataset/C101_25.txt`.

## Ground rules

1. **`legacy/` is frozen.** It is a teaching record of the original port
   with its defect catalogue (D1–D9). Never modify or delete it.
2. **Conventional commits**: `feat:`, `fix:`, `docs:`, `perf:`, `test:`,
   `chore:` … one logical change per commit.
3. **Determinism is a feature.** Solver behaviour must not depend on dict
   ordering, wall-clock jitter (beyond explicit budgets) or thread counts.
4. **Bounds must be sound.** Never report a lower bound derived from a
   partially converged relaxation; `SOLVED_OPTIMAL` requires a closed-gap
   certificate.
5. **No hardcoded paths**, no `print()` in library code (use
   `logging.getLogger("bpvrptw...")`), no new mandatory dependencies.
6. **Add tests** for behavioural changes. Correctness references live in
   `tests/exact.py` (brute-force optimum) and
   `tests/test_labeling.py` (brute-force route enumeration).

## Benchmark changes

If your change affects solver behaviour or performance, re-run the
benchmarks so the committed numbers stay truthful:

```bash
python -m bpvrptw bench dataset --time-limit 45 \
    --json results/bench_tier1.json --csv results/bench_tier1.csv
python scripts/bench_tier2.py          # optional deep tier
python scripts/merge_bench.py          # regenerates docs + README tables
python scripts/check_bench_report.py results/benchmarks.json
```

## Where to start

Look for the `legacy/README.md` defect catalogue — every fix there links
to the code that supersedes it. Good first contributions: extra parity
instances for `scripts/legacy_parity.py`, more brute-force cross-checks,
and documentation improvements.
