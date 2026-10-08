// Bounded best-first ESPPRC labeling for the pricing subproblem.
//
// C++ mirror of bpvrptw/labeling.py: labels are processed best-first by
// reduced cost, dominance follows Feillet et al., and the search is bounded
// by a label cap and a wall-clock budget (graceful degradation instead of
// hanging). Supports forbidden arcs (branch-and-price constraints); with
// any forbidden arc present, Feillet-style unreachability pruning is
// disabled because the triangle-inequality argument no longer holds.
#pragma once

#include <cstdint>
#include <vector>

#include "instance.hpp"

namespace bpvrptw {

// Visited-vertex set over up to 126 customers (both depots included).
struct Mask {
    std::uint64_t lo = 0;
    std::uint64_t hi = 0;

    void set(int j) {
        if (j < 64) lo |= (1ULL << j);
        else hi |= (1ULL << (j - 64));
    }
    bool test(int j) const {
        return j < 64 ? ((lo >> j) & 1ULL) != 0 : ((hi >> (j - 64)) & 1ULL) != 0;
    }
    bool is_subset_of(const Mask& o) const {
        return (lo & ~o.lo) == 0 && (hi & ~o.hi) == 0;
    }
    bool operator==(const Mask& o) const { return lo == o.lo && hi == o.hi; }
    bool operator!=(const Mask& o) const { return !(*this == o); }
};

struct PricedRoute {
    std::vector<int> path;  // [0, customers..., n-1]
    double reduced_cost = 0.0;
    double true_cost = 0.0;
};

struct PricingResult {
    std::vector<PricedRoute> routes;  // most negative reduced cost first
    long long n_labels_explored = 0;
    bool exhausted = true;
    double elapsed_seconds = 0.0;
};

class EspprcSolver {
public:
    // reduced_costs: arc objective overriding inst.dist (CG passes
    // dist - pi); may be null to use plain distances. arc_allowed: n x n
    // admissibility matrix (branching); null means everything allowed.
    EspprcSolver(const Instance& inst, const std::vector<std::vector<double>>* reduced_costs,
                 const std::vector<std::vector<char>>* arc_allowed);

    PricingResult solve(int max_routes = 10, double threshold = -1e-6,
                        long long max_labels = 2'000'000, double time_limit_seconds = -1.0);

private:
    const Instance& inst_;
    const std::vector<std::vector<double>>* rc_;
    const std::vector<std::vector<char>>* allowed_;
};

}  // namespace bpvrptw
