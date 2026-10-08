#include "instance.hpp"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace bpvrptw {
namespace {
constexpr double kDistanceScale = 10.0;
constexpr double kEps = 1e-9;

std::vector<std::string> read_lines(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot read " + path);
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(in, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
        lines.push_back(line);
    }
    return lines;
}
}  // namespace

Instance Instance::from_solomon(const std::string& path, double speed) {
    auto lines = read_lines(path);
    if (lines.size() < 10) {
        throw std::runtime_error(path + ": expected at least 10 lines (9 header + data), got " +
                                 std::to_string(lines.size()));
    }

    Instance inst;
    inst.speed = speed;
    {
        std::istringstream name_stream(lines[0]);
        name_stream >> inst.name;
    }
    {
        std::istringstream vehicle_stream(lines[4]);
        if (!(vehicle_stream >> inst.vehicle_count >> inst.capacity)) {
            throw std::runtime_error(path + ": line 5 is not '<int> <number>'");
        }
    }
    if (inst.vehicle_count <= 0) throw std::runtime_error("vehicle_count must be positive");
    if (inst.capacity <= 0) throw std::runtime_error("capacity must be positive");
    if (speed <= 0) throw std::runtime_error("speed must be positive");

    struct Row {
        int id;
        double x, y, demand, ready, due, service;
    };
    std::vector<Row> rows;
    for (std::size_t i = 9; i < lines.size(); ++i) {
        const std::string& raw = lines[i];
        if (raw.find_first_not_of(" \t") == std::string::npos) continue;
        std::istringstream stream(raw);
        Row row{};
        if (!(stream >> row.id >> row.x >> row.y >> row.demand >> row.ready >> row.due >>
              row.service)) {
            throw std::runtime_error(path + ": line " + std::to_string(i + 1) +
                                     ": expected 7 columns");
        }
        rows.push_back(row);
    }
    if (rows.empty()) throw std::runtime_error(path + ": no customer data rows found");

    // Some Solomon files repeat the depot as an explicit end-depot row;
    // drop it when the last row duplicates the depot with zero demand.
    if (rows.size() >= 2) {
        const Row& depot = rows[0];
        const Row& last = rows.back();
        if (std::fabs(last.x - depot.x) < 1e-9 && std::fabs(last.y - depot.y) < 1e-9 &&
            last.demand == 0.0) {
            rows.pop_back();
        }
    }

    const int customers = static_cast<int>(rows.size()) - 1;
    if (customers < 2) {
        throw std::runtime_error("an instance needs at least depot + 2 customers");
    }
    inst.n = customers + 2;
    const int n = inst.n;
    inst.x.assign(n, 0.0);
    inst.y.assign(n, 0.0);
    inst.demand.assign(n, 0.0);
    inst.ready_time.assign(n, 0.0);
    inst.due_time.assign(n, 0.0);
    inst.service_time.assign(n, 0.0);

    const Row& depot = rows[0];
    inst.x[0] = depot.x;
    inst.y[0] = depot.y;
    inst.ready_time[0] = depot.ready;
    inst.due_time[0] = depot.due;
    inst.service_time[0] = depot.service;
    for (int i = 1; i <= customers; ++i) {
        const Row& row = rows[i];
        inst.x[i] = row.x;
        inst.y[i] = row.y;
        inst.demand[i] = row.demand;
        inst.ready_time[i] = row.ready;
        inst.due_time[i] = row.due;
        inst.service_time[i] = row.service;
        if (row.demand < 0) throw std::runtime_error("demands must be non-negative");
        if (row.due < row.ready - kEps) {
            throw std::runtime_error("vertex " + std::to_string(row.id) +
                                     ": due_time precedes ready_time");
        }
    }
    // End depot mirrors the start depot, zero demand and service.
    inst.x[n - 1] = inst.x[0];
    inst.y[n - 1] = inst.y[0];
    inst.ready_time[n - 1] = inst.ready_time[0];
    inst.due_time[n - 1] = inst.due_time[0];
    inst.service_time[n - 1] = 0.0;

    inst.dist.assign(n, std::vector<double>(n, 0.0));
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            const double dx = inst.x[i] - inst.x[j];
            const double dy = inst.y[i] - inst.y[j];
            inst.dist[i][j] = std::round(kDistanceScale * std::sqrt(dx * dx + dy * dy)) /
                              kDistanceScale;
        }
    }
    return inst;
}

}  // namespace bpvrptw
