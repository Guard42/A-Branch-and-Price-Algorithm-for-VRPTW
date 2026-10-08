// Exact branch-and-price for VRPTW (C++ mirror of bpvrptw/branch_and_price.py).
//
// The class owns the search tree: each node runs column generation over a
// covering master problem, the tree branches on fractional arcs (child 1
// restricts the parent's matrix in place; child 2 rebuilds from the pristine
// matrix with all ancestor decisions), and parent routes warm start their
// children's RMPs.
#pragma once

#include <string>
#include <vector>

#include "column_generation.hpp"
#include "instance.hpp"
#include "route.hpp"

namespace bpvrptw {

struct BpResult {
    std::string status;  // SOLVED_OPTIMAL | SOLVED_FEASIBLE | TIME_LIMIT | INFEASIBLE
    std::vector<Route> routes;
    double total_cost = 0.0;
    bool has_lower_bound = false;
    double lower_bound = 0.0;
    double solve_time_seconds = 0.0;
    std::string instance_name;
    int bb_nodes = 0;
    bool gap_closed = false;
    double gap_pct = 0.0;
};

class BranchAndPrice {
public:
    // time_limit_seconds < 0 means unbounded.
    explicit BranchAndPrice(const Instance& inst, double gap = 1e-6,
                            double time_limit_seconds = -1.0, bool verbose = false);

    BpResult solve();

private:
    const Instance& inst_;
    double gap_;
    double time_limit_;
    bool verbose_;
};

}  // namespace bpvrptw
