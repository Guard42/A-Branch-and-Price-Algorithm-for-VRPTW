// Solomon-format VRPTW instance: parsing and derived matrices.
//
// Vertex indexing mirrors the Python package: 0 is the start depot,
// n-1 a copy of the depot acting as route end, 1..n-2 the customers.
// Distances are rounded to one decimal (Solomon benchmark convention),
// exactly like bpvrptw/instance.py.
#pragma once

#include <string>
#include <vector>

namespace bpvrptw {

struct Instance {
    std::string name;
    int vehicle_count = 0;
    double capacity = 0.0;
    double speed = 1.0;
    int n = 0;  // total vertices including both depot copies

    std::vector<double> x, y;
    std::vector<double> demand, ready_time, due_time, service_time;
    std::vector<std::vector<double>> dist;

    int start_depot() const { return 0; }
    int end_depot() const { return n - 1; }
    int n_customers() const { return n - 2; }

    double travel_time(int i, int j) const { return dist[i][j] / speed; }

    // Throws std::runtime_error on any structural violation.
    static Instance from_solomon(const std::string& path, double speed = 1.0);
};

}  // namespace bpvrptw
