#include "construction.hpp"

#include <tuple>

namespace bpvrptw {
namespace {

bool ok(const std::vector<std::vector<char>>* allowed, int a, int b) {
    return allowed == nullptr || (*allowed)[a][b] != 0;
}

}  // namespace

std::vector<Route> greedy_insertion_routes(const Instance& inst,
                                           const std::vector<std::vector<char>>* arc_allowed) {
    const int end = inst.end_depot();
    std::vector<std::vector<int>> routes;
    std::vector<int> unvisited;
    for (int c = 1; c <= inst.n_customers(); ++c) unvisited.push_back(c);

    // Open a solo route for the lowest-index servable customer.
    const auto open_route = [&]() -> bool {
        for (std::size_t idx = 0; idx < unvisited.size(); ++idx) {
            const int c = unvisited[idx];
            if (!ok(arc_allowed, 0, c) || !ok(arc_allowed, c, end)) continue;
            Route rec;
            if (Route::try_from_path(inst, {0, c, end}, &rec)) {
                routes.push_back({0, c, end});
                unvisited.erase(unvisited.begin() + static_cast<long>(idx));
                return true;
            }
        }
        return false;
    };

    if (!unvisited.empty()) open_route();

    while (!unvisited.empty()) {
        // (delta_cost, customer, route_index, insertion_slot)
        std::tuple<double, int, int, int> best;
        bool found = false;
        for (std::size_t ri = 0; ri < routes.size(); ++ri) {
            const std::vector<int>& path = routes[ri];
            double base = 0.0;
            for (std::size_t k = 0; k + 1 < path.size(); ++k) {
                base += inst.dist[path[k]][path[k + 1]];
            }
            for (std::size_t slot = 1; slot < path.size(); ++slot) {
                const int i = path[slot - 1];
                const int j = path[slot];
                for (int c : unvisited) {
                    if (c == i || c == j || !ok(arc_allowed, i, c) || !ok(arc_allowed, c, j)) {
                        continue;
                    }
                    std::vector<int> candidate;
                    candidate.reserve(path.size() + 1);
                    candidate.insert(candidate.end(), path.begin(), path.begin() + slot);
                    candidate.push_back(c);
                    candidate.insert(candidate.end(), path.begin() + slot, path.end());
                    Route rec;
                    if (!Route::try_from_path(inst, candidate, &rec)) continue;
                    const double delta = rec.cost - base;
                    const std::tuple<double, int, int, int> key{delta, c,
                                                                static_cast<int>(ri),
                                                                static_cast<int>(slot)};
                    if (!found || key < best) {
                        best = key;
                        found = true;
                    }
                }
            }
        }
        if (!found) {
            if (!open_route()) break;
            continue;
        }
        const int c = std::get<1>(best);
        const int ri = std::get<2>(best);
        const int slot = std::get<3>(best);
        std::vector<int>& path = routes[ri];
        path.insert(path.begin() + slot, c);
        unvisited.erase(std::find(unvisited.begin(), unvisited.end(), c));
    }

    std::vector<Route> records;
    for (const auto& path : routes) {
        Route rec;
        if (Route::try_from_path(inst, path, &rec)) records.push_back(std::move(rec));
    }
    return records;
}

}  // namespace bpvrptw
