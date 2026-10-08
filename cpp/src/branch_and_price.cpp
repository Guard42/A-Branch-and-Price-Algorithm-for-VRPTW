#include "branch_and_price.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <set>

#include "construction.hpp"

namespace bpvrptw {
namespace {
constexpr double kForbidden = 1e10;
constexpr double kPricingEps = 1e-9;

bool arc_allowed_at(const std::vector<std::vector<double>>& dist, int i, int j) {
    return dist[i][j] < (kForbidden - 1e6);
}

void apply_branching(std::vector<std::vector<double>>& dist,
                     const std::vector<std::vector<double>>& base_dist, int branch_from,
                     int branch_to, int branch_value) {
    const int start_depot = 0;
    const int end_depot = static_cast<int>(dist.size()) - 1;
    const int n = static_cast<int>(dist.size());
    if (branch_value == 0) {
        dist[branch_from][branch_to] = kForbidden;
        return;
    }
    // value 1: from `branch_from` only `branch_to` remains reachable (unless
    // branching out of the start depot: many routes may leave it), and into
    // `branch_to` only `branch_from` may arrive (unless it is the end depot:
    // many routes may return there). The reverse arc is always forbidden.
    if (branch_from != start_depot) {
        for (int j = 0; j < n; ++j) dist[branch_from][j] = kForbidden;
        dist[branch_from][branch_to] = base_dist[branch_from][branch_to];
    }
    if (branch_to != end_depot) {
        for (int i = 0; i < n; ++i) dist[i][branch_to] = kForbidden;
        dist[branch_from][branch_to] = base_dist[branch_from][branch_to];
    }
    dist[branch_to][branch_from] = kForbidden;
}

// Closest-to-0.5 fractional edge (Ryan-Foster style), ties toward larger
// true edge cost, then lexicographic. Returns false when integral.
bool select_branch_edge(const std::vector<std::vector<double>>& edges,
                        const std::vector<std::vector<double>>& true_dist, int* out_from,
                        int* out_to) {
    const int n = static_cast<int>(edges.size());
    double best_score = -1.0, best_cost = -1.0;
    bool found = false;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            const double coef = edges[i][j];
            if (coef <= 1e-6) continue;
            if (std::fabs(coef - std::round(coef)) < 1e-8) continue;
            const double frac_floor = coef - std::floor(coef);
            const double score = std::min(frac_floor, 1.0 - frac_floor);
            const double cost_ij = true_dist[i][j];
            if (score > best_score + 1e-12 ||
                (std::fabs(score - best_score) <= 1e-12 && cost_ij > best_cost + 1e-12)) {
                best_score = score;
                best_cost = cost_ij;
                *out_from = i;
                *out_to = j;
                found = true;
            }
        }
    }
    return found;
}

struct BpContext {
    const Instance& inst;
    double gap;
    double deadline;  // steady seconds; < 0 means unbounded
    double started;
    double lowerbound = -1e10;
    double upperbound = 1e10;
    std::vector<Route> best_routes;
    int nodes_visited = 0;

    double now() const {
        return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch())
            .count();
    }
};

struct BpNode {
    BpNode* father = nullptr;
    BpNode* son0 = nullptr;
    int branch_from = -1;
    int branch_to = -1;
    int branch_value = -1;
    double lowest_value = -1e10;
    bool toplevel = false;
};

bool path_uses_arc(const Route& r, int i, int j) {
    for (std::size_t k = 0; k + 1 < r.path.size(); ++k) {
        if (r.path[k] == i && r.path[k + 1] == j) return true;
    }
    return false;
}

std::vector<std::vector<double>> edge_usage(const Instance& inst,
                                            const std::vector<ColumnValuePair>& columns) {
    const int n = inst.n;
    std::vector<std::vector<double>> edges(n, std::vector<double>(n, 0.0));
    for (const ColumnValuePair& cv : columns) {
        if (cv.value <= 1e-6) continue;
        for (std::size_t k = 0; k + 1 < cv.route.path.size(); ++k) {
            edges[cv.route.path[k]][cv.route.path[k + 1]] += cv.value;
        }
    }
    return edges;
}

