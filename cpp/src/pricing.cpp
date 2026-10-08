#include "pricing.hpp"

#include <algorithm>
#include <chrono>
#include <map>
#include <queue>
#include <stdexcept>

namespace bpvrptw {
namespace {
constexpr double kEps = 1e-9;
// Tie-break index handed to the creation-time dominance filter for a brand
// new label: full ties resolve to the incumbent, killing
// permutation-equivalent duplicates early (mirrors labeling.py's 1 << 60).
constexpr long long kNewTieBreak = 1LL << 60;

struct Label {
    int city;
    int parent;  // index into the label pool, -1 for the root
    double cost;
    double time;
    double load;
    Mask mask;
};

struct BucketEntry {
    double cost, time, load;
    Mask mask;
    long long idx;
};

// Standard ESPPRC dominance: a reaches a subset of b's vertices with each
// resource no worse, and is strictly better somewhere; full ties resolve to
// the earlier label.
bool dominates(double cost_a, double time_a, double load_a, const Mask& mask_a, long long idx_a,
               double cost_b, double time_b, double load_b, const Mask& mask_b, long long idx_b) {
    if (!mask_a.is_subset_of(mask_b)) return false;
    if (!(cost_a <= cost_b + kEps && time_a <= time_b + kEps && load_a <= load_b + kEps)) {
        return false;
    }
    if (cost_a < cost_b - kEps || time_a < time_b - kEps || load_a < load_b - kEps ||
        mask_a != mask_b) {
        return true;
    }
    return idx_a < idx_b;
}

struct HeapEntry {
    double cost;
    int city;
    double time;
    double load;
    long long counter;  // unique -> strict weak ordering, deterministic
    long long label_idx;
};

// Best-first: smallest reduced cost first (ties by city/time/load/counter).
struct HeapGreater {
    bool operator()(const HeapEntry& a, const HeapEntry& b) const {
        if (a.cost != b.cost) return a.cost > b.cost;
        if (a.city != b.city) return a.city > b.city;
        if (a.time != b.time) return a.time > b.time;
        if (a.load != b.load) return a.load > b.load;
        return a.counter > b.counter;
    }
};

}  // namespace

EspprcSolver::EspprcSolver(const Instance& inst,
                           const std::vector<std::vector<double>>* reduced_costs,
                           const std::vector<std::vector<char>>* arc_allowed)
    : inst_(inst), rc_(reduced_costs), allowed_(arc_allowed) {
    if (inst.n > 126) {
        throw std::runtime_error("C++ solver supports at most 124 customers per instance");
    }
}

PricingResult EspprcSolver::solve(int max_routes, double threshold, long long max_labels,
                                  double time_limit_seconds) {
    const auto started = std::chrono::steady_clock::now();
    const int n = inst_.n;
    const int start = inst_.start_depot();
    const int end = inst_.end_depot();
    const double capacity = inst_.capacity;

    std::vector<std::vector<double>> ttime(n, std::vector<double>(n));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) ttime[i][j] = inst_.dist[i][j] / inst_.speed;

    PricingResult result;
    long long counter = 0;
    long long n_labels = 1;

    std::vector<Label> labels;
    labels.push_back({start, -1, 0.0, 0.0, 0.0, Mask{}});
    labels[0].mask.set(start);

    std::priority_queue<HeapEntry, std::vector<HeapEntry>, HeapGreater> heap;
    heap.push({0.0, start, 0.0, 0.0, counter++, 0});

    std::vector<std::vector<BucketEntry>> buckets(n);
    std::vector<std::pair<double, long long>> candidates;  // (reduced cost, label idx)
    std::map<std::pair<std::uint64_t, std::uint64_t>, long long> seen_routes;
    bool exhausted = true;

    const bool pruning_enabled = (allowed_ == nullptr);

