// Command-line solver: bpvrptw_cpp <instance> [--time-limit S] [--verbose]
// Prints the result in a JSON-like summary (mirrors `python -m bpvrptw solve`).
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "branch_and_price.hpp"
#include "instance.hpp"

int main(int argc, char** argv) {
    std::string path;
    double time_limit = -1.0;
    bool verbose = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--time-limit" && i + 1 < argc) {
            time_limit = std::atof(argv[++i]);
        } else if (arg == "--verbose") {
            verbose = true;
        } else if (arg == "--help" || arg == "-h") {
            std::printf("usage: bpvrptw_cpp <instance.solomon> [--time-limit S] [--verbose]\n");
            return 0;
        } else {
            path = arg;
        }
    }
    if (path.empty()) {
        std::fprintf(stderr, "error: no instance file given\n");
        std::fprintf(stderr, "usage: bpvrptw_cpp <instance.solomon> [--time-limit S] [--verbose]\n");
        return 2;
    }

    bpvrptw::Instance inst;
    try {
        inst = bpvrptw::Instance::from_solomon(path);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 2;
    }

    const bpvrptw::BpResult result =
        bpvrptw::BranchAndPrice(inst, 1e-6, time_limit, verbose).solve();

    std::printf("status        %s\n", result.status.c_str());
    std::printf("instance      %s\n", result.instance_name.c_str());
    std::printf("total_cost    %.2f\n", result.total_cost);
    std::printf("routes        %zu\n", result.routes.size());
    if (result.has_lower_bound) std::printf("lower_bound   %.2f\n", result.lower_bound);
    std::printf("bb_nodes      %d\n", result.bb_nodes);
    std::printf("time_seconds  %.2f\n", result.solve_time_seconds);
    for (const bpvrptw::Route& route : result.routes) {
        std::printf("route         ");
        for (std::size_t k = 0; k < route.path.size(); ++k) {
            std::printf("%d%s", route.path[k], k + 1 < route.path.size() ? " " : "");
        }
        std::printf("  cost=%.2f load=%.0f\n", route.cost, route.load);
    }
    return result.routes.empty() ? 1 : 0;
}