bool has_fractional_edge(const std::vector<std::vector<double>>& edges) {
    for (const auto& row : edges) {
        for (double e : row) {
            if (e > 1e-6 && std::fabs(e - std::round(e)) >= 1e-8) return true;
        }
    }
    return false;
}

// Records the node's primal solution as incumbent when integral. Returns
// true when an incumbent was recorded; also used for partially converged
// nodes whose primal happens to be integral (feasible solution, unsound
// bound).
bool maybe_record_incumbent(BpContext& ctx, const CgResult& result, int depth, bool verbose) {
    const std::vector<std::vector<double>> edges = edge_usage(ctx.inst, result.column_values);
    if (has_fractional_edge(edges)) return false;
    double total = 0.0;
    std::vector<Route> selected;
    for (const ColumnValuePair& cv : result.column_values) {
        if (cv.value > 1e-6) {
            total += cv.route.cost;
            selected.push_back(cv.route);
        }
    }
    if (total < ctx.upperbound) {
        ctx.upperbound = total;
        ctx.best_routes = std::move(selected);
        if (verbose) {
            std::printf("  INCUMBENT | UB=%.6f depth=%d nodes=%d\n", ctx.upperbound, depth,
                        ctx.nodes_visited);
        }
    } else if (verbose) {
        std::printf("  FEAS | UB=%.6f depth=%d\n", ctx.upperbound, depth);
    }
    return true;
}