    while (!heap.empty()) {
        if (time_limit_seconds >= 0.0) {
            const double elapsed =
                std::chrono::duration<double>(std::chrono::steady_clock::now() - started)
                    .count();
            if (elapsed > time_limit_seconds) {
                exhausted = false;
                break;
            }
        }
        if (n_labels >= max_labels) {
            exhausted = false;
            break;
        }

        const HeapEntry entry = heap.top();
        heap.pop();
        const long long idx = entry.label_idx;
        // Copy by value: the j-loop below appends to `labels`, and a
        // reallocation would dangle any reference taken here.
        const Label label = labels[idx];
        std::vector<BucketEntry>& bucket = buckets[label.city];

        // Re-check dominance at pop time (newer labels may dominate us).
        bool dominated = false;
        std::vector<BucketEntry> kept;
        kept.reserve(bucket.size() + 1);
        for (const BucketEntry& item : bucket) {
            if (item.idx != idx &&
                dominates(item.cost, item.time, item.load, item.mask, item.idx, label.cost,
                          label.time, label.load, label.mask, idx)) {
                dominated = true;
                break;
            }
            if (!dominates(label.cost, label.time, label.load, label.mask, idx, item.cost,
                           item.time, item.load, item.mask, item.idx)) {
                kept.push_back(item);
            }
        }
        if (dominated) continue;
        bucket = std::move(kept);
        bucket.push_back({label.cost, label.time, label.load, label.mask, idx});

        // Extend to every admissible unvisited vertex.
        const auto& tt_row = ttime[label.city];
        const auto& rc_row = (rc_ != nullptr) ? (*rc_)[label.city] : inst_.dist[label.city];
        const auto* allow_row = (allowed_ != nullptr) ? &(*allowed_)[label.city] : nullptr;
        const double svc_here = inst_.service_time[label.city];
        const bool at_start = (label.city == start);

        for (int j = 0; j < n; ++j) {
            if (j == label.city || j == start || label.mask.test(j)) continue;
            if (allow_row != nullptr && !(*allow_row)[j]) continue;
            if (at_start && j == end) continue;  // a route needs >= 1 customer

            double arrival = label.time + tt_row[j] + svc_here;
            if (arrival < inst_.ready_time[j]) arrival = inst_.ready_time[j];
            const double new_load = label.load + inst_.demand[j];
            if (arrival > inst_.due_time[j] + kEps || new_load > capacity + kEps) continue;
            const double new_cost = label.cost + rc_row[j];
            Mask new_mask = label.mask;
            new_mask.set(j);

            if (j == end) {
                auto key = std::make_pair(new_mask.lo, new_mask.hi);
                auto it = seen_routes.find(key);
                if (it != seen_routes.end() && labels[it->second].cost <= new_cost + kEps) {
                    continue;  // permutation duplicate; keep the first
                }
                labels.push_back({j, static_cast<int>(idx), new_cost, arrival, new_load, new_mask});
                const long long child = static_cast<long long>(labels.size()) - 1;
                seen_routes[key] = child;
                ++n_labels;
                if (new_cost < threshold) candidates.emplace_back(new_cost, child);
                continue;
            }

            // Feillet-style pruning: mark customers unreachable from here as
            // visited (skipped entirely under forbidden arcs).
            Mask child_mask = new_mask;
            if (pruning_enabled) {
                for (int k = 1; k < n - 1; ++k) {
                    if (child_mask.test(k)) continue;
                    const double earliest = arrival + tt_row[k] + inst_.service_time[j];
                    if (earliest > inst_.due_time[k] + kEps ||
                        new_load + inst_.demand[k] > capacity + kEps) {
                        child_mask.set(k);
                    }
                }
            }

            bool dominated_at_creation = false;
            for (const BucketEntry& item : buckets[j]) {
                if (dominates(item.cost, item.time, item.load, item.mask, item.idx, new_cost,
                              arrival, new_load, child_mask, kNewTieBreak)) {
                    dominated_at_creation = true;
                    break;
                }
            }
            if (dominated_at_creation) continue;

            labels.push_back({j, static_cast<int>(idx), new_cost, arrival, new_load, child_mask});
            const long long child = static_cast<long long>(labels.size()) - 1;
            ++n_labels;
            heap.push({new_cost, j, arrival, new_load, counter++, child});
        }
    }

    // Reconstruct the best `max_routes` candidates, most negative first,
    // deduplicating permutation-equivalent routes at extraction time.
    std::sort(candidates.begin(), candidates.end(),
              [](const std::pair<double, long long>& a, const std::pair<double, long long>& b) {
                  if (a.first != b.first) return a.first < b.first;
                  return a.second < b.second;
              });
    std::map<std::pair<std::uint64_t, std::uint64_t>, char> emitted;
    for (const auto& [cost, idx] : candidates) {
        std::vector<int> walk_path;
        for (long long walk = idx; walk >= 0; walk = labels[walk].parent) {
            walk_path.push_back(labels[walk].city);
        }
        std::reverse(walk_path.begin(), walk_path.end());
        const Mask& mask = labels[idx].mask;
        auto key = std::make_pair(mask.lo, mask.hi);
        if (emitted.count(key)) continue;
        emitted[key] = 1;

        PricedRoute route;
        route.path = std::move(walk_path);
        route.reduced_cost = cost;
        for (std::size_t k = 0; k + 1 < route.path.size(); ++k) {
            route.true_cost += inst_.dist[route.path[k]][route.path[k + 1]];
        }
        result.routes.push_back(std::move(route));
        if (static_cast<int>(result.routes.size()) >= max_routes) break;
    }

    result.n_labels_explored = n_labels;
    result.exhausted = exhausted;
    result.elapsed_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    return result;
}

}  // namespace bpvrptw
