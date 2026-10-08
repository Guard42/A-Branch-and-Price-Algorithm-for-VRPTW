// Column generation over the covering master problem (C++ mirror of
// bpvrptw/column_generation.py).
#pragma once

#include <memory>
#include <string>
#include <vector>

#include "instance.hpp"
#include "route.hpp"
#include "simplex.hpp"

namespace bpvrptw {

inline constexpr double kPricingThreshold = -1e-4;

struct ColumnValuePair {
    Route route;
    double value = 0.0;
};

struct CgResult {
    double objective = 0.0;
    int iterations = 0;
    int n_columns = 0;
    std::string status;  // "optimal" | "iteration_limit" | "time_limit"
    std::vector<ColumnValuePair> column_values;
    double lower_bound = 0.0;
};

class ColumnGeneration {
public:
    explicit ColumnGeneration(const Instance& inst) : inst_(inst) {}

    // seed_columns may be null (defaults to single-customer routes plus the
    // greedy construction). time_limit_seconds < 0 means unbounded.
    CgResult solve(const std::vector<Route>* seed_columns = nullptr,
                   const std::vector<std::vector<char>>* arc_allowed = nullptr,
                   int max_iterations = 500, double time_limit_seconds = -1.0);

private:
    const Instance& inst_;
};

// Default seed pool: every feasible single-customer route (skipping those
// that use a forbidden arc) followed by the greedy construction routes.
std::vector<Route> default_seed_columns(const Instance& inst,
                                        const std::vector<std::vector<char>>* arc_allowed);

}  // namespace bpvrptw
