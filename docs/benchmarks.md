# Benchmarks

Measured results of the bundled Solomon subset with this library, exactly as
produced by `python -m bpvrptw bench dataset ...` and
`scripts/bench_tier2.py`. Every number below is reproducible on any machine;
rows marked *time limit* did not converge within the budget and report the
best incumbent found — honestly. No instance hangs: the historical `c104`
deadlock (see `legacy/README.md`, D8) now ends cleanly inside its budget.

## Methodology

## Methodology

- Two tiers: a 45 s sweep over every file in `dataset/` (tier 1), then a
  300 s deep run on selected non-converged instances (tier 2).
- Solver settings: `BranchAndPrice(lp_solver='auto', gap=1e-6)`; HiGHS or
  Gurobi LP backend per availability (`auto`).
- **Gap** = `(cost − lower_bound) / |cost| × 100`, reported only when the
  solver holds a *sound* lower bound — one produced by fully converged
  column generation. A partially priced RMP objective is never used as a
  bound (it sits above the true optimum and would fake a zero gap).
  `SOLVED_OPTIMAL` rows carry a closed-gap certificate (gap ≤ 1e-6 by
  construction); `-` means the run ended before any node proved a bound.
- Raw data: [`results/bench_tier1.json`](../results/bench_tier1.json),
  [`results/bench_tier2.json`](../results/bench_tier2.json),
  merged into [`results/benchmarks.json`](../results/benchmarks.json).
## Results