void node_recursion(BpNode& node, const std::vector<std::vector<double>>& dist_matrix,
                    std::vector<Route> routes, int depth, BpContext& ctx, bool verbose) {
    ++ctx.nodes_visited;
    if (ctx.deadline >= 0 && ctx.now() > ctx.deadline) {
        std::printf("WARNING: time limit hit at depth %d; stopping search\n", depth);
        return;  // lowest_value stays at -1e10, exactly like the Python tree
    }
    if ((ctx.upperbound - ctx.lowerbound) / std::max(ctx.upperbound, 1e-10) < ctx.gap) {
        return;
    }

    const int n = ctx.inst.n;
    std::vector<std::vector<char>> allowed(n, std::vector<char>(n, 0));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) allowed[i][j] = arc_allowed_at(dist_matrix, i, j) ? 1 : 0;

    CgResult result;
    try {
        ColumnGeneration cg(ctx.inst);
        double remaining = -1.0;
        if (ctx.deadline >= 0) remaining = std::max(0.01, ctx.deadline - ctx.now());
        result = cg.solve(&routes, &allowed, 500, remaining);
    } catch (const std::runtime_error&) {
        // The master problem cannot even be seeded under these branching
        // constraints -> subtree infeasible.
        node.lowest_value = 1e11;
        return;
    }

    // Infeasible-relaxation detection: forbidden arcs inflate column costs
    // beyond any real solution (same convention as the legacy code).
    double maxlength = 0.0;
    for (const auto& row : ctx.inst.dist) {
        maxlength += *std::max_element(row.begin(), row.end());
    }
    if (result.objective > 2 * maxlength || result.objective < kPricingThreshold) {
        if (verbose) std::printf("  RELAX INFEASIBLE | depth=%d obj=%.4f\n", depth, result.objective);
        node.lowest_value = 1e11;
        return;
    }

    if (result.status != "optimal") {
        // Pricing did not run to exhaustion: the current RMP objective is
        // NOT a valid global lower bound. Record an integral incumbent if
        // the partial solution happens to be integral, then stop descending
        // -- branching on unproven bounds would make every downstream claim
        // unsound.
        maybe_record_incumbent(ctx, result, depth, verbose);
        return;
    }

    node.lowest_value = result.objective;
    // Global lower-bound bookkeeping (identical structure to the Python tree).
    if (node.father != nullptr && node.father->son0 != nullptr && node.father->toplevel) {
        ctx.lowerbound = std::min(node.lowest_value, node.father->son0->lowest_value);
        node.toplevel = true;
    } else if (node.father == nullptr) {
        ctx.lowerbound = result.objective;
    }

    if (node.lowest_value > ctx.upperbound) {
        if (verbose) {
            std::printf("  CUT | LB=%.6f UB=%.6f depth=%d\n", ctx.lowerbound, ctx.upperbound,
                        depth);
        }
        return;
    }

    const std::vector<std::vector<double>> edges = edge_usage(ctx.inst, result.column_values);
    int bf = -1, bt = -1;
    if (!select_branch_edge(edges, ctx.inst.dist, &bf, &bt)) {
        maybe_record_incumbent(ctx, result, depth, verbose);
        return;
    }
    const double coef = edges[bf][bt];
    const int best_val = (std::fabs(1.0 - coef) > coef) ? 0 : 1;
    if (verbose) {
        std::printf("  INTEG INFEAS | LB=%.6f UB=%.6f depth=%d branch %d->%d val=%d\n",
                    ctx.lowerbound, ctx.upperbound, depth, bf, bt, best_val);
    }

    // ---- Child 1: parent's matrix plus this decision --------------------
    BpNode child1;
    child1.father = &node;
    child1.branch_from = bf;
    child1.branch_to = bt;
    child1.branch_value = best_val;
    std::vector<std::vector<double>> dist1 = dist_matrix;
    apply_branching(dist1, ctx.inst.dist, bf, bt, best_val);
    std::vector<Route> keep1;
    for (const Route& r : routes) {
        if (r.path.size() <= 3 || !path_uses_arc(r, bf, bt)) keep1.push_back(r);
    }
    node_recursion(child1, dist1, std::move(keep1), depth + 1, ctx, verbose);
    node.son0 = &child1;

    // ---- Child 2: pristine matrix plus ALL ancestor decisions ------------
    BpNode child2;
    child2.father = &node;
    child2.branch_from = bf;
    child2.branch_to = bt;
    child2.branch_value = 1 - best_val;
    std::vector<std::vector<double>> dist2 = ctx.inst.dist;
    std::vector<const BpNode*> chain;
    for (const BpNode* walker = &node; walker != nullptr && walker->branch_from >= 0;
         walker = walker->father) {
        chain.push_back(walker);
    }
    for (auto it = chain.rbegin(); it != chain.rend(); ++it) {
        apply_branching(dist2, ctx.inst.dist, (*it)->branch_from, (*it)->branch_to,
                        (*it)->branch_value);
    }
    apply_branching(dist2, ctx.inst.dist, bf, bt, 1 - best_val);
    std::vector<Route> keep2;
    for (const Route& r : routes) {
        if (r.path.size() <= 3) {
            keep2.push_back(r);
            continue;
        }
        bool admissible = true;
        for (std::size_t k = 0; k + 1 < r.path.size(); ++k) {
            if (!(dist2[r.path[k]][r.path[k + 1]] < kForbidden - 1e-6)) {
                admissible = false;
                break;
            }
        }
        if (admissible) keep2.push_back(r);
    }
    node_recursion(child2, dist2, std::move(keep2), depth + 1, ctx, verbose);
    node.lowest_value = std::min(child1.lowest_value, child2.lowest_value);
}

}  // namespace

BranchAndPrice::BranchAndPrice(const Instance& inst, double gap, double time_limit_seconds,
                               bool verbose)
    : inst_(inst), gap_(gap), time_limit_(time_limit_seconds), verbose_(verbose) {}

