# The Branch-and-Price Algorithm, End to End

This document walks through the exact algorithm implemented in `bpvrptw/`,
with the mathematics kept honest and every design choice tied back to the
defects of the legacy port (see [`legacy/README.md`](../legacy/README.md),
catalogue D1–D9).

## 1. Problem statement (VRPTW)

A homogeneous fleet of `K` vehicles, each with capacity `Q`, is based at a
depot. Customers `i = 1..n` have coordinates, demand `q_i`, a service
duration `s_i` and a time window `[a_i, b_i]`: arriving *before* `a_i`
forces waiting, arriving *after* `b_i` is forbidden. Travel between two
vertices costs the Euclidean distance rounded to one decimal — the Solomon
benchmark convention — and takes distance / speed time.

We solve the problem **exactly**: find the feasible solution of minimum
total travel cost. Vertices are indexed `0 .. n+1` in the literature; this
codebase uses a single array `0 .. n-1` where `0` is the start depot,
`n-1` an identical copy acting as route end, and `1 .. n-2` the customers.
(Off-by-one on that end-depot index is precisely legacy bug D3.)

## 2. Master problem: set partitioning

Let `P` be the (exponentially large) set of feasible routes `p`, with cost
`c_p` and incidence `a_{ip} ∈ {0,1}` (route `p` visits customer `i`).

```
min   Σ_p  c_p · y_p                       (MP)
s.t.  Σ_p  a_{ip} · y_p ≥ 1     i = 1..n   -- coverage
      y_p ∈ {0,1}
```

Using `≥ 1` instead of `= 1` keeps the LP polytope integral-friendly and
matches the upstream formulation. Column generation works on the LP
relaxation: start from a *restricted* master (RMP) holding only seed
columns (one single-customer route per customer), solve it, then ask a
pricing subproblem for new columns.

## 3. Duals and reduced costs

After solving the RMP, let `π_i ≥ 0` be the dual value of customer `i`'s
coverage row. The reduced cost of a route `p` is

```
rc(p) = c_p − Σ_{i ∈ p} π_i .
```

If some route has `rc(p) < 0`, adding it may improve the RMP; if none does,
the current RMP optimum solves the full LP relaxation and its objective is
a valid global lower bound. This certificate is what the tests assert.

> Implementation note (`bpvrptw/rmp.py`): both bundled backends normalize
> to exactly this convention (`rc = cost − Σ duals[covers] ≥ 0` at LP
> optimality). HiGHS returns nonnegative duals for `≥` rows in minimization;
> Gurobi's `Pi` matches after the same normalization.

The pricing subproblem therefore searches for routes minimizing

```
Σ_{arcs (i,j) ∈ p} ( d_{ij} − π_i )
```

over all *elementary* paths from the start depot to the end depot subject
to capacity and time windows — the **ESPPRC**.

## 4. Pricing: elementary shortest path with resource constraints

ESPPRC is NP-hard in general (elementarity is what makes it hard), but
label-setting with strong dominance handles tens of customers fine.

### Labels

A label at vertex `j` carries `(cost, time, load, S)`:

* `cost` — accumulated reduced cost along the path,
* `time` — earliest arrival at `j` including waiting and service
  (`t_j = max(t_prev + tt + s_prev, a_j)`),
* `load` — accumulated demand,
* `S ⊆ V` — the set of vertices visited so far (stored as a bitmask).

### Dominance

Label `L1` dominates `L2` (same vertex) iff

```
cost(L1) ≤ cost(L2),  time(L1) ≤ time(L2),  load(L1) ≤ load(L2),
S(L1) ⊆ S(L2)
```

with strictness somewhere. Any completion feasible for `L2` is feasible
for `L1` with no worse objective, so `L2` may be discarded. Two labels tie
on everything when their visit sets differ only by permutation order —
under symmetric distances these are indistinguishable; the first one wins
(deterministic insertion-order tie-break). Full-tie handling is also where
legacy bug D2 lived: the Python port's comparator referenced undefined
names and never ran because ordering ignored labels entirely (D1).

