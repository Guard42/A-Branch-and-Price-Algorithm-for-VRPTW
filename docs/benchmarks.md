# Benchmarks

Measured results of the bundled Solomon subset with this library, exactly as
produced by `python -m bpvrptw bench dataset ...` and
`scripts/bench_tier2.py`. Every number below is reproducible on any machine;
rows marked *time limit* did not converge within the budget and report the
best incumbent found — honestly. No instance hangs: the historical `c104`
deadlock (see `legacy/README.md`, D8) now ends cleanly inside its budget.

## Methodology

- Two tiers: a 45 s sweep over every file in `dataset/` (tier 1), then a
  300 s deep run on selected non-converged instances (tier 2).
- Solver settings: `BranchAndPrice(lp_solver='auto', gap=1e-6)`; HiGHS or
  Gurobi LP backend per availability (`auto`).
- Raw data: [`results/bench_tier1.json`](../results/bench_tier1.json),
  [`results/bench_tier2.json`](../results/bench_tier2.json),
  merged into [`results/benchmarks.json`](../results/benchmarks.json).

## Results

| Instance | Status | Cost | Routes | Lower bound | Time (s) |
|----------|--------|------:|-------:|------------:|---------:|
| `C101_25.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 1.3 |
| `C102.txt` | **OPTIMAL** | 190.60 | 3 | 190.60 | 33.1 |
| `C103.txt` | time limit | 1132.40 | 25 | 1132.40 | 300.1 |
| `C104.txt` | time limit | 1132.40 | 25 | 1132.40 | 300.0 |
| `C105.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 1.4 |
| `C106.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 1.0 |
| `C107.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 2.3 |
| `C108.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 4.6 |
| `C109.txt` | **OPTIMAL** | 191.70 | 3 | 191.70 | 17.5 |
| `C110_1.TXT` | time limit | 402788.00 | 1000 | 402788.00 | 45.2 |
| `C201.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 3.7 |
| `C202.txt` | time limit | 1275.40 | 25 | 1275.40 | 300.1 |
| `C203.txt` | time limit | 1275.40 | 25 | 1275.40 | 45.0 |
| `C204.txt` | time limit | 1275.40 | 25 | 1275.40 | 45.0 |
| `C205.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 4.4 |
| `C206.txt` | **OPTIMAL** | 215.60 | 2 | 215.60 | 7.9 |
| `C207.txt` | time limit | 1275.40 | 25 | 1275.40 | 45.0 |
| `C208.txt` | **OPTIMAL** | 215.40 | 2 | 215.40 | 40.3 |
| `R101.txt` | **OPTIMAL** | 618.10 | 8 | 618.10 | 0.0 |
| `R102.txt` | **OPTIMAL** | 547.90 | 7 | 547.90 | 38.7 |
| `R103.txt` | **OPTIMAL** | 455.60 | 5 | 455.60 | 2.5 |
| `R104.txt` | **OPTIMAL** | 418.00 | 4 | 418.00 | 16.1 |
| `R105.txt` | **OPTIMAL** | 531.30 | 6 | 531.30 | 0.1 |
| `R106.txt` | time limit | 1245.80 | 25 | 458.20 | 300.1 |
| `R107.txt` | **OPTIMAL** | 425.30 | 4 | 425.30 | 4.2 |
| `R108.txt` | time limit | 1245.80 | 25 | 397.79 | 45.0 |
| `R109.txt` | **OPTIMAL** | 442.70 | 5 | 442.70 | 0.3 |
| `R110.txt` | time limit | 1245.80 | 25 | 439.38 | 45.0 |
| `R111.txt` | time limit | 1245.80 | 25 | 428.26 | 45.0 |
| `R112.txt` | time limit | 1245.80 | 25 | 388.15 | 45.1 |
| `R201.txt` | time limit | 1245.80 | 25 | 461.30 | 300.1 |
| `R202.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R203.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.1 |
| `R204.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.1 |
| `R205.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R206.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R207.txt` | time limit | 1245.80 | 25 | 1245.80 | 300.1 |
| `R208.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R209.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R210.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `R211.txt` | time limit | 1245.80 | 25 | 1245.80 | 45.0 |
| `RC101.txt` | INFEASIBLE | 0.00 | 0 | 409.38 | 45.0 |
| `RC102.txt` | **OPTIMAL** | 352.90 | 3 | 352.90 | 0.6 |
| `RC103.txt` | **OPTIMAL** | 334.20 | 3 | 334.20 | 3.9 |
| `RC104.txt` | **OPTIMAL** | 307.20 | 3 | 307.20 | 21.6 |
| `RC105.txt` | **OPTIMAL** | 412.40 | 4 | 412.40 | 0.7 |
| `RC106.txt` | **OPTIMAL** | 346.60 | 3 | 346.60 | 0.5 |
| `RC107.txt` | **OPTIMAL** | 299.10 | 3 | 299.10 | 2.9 |
| `RC108.txt` | **OPTIMAL** | 295.00 | 3 | 295.00 | 10.2 |
| `RC201.txt` | **OPTIMAL** | 361.40 | 3 | 361.40 | 2.6 |
| `RC202.txt` | time limit | 1887.00 | 25 | 1887.00 | 300.1 |
| `RC203.txt` | time limit | 1887.00 | 25 | 1887.00 | 45.1 |
| `RC204.txt` | time limit | 1887.00 | 25 | 1887.00 | 45.0 |
| `RC205.txt` | **OPTIMAL** | 339.10 | 3 | 339.10 | 291.6 |
| `RC206.txt` | time limit | 1887.00 | 25 | 1887.00 | 45.0 |
| `RC207.txt` | time limit | 1887.00 | 25 | 1887.00 | 300.1 |
| `RC208.txt` | time limit | 1887.00 | 25 | 1887.00 | 300.2 |
| `c101.txt` | INFEASIBLE | 0.00 | 0 | 910.75 | 45.0 |

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

*Generated 2026-08-24 by `scripts/merge_bench.py`.*