BpResult BranchAndPrice::solve() {
    const auto started = std::chrono::steady_clock::now();
    BpContext ctx{inst_, gap_,
                  time_limit_ >= 0
                      ? std::chrono::duration<double>(
                            std::chrono::steady_clock::now().time_since_epoch())
                                    .count() +
                            time_limit_
                      : -1.0,
                  0.0};

    // Upper bound on any single-route length; used for the legacy-style
    // "relaxation became infeasible because arcs got forbidden" test.
    double maxlength = 0.0;
    for (const auto& row : inst_.dist) maxlength += *std::max_element(row.begin(), row.end());
    (void)maxlength;

    std::vector<Route> seed_routes;
    for (int c = 1; c <= inst_.n_customers(); ++c) {
        Route rec;
        if (Route::try_from_path(inst_, {0, c, inst_.end_depot()}, &rec)) {
            seed_routes.push_back(std::move(rec));
        }
    }

    BpResult out;
    out.instance_name = inst_.name;
    if (seed_routes.empty()) {
        out.status = "INFEASIBLE";
        out.solve_time_seconds =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        out.bb_nodes = 0;
        return out;
    }

    // Initial incumbent: prefer the construction heuristic; extend it with
    // solo routes for uncovered customers; fall back to pure singles.
    std::vector<Route> initial_pool = seed_routes;
    const std::vector<Route> constructed = greedy_insertion_routes(inst_);
    if (!constructed.empty()) {
        std::set<int> covered;
        double load_sum = 0.0;
        for (const Route& r : constructed) {
            for (std::size_t k = 1; k + 1 < r.path.size(); ++k) {
                covered.insert(r.path[k]);
            }
            load_sum += r.load;
            initial_pool.push_back(r);
        }
        for (int c = 1; c <= inst_.n_customers(); ++c) {
            if (covered.count(c)) continue;
            Route rec;
            if (Route::try_from_path(inst_, {0, c, inst_.end_depot()}, &rec)) {
                initial_pool.push_back(std::move(rec));
            }
        }
        const bool missing = covered.size() != static_cast<std::size_t>(inst_.n_customers());
        if (!missing && load_sum <= inst_.capacity * inst_.vehicle_count + 1e-9) {
            // The heuristic covers everyone -> a valid incumbent.
            double total = 0.0;
            for (const Route& r : constructed) total += r.cost;
            ctx.upperbound = total;
            ctx.best_routes = constructed;
        }
    } else {
        double total = 0.0;
        for (const Route& r : seed_routes) total += r.cost;
        ctx.upperbound = total;
        ctx.best_routes = seed_routes;
    }

    BpNode root;
    root.toplevel = true;
    node_recursion(root, inst_.dist, std::move(initial_pool), 0, ctx, verbose_);

    const bool timed_out = ctx.deadline >= 0 && ctx.now() > ctx.deadline;
    const bool lb_valid = ctx.lowerbound > -1e9;
    double total = 0.0;
    for (const Route& r : ctx.best_routes) total += r.cost;
    out.routes = ctx.best_routes;
    out.total_cost = total;
    out.has_lower_bound = lb_valid;
    out.lower_bound = ctx.lowerbound;
    out.bb_nodes = ctx.nodes_visited;
    out.solve_time_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    out.gap_closed = lb_valid && !ctx.best_routes.empty() &&
                     (ctx.upperbound - ctx.lowerbound) /
                             std::max(std::fabs(ctx.upperbound), 1e-10) <
                         gap_;
    if (ctx.best_routes.empty()) {
        out.status = "INFEASIBLE";
    } else if (out.gap_closed && !timed_out) {
        out.status = "SOLVED_OPTIMAL";
    } else if (timed_out) {
        out.status = "TIME_LIMIT";
    } else {
        out.status = "SOLVED_FEASIBLE";
    }
    out.gap_pct =
        (!lb_valid || ctx.best_routes.empty())
            ? 0.0
            : std::max(0.0, (ctx.upperbound - ctx.lowerbound) /
                                    std::max(std::fabs(ctx.upperbound), 1e-10) * 100.0);
    return out;
}

}  // namespace bpvrptw
