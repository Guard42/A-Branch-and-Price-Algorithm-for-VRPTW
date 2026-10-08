// Correctness gate: solve a set of bundled Solomon instances and assert the
// known optimal costs (cross-checked in the Python README benchmark tables
// against both branch-and-price and a direct Gurobi MIP).
#include <cstdio>
#include <string>
#include <vector>

#include "branch_and_price.hpp"
#include "instance.hpp"
#include "route.hpp"

namespace {

struct KnownOptimum {
    const char* file;
    double cost;
};

// Instances proven optimal by both the Python solver and the Gurobi MIP
// baseline (README benchmark tables), each solving in seconds.
const std::vector<KnownOptimum>& known_optima() {
    static const std::vector<KnownOptimum> kOptima = {
        {"C101_25.txt", 191.70}, {"C105.txt", 191.70},  {"C201.txt", 215.60},
        {"R101.txt", 618.10},    {"R102.txt", 547.90}, {"R103.txt", 455.60},
        {"R105.txt", 531.30},    {"RC102.txt", 352.90},
    };
    return kOptima;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string dataset_dir = (argc > 1) ? argv[1] : "dataset";
    int failures = 0;
    for (const KnownOptimum& known : known_optima()) {
        const std::string path = dataset_dir + "/" + known.file;
        bpvrptw::Instance inst;
        try {
            inst = bpvrptw::Instance::from_solomon(path);
        } catch (const std::exception& e) {
            std::printf("FAIL %s: %s\n", known.file, e.what());
            ++failures;
            continue;
        }
        const bpvrptw::BpResult result =
            bpvrptw::BranchAndPrice(inst, 1e-6, 300.0, false).solve();

        // Full feasibility self-check: every customer exactly once, every
        // route capacity- and time-window-feasible.
        bool feasible = result.status == "SOLVED_OPTIMAL";
        std::vector<int> served_count(static_cast<std::size_t>(inst.n), 0);
        for (const bpvrptw::Route& route : result.routes) {
            bpvrptw::Route rec;
            if (!bpvrptw::Route::try_from_path(inst, route.path, &rec)) feasible = false;
            for (std::size_t k = 1; k + 1 < route.path.size(); ++k) {
                ++served_count[static_cast<std::size_t>(route.path[k])];
            }
        }
        for (int c = 1; c <= inst.n_customers(); ++c) {
            if (served_count[static_cast<std::size_t>(c)] != 1) feasible = false;
        }

        const bool cost_ok = result.status == "SOLVED_OPTIMAL" &&
                             (result.total_cost - known.cost) * (result.total_cost - known.cost) <
                                 1e-4;
        if (feasible && cost_ok) {
            std::printf("PASS %-12s cost=%.2f routes=%zu nodes=%d time=%.2fs\n", known.file,
                        result.total_cost, result.routes.size(), result.bb_nodes,
                        result.solve_time_seconds);
        } else {
            std::printf("FAIL %-12s status=%s cost=%.2f expected=%.2f feasible=%s\n", known.file,
                        result.status.c_str(), result.total_cost, known.cost,
                        feasible ? "yes" : "no");
            ++failures;
        }
    }
    if (failures) {
        std::printf("%d/%zu checks FAILED\n", failures, known_optima().size());
        return 1;
    }
    std::printf("all %zu known optima reproduced\n", known_optima().size());
    return 0;
}
