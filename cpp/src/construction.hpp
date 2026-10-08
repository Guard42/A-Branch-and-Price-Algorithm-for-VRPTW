// Deterministic greedy insertion heuristic (mirrors bpvrptw/construction.py).
//
// Seeds column generation with good initial routes and provides the
// branch-and-price tree with a strong initial upper bound.
#pragma once

#include <vector>

#include "instance.hpp"
#include "route.hpp"

namespace bpvrptw {

// Parallel cheapest-feasible-insertion: customers enter at their globally
// cheapest feasible position; when nothing fits, a new route opens for the
// lowest-index servable customer. Ties break on customer index, then route
// index, then insertion slot. arc_allowed (nullable) marks forbidden arcs.
std::vector<Route> greedy_insertion_routes(
    const Instance& inst, const std::vector<std::vector<char>>* arc_allowed = nullptr);

}  // namespace bpvrptw
