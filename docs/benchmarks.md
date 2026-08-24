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
| `C101_25.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.7 |
| `C102.txt` | **OPTIMAL** | 190.60 | 3 | 190.60 | 0.000 | 17.9 |
| `C103.txt` | time limit | 1132.40 | 25 | - | - | 300.1 |
| `C104.txt` | time limit | 1132.40 | 25 | - | - | 300.1 |
| `C105.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.6 |
| `C106.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 0.5 |
| `C107.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 1.0 |
| `C108.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 2.1 |
| `C109.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 0.000 | 8.6 |
| `C110_1.TXT` | time limit | 402788.00 | 1000 | - | - | 45.1 |
| `C201.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 1.6 |
| `C202.txt` | time limit | 1275.40 | 25 | - | - | 300.1 |
| `C203.txt` | time limit | 1275.40 | 25 | - | - | 45.0 |
| `C204.txt` | time limit | 1275.40 | 25 | - | - | 45.0 |
| `C205.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 5.8 |
| `C206.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 0.000 | 8.9 |
| `C207.txt` | time limit | 1275.40 | 25 | - | - | 45.0 |
| `C208.txt` | **OPTIMAL** | 215.40 | 2 | 215.40 | 0.000 | 89.7 |
| `R101.txt` | **OPTIMAL** | 618.10 | 8 | 618.10 | 0.000 | 0.0 |
| `R102.txt` | **OPTIMAL** | 547.90 | 7 | 547.90 | 0.000 | 82.5 |
| `R103.txt` | **OPTIMAL** | 455.60 | 5 | 455.60 | 0.000 | 2.3 |
| `R104.txt` | **OPTIMAL** | 418.00 | 4 | 418.00 | 0.000 | 14.2 |
| `R105.txt` | **OPTIMAL** | 531.30 | 6 | 531.30 | 0.000 | 0.1 |
| `R106.txt` | time limit | 1245.80 | 25 | 458.20 | 63.220 | 300.2 |
| `R107.txt` | **OPTIMAL** | 425.30 | 4 | 425.30 | 0.000 | 4.3 |
| `R108.txt` | time limit | 1245.80 | 25 | 397.79 | 68.069 | 45.1 |
| `R109.txt` | **OPTIMAL** | 442.70 | 5 | 442.70 | 0.000 | 0.4 |
| `R110.txt` | time limit | 1245.80 | 25 | 439.38 | 64.731 | 45.0 |
| `R111.txt` | time limit | 1245.80 | 25 | 428.26 | 65.624 | 45.0 |
| `R112.txt` | time limit | 1245.80 | 25 | 388.15 | 68.843 | 45.1 |
| `R201.txt` | time limit | 1245.80 | 25 | 461.30 | 62.972 | 300.1 |
| `R202.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R203.txt` | time limit | 1245.80 | 25 | - | - | 45.1 |
| `R204.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R205.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R206.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R207.txt` | time limit | 1245.80 | 25 | - | - | 300.1 |
| `R208.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R209.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R210.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `R211.txt` | time limit | 1245.80 | 25 | - | - | 45.0 |
| `RC101.txt` | time limit | 1887.00 | 25 | 409.38 | 78.306 | 45.0 |
| `RC102.txt` | **OPTIMAL** | 352.90 | 3 | 352.90 | 0.000 | 0.6 |
| `RC103.txt` | **OPTIMAL** | 334.20 | 3 | 334.20 | 0.000 | 3.3 |
| `RC104.txt` | **OPTIMAL** | 307.20 | 3 | 307.20 | 0.000 | 16.9 |
| `RC105.txt` | **OPTIMAL** | 412.40 | 4 | 412.40 | 0.000 | 0.5 |
| `RC106.txt` | **OPTIMAL** | 346.60 | 3 | 346.60 | 0.000 | 0.4 |
| `RC107.txt` | **OPTIMAL** | 299.10 | 3 | 299.10 | 0.000 | 2.2 |
| `RC108.txt` | **OPTIMAL** | 295.00 | 3 | 295.00 | 0.000 | 8.2 |
| `RC201.txt` | **OPTIMAL** | 361.40 | 3 | 361.40 | 0.000 | 2.3 |
| `RC202.txt` | time limit | 1887.00 | 25 | - | - | 300.0 |
| `RC203.txt` | time limit | 1887.00 | 25 | - | - | 45.0 |
| `RC204.txt` | time limit | 1887.00 | 25 | - | - | 45.0 |
| `RC205.txt` | **OPTIMAL** | 339.10 | 3 | 339.10 | 0.000 | 213.9 |
| `RC206.txt` | time limit | 1887.00 | 25 | - | - | 45.0 |
| `RC207.txt` | time limit | 1887.00 | 25 | - | - | 300.2 |
| `RC208.txt` | time limit | 1887.00 | 25 | - | - | 300.1 |
| `c101.txt` | time limit | 5770.80 | 100 | - | - | 45.0 |

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

- Legacy parity: `scripts/legacy_parity.py` re-runs the frozen legacy
  implementation and the new solver side by side. Verified identical optima
  on C101_25 (191.70), R101 (618.10), RC106 (346.60) and C201 (215.60),
  with the new implementation 5-33x faster (C201: 63.5s -> 1.9s).

*Generated 2026-08-24 by `scripts/merge_bench.py`.*
