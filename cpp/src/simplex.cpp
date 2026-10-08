#include "simplex.hpp"

#include <cmath>
#include <stdexcept>

namespace bpvrptw {
namespace {
constexpr double kPivotTol = 1e-9;
constexpr double kOptTol = 1e-7;
constexpr double kDegenerateTheta = 1e-12;
constexpr int kBlandAfter = 50;     // consecutive degenerate pivots
constexpr int kRefreshEvery = 100;  // iterations between re-inversions
}  // namespace

CoveringSimplex::CoveringSimplex(int n_rows) : m_(n_rows) {
    if (m_ <= 0) throw std::runtime_error("covering LP needs at least one row");
    binv_.assign(m_, std::vector<double>(m_, 0.0));
    for (int i = 0; i < m_; ++i) binv_[i][i] = 1.0;
    // Phase 1 starts from the all-artificial basis: B = I, x_B = 1.
    basis_.assign(m_, {ColKind::kArtificial, 0});
    for (int i = 0; i < m_; ++i) basis_[i].id = i;
    x_basic_.assign(m_, 1.0);
    artificial_basic_.assign(m_, 1);
    surplus_basic_.assign(m_, 0);
}

int CoveringSimplex::add_column(double cost, const std::vector<int>& covers) {
    costs_.push_back(cost);
    covers_.push_back(covers);
    structural_basic_.push_back(0);
    return static_cast<int>(costs_.size()) - 1;
}

void CoveringSimplex::refresh_inverse() {
    // Build [B | I] and invert the basis by Gauss-Jordan with partial
    // pivoting, then restore x_B = Binv * 1.
    std::vector<std::vector<double>> a(m_, std::vector<double>(2 * m_, 0.0));
    for (int i = 0; i < m_; ++i) {
        const ColRef& bc = basis_[i];
        if (bc.kind == ColKind::kStructural) {
            for (int r : covers_[bc.id]) a[r][i] = 1.0;
        } else {
            a[bc.id][i] = (bc.kind == ColKind::kSurplus) ? -1.0 : 1.0;
        }
        a[i][m_ + i] = 1.0;
    }
    for (int col = 0; col < m_; ++col) {
        int piv = col;
        for (int r = col + 1; r < m_; ++r) {
            if (std::fabs(a[r][col]) > std::fabs(a[piv][col])) piv = r;
        }
        if (std::fabs(a[piv][col]) < 1e-12) {
            throw std::runtime_error("simplex basis became singular");
        }
        if (piv != col) std::swap(a[piv], a[col]);
        const double d = a[col][col];
        for (int j = 0; j < 2 * m_; ++j) a[col][j] /= d;
        for (int r = 0; r < m_; ++r) {
            if (r == col) continue;
            const double f = a[r][col];
            if (f == 0.0) continue;
            for (int j = 0; j < 2 * m_; ++j) a[r][j] -= f * a[col][j];
        }
    }
    for (int i = 0; i < m_; ++i) {
        binv_[i].assign(a[i].begin() + m_, a[i].end());
        double sum = 0.0;
        for (int k = 0; k < m_; ++k) sum += binv_[i][k];
        x_basic_[i] = sum;  // b is the all-ones vector
    }
    since_refresh_ = 0;
}

std::vector<double> CoveringSimplex::compute_duals() const {
    std::vector<double> cb(m_, 0.0);
    for (int i = 0; i < m_; ++i) {
        const ColRef& bc = basis_[i];
        if (phase_ == 1) {
            cb[i] = (bc.kind == ColKind::kArtificial) ? 1.0 : 0.0;
        } else {
            cb[i] = (bc.kind == ColKind::kStructural) ? costs_[bc.id] : 0.0;
        }
    }
    // pi = Binv^T c_B.
    std::vector<double> pi(m_, 0.0);
    for (int i = 0; i < m_; ++i) {
        if (cb[i] == 0.0) continue;
        for (int k = 0; k < m_; ++k) pi[k] += binv_[i][k] * cb[i];
    }
    return pi;
}

std::vector<double> CoveringSimplex::direction(const ColRef& col) const {
    std::vector<double> a(m_, 0.0), d(m_, 0.0);
    if (col.kind == ColKind::kStructural) {
        for (int r : covers_[col.id]) a[r] = 1.0;
    } else {
        a[col.id] = (col.kind == ColKind::kSurplus) ? -1.0 : 1.0;
    }
    for (int i = 0; i < m_; ++i) {
        double sum = 0.0;
        for (int k = 0; k < m_; ++k) {
            if (a[k] != 0.0) sum += binv_[i][k] * a[k];
        }
        d[i] = sum;
    }
    return d;
}

void CoveringSimplex::pivot(int row, const ColRef& enter) {
    const std::vector<double> d = direction(enter);
    const double pivot_val = d[row];
    if (std::fabs(pivot_val) < kPivotTol) {
        throw std::runtime_error("simplex picked a degenerate pivot element");
    }
    // Product-form update of the explicit basis inverse.
    for (int j = 0; j < m_; ++j) binv_[row][j] /= pivot_val;
    for (int i = 0; i < m_; ++i) {
        if (i == row || d[i] == 0.0) continue;
        const double f = d[i];
        for (int j = 0; j < m_; ++j) binv_[i][j] -= f * binv_[row][j];
    }
    const double theta = x_basic_[row] / pivot_val;
    for (int i = 0; i < m_; ++i) x_basic_[i] -= theta * d[i];
    x_basic_[row] = theta;

    const ColRef leaving = basis_[row];
    if (leaving.kind == ColKind::kStructural) structural_basic_[leaving.id] = 0;
    else if (leaving.kind == ColKind::kSurplus) surplus_basic_[leaving.id] = 0;
    else artificial_basic_[leaving.id] = 0;

    basis_[row] = enter;
    if (enter.kind == ColKind::kStructural) structural_basic_[enter.id] = 1;
    else if (enter.kind == ColKind::kSurplus) surplus_basic_[enter.id] = 1;
    else artificial_basic_[enter.id] = 1;
}

bool CoveringSimplex::iterate(int phase) {
    const std::vector<double> pi = compute_duals();
    const bool bland = degenerate_streak_ >= kBlandAfter;

    ColRef enter{ColKind::kArtificial, -1};
    double best_rc = -kOptTol;
    // Structural columns: rc = c_j - pi . covers, with c_j = 0 in phase 1
    // (the phase-1 objective prices only the artificials).
    for (int col = 0; col < static_cast<int>(costs_.size()); ++col) {
        if (structural_basic_[col]) continue;
        double rc = (phase == 1) ? 0.0 : costs_[col];
        for (int r : covers_[col]) rc -= pi[r];
        if (rc < -kOptTol) {
            if (bland) {
                enter = {ColKind::kStructural, col};
                break;
            }
            if (rc < best_rc) {
                best_rc = rc;
                enter = {ColKind::kStructural, col};
            }
        }
    }
    // Surplus columns: rc = pi_i (they must stay priced out at optimality,
    // which is exactly the nonnegativity of the covering duals).
    if (enter.id < 0) {
        for (int i = 0; i < m_; ++i) {
            if (surplus_basic_[i]) continue;
            const double rc = pi[i];
            if (rc < -kOptTol) {
                if (bland) {
                    enter = {ColKind::kSurplus, i};
                    break;
                }
                if (rc < best_rc) {
                    best_rc = rc;
                    enter = {ColKind::kSurplus, i};
                }
            }
        }
    }
    if (enter.id < 0) return false;  // optimal for this phase

    // Ratio test; ties resolve to the smaller order_id for determinism.
    const std::vector<double> d = direction(enter);
    int leave = -1;
    double best_theta = 0.0;
    long long best_order = 0;
    for (int i = 0; i < m_; ++i) {
        if (d[i] <= kPivotTol) continue;
        const double theta = x_basic_[i] / d[i];
        if (theta < -1e-12) continue;  // numerical noise guard
        const long long order = order_id(basis_[i]);
        if (leave < 0 || theta < best_theta - 1e-12 ||
            (theta <= best_theta + 1e-12 && order < best_order)) {
            best_theta = theta;
            leave = i;
            best_order = order;
        }
    }
    if (leave < 0) throw std::runtime_error("simplex direction unbounded (should not happen)");

    pivot(leave, enter);
    if (best_theta <= kDegenerateTheta) {
        ++degenerate_streak_;
    } else {
        degenerate_streak_ = 0;
    }
    if (++since_refresh_ >= kRefreshEvery) refresh_inverse();
    return true;
}

RmpSolution CoveringSimplex::solve() {
    if (phase_ == 1) {
        while (iterate(1)) {
        }
        double artificial_sum = 0.0;
        for (int i = 0; i < m_; ++i) {
            if (basis_[i].kind == ColKind::kArtificial) artificial_sum += x_basic_[i];
        }
        if (artificial_sum > 1e-7) {
            throw std::runtime_error("master problem infeasible (no seed coverage)");
        }
        phase_ = 2;
        degenerate_streak_ = 0;
    }
    // Phase 2: original costs. Basic artificials sit at zero and may leave
    // through ordinary ratio tests; they never re-enter.
    while (iterate(2)) {
    }

    refresh_inverse();  // clean numerics before extracting the answer

    RmpSolution out;
    out.primal.assign(costs_.size(), 0.0);
    double objective = 0.0;
    for (int i = 0; i < m_; ++i) {
        if (basis_[i].kind == ColKind::kStructural) {
            const double v = std::max(0.0, x_basic_[i]);
            out.primal[basis_[i].id] = v;
            objective += costs_[basis_[i].id] * v;
        }
    }
    out.objective = objective;
    out.duals = compute_duals();
    return out;
}

}  // namespace bpvrptw