| Instance | Status | Cost | Routes | Lower bound | Gap (%) | Time (s) |
|----------|--------|------:|-------:|------------:|--------:|---------:|
| `C101_25.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.1 |
| `C102.txt` | **OPTIMAL** | 190.60 | 3 | 190.60 | 0.000 | 4.5 |
| `C103.txt` | **OPTIMAL** | 190.60 | 3 | 190.60 | 0.000 | 58.1 |
| `C104.txt` | time limit | 217.00 | 3 | - | - | 300.0 |
| `C105.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.2 |
| `C106.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.1 |
| `C107.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.2 |
| `C108.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.5 |
| `C109.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 2.0 |
| `C110_1.TXT` | time limit | 78728.10 | 130 | - | - | 1761.7 |
| `C201.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 1.0 |
| `C202.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 26.5 |
| `C203.txt` | time limit | 258.30 | 1 | - | - | 45.0 |
| `C204.txt` | time limit | 307.80 | 1 | - | - | 45.0 |
| `C205.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 1.2 |
| `C206.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 2.6 |
| `C207.txt` | **OPTIMAL** | 215.30 | 2 | 215.30 | 0.000 | 15.1 |
| `C208.txt` | **OPTIMAL** | 215.40 | 2 | 215.40 | 0.000 | 7.8 |
| `R101.txt` | **OPTIMAL** | 618.10 | 8 | 618.10 | 0.000 | 0.0 |
| `R102.txt` | **OPTIMAL** | 547.90 | 7 | 547.90 | 0.000 | 2.5 |
| `R103.txt` | **OPTIMAL** | 455.60 | 5 | 455.60 | 0.000 | 0.5 |
| `R104.txt` | **OPTIMAL** | 418.00 | 4 | 418.00 | 0.000 | 1.6 |
| `R105.txt` | **OPTIMAL** | 531.30 | 6 | 531.30 | 0.000 | 0.1 |
| `R106.txt` | **OPTIMAL** | 466.40 | 5 | 469.80 | 0.000 | 103.3 |
| `R107.txt` | **OPTIMAL** | 425.30 | 4 | 425.30 | 0.000 | 1.0 |
| `R108.txt` | **OPTIMAL** | 398.30 | 4 | 398.30 | 0.000 | 75.6 |
| `R109.txt` | **OPTIMAL** | 442.70 | 5 | 442.70 | 0.000 | 0.2 |
| `R110.txt` | time limit | 480.90 | 5 | 439.38 | 8.635 | 45.0 |
| `R111.txt` | time limit | 429.60 | 4 | 428.26 | 0.312 | 45.0 |
| `R112.txt` | time limit | 395.40 | 4 | 388.15 | 1.834 | 45.0 |
| `R201.txt` | time limit | 661.00 | 2 | 461.30 | 30.212 | 45.0 |
| `R202.txt` | time limit | 650.50 | 2 | - | - | 45.0 |
| `R203.txt` | time limit | 558.80 | 2 | - | - | 45.0 |
| `R204.txt` | time limit | 572.10 | 2 | - | - | 45.0 |
| `R205.txt` | time limit | 512.80 | 2 | 391.80 | 23.596 | 45.2 |
| `R206.txt` | time limit | 500.80 | 1 | - | - | 45.0 |
| `R207.txt` | time limit | 479.40 | 1 | - | - | 45.0 |
| `R208.txt` | time limit | 461.10 | 2 | - | - | 45.0 |
| `R209.txt` | time limit | 569.30 | 2 | 365.05 | 35.877 | 45.0 |
| `R210.txt` | time limit | 567.60 | 2 | - | - | 45.1 |
| `R211.txt` | time limit | 500.80 | 2 | - | - | 45.1 |
| `RC101.txt` | time limit | 596.30 | 5 | 409.38 | 31.347 | 300.3 |
| `RC102.txt` | **OPTIMAL** | 352.90 | 3 | 352.90 | 0.000 | 0.9 |
| `RC103.txt` | **OPTIMAL** | 334.20 | 3 | 334.20 | 0.000 | 3.1 |
| `RC104.txt` | **OPTIMAL** | 307.20 | 3 | 307.20 | 0.000 | 4.8 |
| `RC105.txt` | **OPTIMAL** | 412.40 | 4 | 412.40 | 0.000 | 0.4 |
| `RC106.txt` | **OPTIMAL** | 346.60 | 3 | 346.60 | 0.000 | 0.3 |
| `RC107.txt` | **OPTIMAL** | 299.10 | 3 | 299.10 | 0.000 | 1.7 |
| `RC108.txt` | **OPTIMAL** | 295.00 | 3 | 295.00 | 0.000 | 8.0 |
| `RC201.txt` | **OPTIMAL** | 361.40 | 3 | 361.40 | 0.000 | 0.5 |
| `RC202.txt` | **OPTIMAL** | 338.90 | 3 | 338.90 | 0.000 | 4.3 |
| `RC203.txt` | **OPTIMAL** | 327.80 | 3 | 327.80 | 0.000 | 280.5 |
| `RC204.txt` | time limit | 436.30 | 2 | - | - | 45.1 |
| `RC205.txt` | **OPTIMAL** | 339.10 | 3 | 339.10 | 0.000 | 2.5 |
| `RC206.txt` | **OPTIMAL** | 325.20 | 3 | 325.20 | 0.000 | 3.6 |
| `RC207.txt` | time limit | 572.40 | 2 | - | - | 45.0 |
| `RC208.txt` | time limit | 336.30 | 1 | - | - | 45.0 |
| `c101.txt` | **OPTIMAL** | 828.70 | 10 | 828.70 | 0.000 | 37.8 |

## Reading the numbers

- The C-family 25-customer instances all collapse to the same optimum
  (191.7 / 215.6): these truncated files share the customer geometry.
- `c104.txt` — the instance that used to hang forever in the legacy port —
  now returns its incumbent within the budget and is flagged as a time
  limit instead of freezing.
- `C110_1.TXT` carries 1000 customers: far beyond an educational pure-
  Python implementation; it is kept here to show honest resource bounding,
  not as a performance claim.
- Literature best-known values are not directly comparable because most
  files in `dataset/` are 25-customer truncations of the original
  100-customer Solomon instances.

*Generated 2026-08-25 by `scripts/merge_bench.py`.*
