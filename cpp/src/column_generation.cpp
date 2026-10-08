#include "column_generation.hpp"

#include <algorithm>
#include <chrono>
#include <set>
#include <stdexcept>

#include "construction.hpp"
#include "pricing.hpp"

namespace bpvrptw {
namespace {
// Interior vertex ids (1..n-2) map to coverage rows (0..m-1) by subtracting
// the start depot — mirrors rmp.py's row_of_customer.
std::vector<int> interior_rows(const std::vector<int>& path) {
    std::vector<int> rows;
    rows.reserve(path.size() - 2);
    for (std::size_t k = 1; k + 1 < path.size(); ++k) rows.push_back(path[k] - 1);
    return rows;
}
}  // namespace

std::vector<Route> default_seed_columns(const Instance& inst,
                                        const std::vector<std::vector<char>>* arc_allowed) {
    const int end = inst.end_depot();
    std::vector<Route> seeds;
    for (int customer = 1; customer <= inst.n_customers(); ++customer) {
        if (arc_allowed != nullptr && (!(*arc_allowed)[0][customer] ||
                                       !(*arc_allowed)[customer][end])) {
            continue;  // pricing must cover this customer
        }
        Route rec;
        if (Route::try_from_path(inst, {0, customer, end}, &rec)) seeds.push_back(std::move(rec));
    }
    if (seeds.empty()) {
        throw std::runtime_error("no feasible single-customer route exists");
    }
    for (const Route& route : greedy_insertion_routes(inst, arc_allowed)) {
        const std::set<int> key(route.path.begin() + 1, route.path.end() - 1);
        bool duplicate = false;
        for (const Route& s : seeds) {
            const std::set<int> other(s.path.begin() + 1, s.path.end() - 1);
            if (other == key) {
                duplicate = true;
                break;
            }
        }
        if (!duplicate) seeds.push_back(route);
    }
    return seeds;
}

CgResult ColumnGeneration::solve(const std::vector<Route>* seed_columns,
                                 const std::vector<std::vector<char>>* arc_allowed,
                                 int max_iterations, double time_limit_seconds) {
    const auto started = std::chrono::steady_clock::now();
    const auto elapsed = [&] {
        return std::chrono::duration<double>(std::chrono::steady_clock::now() - started)
            .count();
    };

    std::vector<Route> records =
        (seed_columns != nullptr) ? *seed_columns : default_seed_columns(inst_, arc_allowed);

    CoveringSimplex backend(inst_.n_customers());
    for (const Route& r : records) {
        backend.add_column(r.cost, interior_rows(r.path));
    }

    const int pricing_routes = std::min(inst_.n_customers(), 20);
    int iterations = 0;
    std::string status = "optimal";
    RmpSolution solution = backend.solve();

    while (true) {
        // rc[i][j] = dist[i][j] - duals[i-1] for interior i; depot rows keep
        // zero shift so their arcs retain distance cost.
        const int n = inst_.n;
        std::vector<double> shift(n, 0.0);
        for (int i = 1; i <= inst_.n_customers(); ++i) shift[i] = solution.duals[i - 1];
        std::vector<std::vector<double>> rc(n, std::vector<double>(n));
        for (int i = 0; i < n; ++i)
            for (int j = 0; j < n; ++j) rc[i][j] = inst_.dist[i][j] - shift[i];

        double remaining = -1.0;
        if (time_limit_seconds >= 0.0) {
            remaining = std::max(0.01, time_limit_seconds - elapsed());
        }
        PricingResult priced =
            EspprcSolver(inst_, &rc, arc_allowed)
                .solve(pricing_routes, kPricingThreshold, 2'000'000, remaining);

        if (!priced.routes.empty() && !priced.exhausted && time_limit_seconds >= 0.0 &&
            elapsed() >= time_limit_seconds) {
            status = "time_limit";
            break;
        }
        if (priced.routes.empty()) break;

        ++iterations;
        if (iterations >= max_iterations) {
            status = "iteration_limit";
            break;
        }
        if (time_limit_seconds >= 0.0 && elapsed() > time_limit_seconds) {
            status = "time_limit";
            break;
        }

        for (const PricedRoute& priced_route : priced.routes) {
            Route rec;
            if (!Route::try_from_path(inst_, priced_route.path, &rec)) {
                throw std::runtime_error("pricing returned an infeasible route");
            }
            records.push_back(std::move(rec));
            backend.add_column(records.back().cost, interior_rows(priced_route.path));
        }
        solution = backend.solve();
    }

    CgResult result;
    result.objective = solution.objective;
    result.iterations = iterations;
    result.n_columns = static_cast<int>(records.size());
    result.status = status;
    result.lower_bound = solution.objective;
    result.column_values.reserve(records.size());
    for (std::size_t k = 0; k < records.size(); ++k) {
        result.column_values.push_back({std::move(records[k]), solution.primal[k]});
    }
    return result;
}

}  // namespace bpvrptw
