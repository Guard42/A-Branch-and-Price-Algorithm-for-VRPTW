#include "route.hpp"

#include <cmath>
#include <set>

namespace bpvrptw {
namespace {
constexpr double kTol = 1e-6;
constexpr double kTimeEps = 1e-9;
}  // namespace

bool Route::try_from_path(const Instance& inst, const std::vector<int>& path, Route* out) {
    if (path.size() < 3) return false;
    if (path.front() != inst.start_depot() || path.back() != inst.end_depot()) return false;
    std::set<int> interior(path.begin() + 1, path.end() - 1);
    if (interior.size() != path.size() - 2) return false;  // duplicate customer
    for (int city : interior) {
        if (city < 1 || city > inst.n_customers()) return false;
    }

    Route rec;
    rec.path = path;
    for (std::size_t k = 0; k + 1 < path.size(); ++k) rec.cost += inst.dist[path[k]][path[k + 1]];
    for (std::size_t k = 1; k + 1 < path.size(); ++k) rec.load += inst.demand[path[k]];
    if (rec.load > inst.capacity + kTol) return false;

    double t = 0.0;
    int prev = path[0];
    for (std::size_t k = 1; k < path.size(); ++k) {
        const int city = path[k];
        t += inst.travel_time(prev, city) + inst.service_time[prev];
        t = std::max(t, inst.ready_time[city]);
        if (t > inst.due_time[city] + kTimeEps) return false;
        prev = city;
    }
    rec.duration = t;
    if (out) *out = std::move(rec);
    return true;
}

}  // namespace bpvrptw