> **What dominance does NOT preserve:** enumeration completeness. A
> dominated partial path disappears together with *every* route it could
> have produced; those completions are covered by the dominating path's
> completions *only in objective*, not as identical column sets. That is
> fine for column generation (termination needs "no negative rc exists"),
> and it is why the test suite checks soundness plus the optimal minimum
> against brute force rather than set equality.

### Feillet pruning

When extending to vertex `j`, any unvisited customer `k` that becomes
provably unreachable — `arrival_j + d_{jk}/v + s_j > b_k` or
`load + q_k > Q` — is marked visited in the label's bitmask. Under the
triangle inequality (Euclidean distances satisfy it up to one-decimal
rounding) this never removes a feasible completion. **Caveat:** once
branch-and-price forbids arbitrary arcs the triangle argument breaks, so
pruning auto-disables whenever an `arc_allowed` restriction matrix is in
play. Forgetting that interplay caused a root-node explosion during
development — the profiler caught it, and the fix normalizes an all-True
matrix to "no restriction".

### Best-first ordering

Labels pop from a heap keyed `(cost, city, time, load, mask)`. Legacy D1
processed labels in *insertion order* and returned the *earliest-created*
negative routes (D9); best-first ordering means the budgeted search always
keeps the most negative columns, which is what CG convergence wants.

### Resource bounds (D8)

The search stops gracefully at `max_labels` or a wall-clock deadline,
returning whatever candidates were found with `exhausted=False`. A bounded
"cannot converge right now" replaces the legacy c104 hang.

## 5. Branch-and-bound over fractional edges

The tree owns itself (see the FAQ in the README for why we do not embed CG
in Gurobi/CPLEX callbacks). At each node:

1. Run CG to LP optimality → node bound.
2. Accumulate edge flows `x_ij = Σ y_p` over selected routes.
3. If every `x_ij` is (near-)integer → incumbent solution; update UB.
4. Else branch on an edge: `x_e = 0` vs `x_e = 1`.

Any integer flow value is legitimate (many routes share the return-to-
depot arc), so integrality means "within tolerance of *some* integer" —
the upstream window test only accepted values near 1 and would branch on
integral flows > 1.

### Which edge? (fixes D5)

Upstream scored candidate edges by `routes[i].get_cost()` — indexing a
route list by *vertex id*. We use a Ryan-Foster-style score:
maximize `min(x_e, ⌈x_e⌉ − x_e)` (closest to fractional), tie-broken by
larger true edge cost and then lexicographically.

### Encoding branching decisions

Forbidden arcs become infinite distances; imposed arcs wipe the tail row
(all departures except the imposed arc) and the head column (all arrivals
except the imposed arc). Two asymmetries matter and are unit-tested:

* many routes may leave the start depot — imposing out of vertex 0 wipes
  nothing;
* **many routes may return to the end depot** — imposing an arc into the
  depot must NOT wipe other arrivals there. Legacy D3 broke exactly this
  case (`branch_to != nbclients + 1` was always true under Python
  indexing).

Child 2 re-applies the whole ancestor chain onto a pristine copy of the
distance matrix, mirroring the legacy diving strategy.

## 6. Termination and certificates

* Global lower bound updates use the son0/toplevel bookkeeping inherited
  from the original implementation.
* Search ends when `(UB − LB)/UB < gap` (default `1e-6`) or the tree is
  exhausted; the incumbent plus the bound ship together in `Solution`.
* Wall-clock limits degrade to `TIME_LIMIT` with the best incumbent —
  never a hang.

## 7. Complexity remarks

Pure-Python labeling is deliberately readable over fast: expect seconds on
25-customer instances, minutes on friendly 100-customer ones, and resource
bounds elsewhere. Research-grade throughput needs C++/Rust pricing,
ng-route relaxation, dual stabilization and stronger branching — see
RouteOpt and the generic branch-cut-and-price literature for that journey.

## References

* Desaulniers, Desaulniers, Solomon (eds.), *Column Generation*, Springer 2005.
* Feillet, Dejax, Gendreau, Gueguen (2004) — ESPPRC with resource constraints.
* Desrochers, Lenstra, Savelsbergh (1990) — time window routing by column generation.
* Solomon (1987) — the benchmark instances shipped in `dataset/`.
