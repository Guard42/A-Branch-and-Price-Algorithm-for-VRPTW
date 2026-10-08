// Dense revised simplex for the restricted master problem.
//
// Replaces the Python package's pluggable LP backends with a self-contained
// oracle, so the C++ implementation needs no external solver and no
// license. Master problem (one covering row per customer, identical to
// bpvrptw/rmp.py)::
//
//     minimize   sum_p  cost_p * y_p
//     subject to sum_p  a_{cp} * y_p >= 1    for every customer c
//                y_p >= 0
//
// At optimality the row duals pi are nonnegative and every column satisfies
// reduced_cost = cost - sum(pi[c] for c in covers) >= 0 (within tolerance),
// matching the dual sign convention of the HiGHS/Gurobi backends.
#pragma once

#include <vector>

namespace bpvrptw {

struct RmpSolution {
    double objective = 0.0;
    std::vector<double> duals;   // one per coverage row
    std::vector<double> primal;  // one per structural column
};

class CoveringSimplex {
public:
    explicit CoveringSimplex(int n_rows);

    // Appends a structural column (sorted row indices, cost) and returns
    // its column index. The basis is untouched: the next solve() warm
    // starts from it.
    int add_column(double cost, const std::vector<int>& covers);

    // Solves the current LP to optimality. Throws std::runtime_error when
    // the LP is infeasible (master problems should always be feasible:
    // seed columns exist).
    RmpSolution solve();

    int n_columns() const { return static_cast<int>(costs_.size()); }

private:
    enum class ColKind { kStructural, kSurplus, kArtificial };
    struct ColRef {
        ColKind kind;
        int id;  // structural column index / row index
    };

    // Stable total order over all columns; used for deterministic Bland
    // rules and ratio-test tie-breaks.
    long long order_id(const ColRef& c) const {
        switch (c.kind) {
            case ColKind::kStructural: return c.id;
            case ColKind::kSurplus: return 1000000000LL + c.id;
            default: return 2000000000LL + c.id;
        }
    }

    void refresh_inverse();                     // Gauss-Jordan re-inversion
    std::vector<double> compute_duals() const;  // pi = Binv^T c_B
    std::vector<double> direction(const ColRef& col) const;  // Binv * a_col
    bool basic(const ColRef& c) const {
        return c.kind == ColKind::kStructural ? structural_basic_[c.id]
                                              : (c.kind == ColKind::kSurplus
                                                     ? surplus_basic_[c.id]
                                                     : artificial_basic_[c.id]);
    }
    void pivot(int row, const ColRef& enter);
    bool iterate(int phase);  // one simplex iteration; false when optimal

    int m_;
    std::vector<double> costs_;
    std::vector<std::vector<int>> covers_;  // structural columns' rows

    std::vector<ColRef> basis_;
    std::vector<std::vector<double>> binv_;  // m x m explicit inverse of B
    std::vector<double> x_basic_;
    std::vector<char> structural_basic_, surplus_basic_, artificial_basic_;
    int phase_ = 1;  // 1: feasibility, 2: original objective
    int degenerate_streak_ = 0;
    int since_refresh_ = 0;
};

}  // namespace bpvrptw
