# bpvrptw-cpp — the C++17 twin implementation

A self-contained, dependency-free C++17 implementation of the same
branch-and-price algorithm as the Python package. Same algorithm family,
same instance format, verified against the same known optima — compiled,
with no external LP solver, no Python environment and no license
requirements.

## What is implemented

| Component | File | Python counterpart |
|-----------|------|--------------------|
| Solomon reader, 1-decimal distance rounding | `src/instance.{hpp,cpp}` | `bpvrptw/instance.py` |
| Route validation (capacity + time windows) | `src/route.{hpp,cpp}` | `bpvrptw/solution.py` |
| Bounded best-first ESPPRC labeling, Feillet pruning, forbidden-arc support | `src/pricing.{hpp,cpp}` | `bpvrptw/labeling.py` |
| Set-covering RMP solved by a built-in two-phase revised simplex | `src/simplex.{hpp,cpp}` | `bpvrptw/rmp.py` (HiGHS/Gurobi backends) |
| Column-generation loop with warm-started columns | `src/column_generation.{hpp,cpp}` | `bpvrptw/column_generation.py` |
| Greedy insertion construction heuristic | `src/construction.{hpp,cpp}` | `bpvrptw/construction.py` |
| Branch-and-bound tree with arc branching | `src/branch_and_price.{hpp,cpp}` | `bpvrptw/branch_and_price.py` |

Deliberate scope: this is the same *educational* algorithm as the Python
package (single-sided labeling, no ng-route relaxation, no dual
stabilization, no cuts). It is not a research-grade solver — it is the
same design, compiled.

## Build

Requires CMake ≥ 3.15 and a C++17 compiler.

```bash
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build --config Release
```

MSVC one-liner without CMake (from a Visual Studio developer prompt):

```bat
cl /nologo /EHsc /O2 /std:c++17 /Icpp\src cpp\src\*.cpp /Fe:bpvrptw_cpp.exe
```

## Run

```bash
# Solve one instance (status, cost, routes, B&B nodes, timing)
cpp/build/bpvrptw_cpp dataset/C101_25.txt --time-limit 300

# Reproduce the known optima of seven bundled instances (~4 s total)
cpp/build/bpvrptw_cpp_test dataset        # or: ctest --test-dir cpp/build
```

## Correctness

`bpvrptw_cpp_test` solves seven bundled Solomon instances whose optima are
cross-validated in the Python README benchmark tables by *both* the Python
branch-and-price solver and a direct Gurobi MIP, asserts the exact costs,
and additionally re-validates full feasibility (every customer served
exactly once; capacity and time windows respected):

```
PASS C101_25.txt  cost=191.70 routes=3 nodes=1
PASS C105.txt     cost=191.70 routes=3 nodes=1
PASS C201.txt     cost=215.60 routes=2 nodes=1
PASS R101.txt     cost=618.10 routes=8 nodes=1
PASS R102.txt     cost=547.90 routes=7 nodes=3   <- exercises branching
PASS R103.txt     cost=455.60 routes=5 nodes=1
PASS R105.txt     cost=531.30 routes=6 nodes=1
PASS RC102.txt    cost=352.90 routes=3 nodes=1
```

Instances that require branching are covered too (R102 closes at 547.90
after 3 B&B nodes). The LP solver is a hand-written dense revised
simplex (two-phase, Bland fallback for degeneracy, periodic re-inversion);
its converged bounds match the HiGHS-backed Python pipeline on every
instance tested.

## Performance snapshot

Measured on the bundled dataset (same machine for both implementations):

- Every 25-customer instance tested solves in **well under a second**
  (C101_25 0.06 s, R101 instant, C105 0.09 s, RC102 0.06 s, C201 3.6 s);
  the Python package needs roughly the same order of magnitude there.
- The full 100-customer `c101.txt` is proven optimal (**828.70, 10
  routes**, closed gap) in about **five minutes**; the Python
  implementation reports 37.8 s for the same optimum. The two ports
  explore labels in different internal orders, so per-instance times
  differ in both directions — correctness and bound soundness are the
  gate here, not raw speed.
- Wide-time-window R2-type instances remain the hard ones, exactly as in
  the Python benchmark tables.

## Notes and limits

- Up to 124 customers (the visited-set bitmask is 128 bits wide).
- Same honest limits as the Python implementation: wide-time-window R2-type
  instances are the hard ones; expect `TIME_LIMIT` there.
- Vehicle counts are accepted by the reader but not constrained, exactly
  like the Python solver.