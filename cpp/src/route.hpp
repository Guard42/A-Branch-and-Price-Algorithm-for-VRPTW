// A validated vehicle route, mirroring bpvrptw/solution.py RouteRecord.
#pragma once

#include <vector>

#include "instance.hpp"

namespace bpvrptw {

struct Route {
    std::vector<int> path;  // [start_depot, customers..., end_depot]
    double cost = 0.0;
    double load = 0.0;
    double duration = 0.0;

    // Recomputes resources and validates capacity + time windows; returns
    // false (out untouched) on any violation.
    static bool try_from_path(const Instance& inst, const std::vector<int>& path, Route* out);
};

}  // namespace bpvrptw
