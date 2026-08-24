"""Pluggable restricted-master-problem (RMP) LP backends.

The branch-and-price tree in :mod:`bpvrptw.branch_and_price` owns all
search logic; the solvers here are pure LP oracles for the master problem.
Both bundled backends keep ONE model object alive for the whole column
generation of a node and add pricing columns incrementally, so the simplex
warm start is retained between iterations (this replaces the legacy
pattern of deleting and rebuilding the entire model every iteration --
defect D4 in ``legacy/README.md``).

Master problem solved here (one coverage row per interior customer)::

    minimize   sum_p  cost_p * y_p
    subject to sum_p  a_{cp} * y_p >= 1    for every customer c
               y_p >= 0

Dual sign convention (identical in both backends): for ``>=`` rows in a
minimization the returned duals are nonnegative at optimality, and every
column satisfies ``reduced_cost = cost - sum(duals[c] for c in covers) >= 0``
within solver tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np

from ._util import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .instance import VRPTWInstance

_logger = get_logger(__name__)


class BackendUnavailableError(RuntimeError):
    """Raised when a requested LP backend cannot be used on this machine."""


@dataclass(frozen=True)
class RmpSolution:
    """One solve of the restricted master problem."""

    objective: float
    #: One dual per coverage row, ordered like ``instance.customers``.
    duals: np.ndarray
    #: One primal value per column currently in the model.
    primal: np.ndarray


@runtime_checkable
class RMPBackend(Protocol):
    """The minimal interface the column generator needs from an LP backend."""

    name: str

    def add_column(self, cost: float, covers: list[int]) -> int:
        """Append one column; ``covers`` are customer indices (1..n-2).

        Returns the column index of the newly added column.
        """
        ...

    def solve(self) -> RmpSolution:
        """Solve the current LP and return objective/duals/primals."""
        ...

    @property
    def n_columns(self) -> int:
        """Number of columns currently in the model."""
        ...

    def close(self) -> None:
        """Release solver resources."""
        ...


def _seed_lp_arrays(
    instance: VRPTWInstance, seed_columns: list[tuple[float, list[int]]]
) -> tuple[np.ndarray, int, dict[int, int], np.ndarray, np.ndarray, np.ndarray]:
    # (costs, n_rows, row_of_customer, starts, indices, values)
    """Build the arrays for the initial (seeded) RMP."""
    customers = list(instance.customers)
    row_of_customer = {c: i for i, c in enumerate(customers)}
    n_rows = len(customers)
    costs = np.array([cost for cost, _ in seed_columns], dtype=np.float64)
    starts = [0]
    indices: list[int] = []
    values: list[float] = []
    for _, covers in seed_columns:
        for c in covers:
            indices.append(row_of_customer[c])
            values.append(1.0)
        starts.append(len(indices))
    return (
        costs,
        n_rows,
        row_of_customer,
        np.array(starts, dtype=np.int32),
        np.array(indices, dtype=np.int32),
        np.array(values, dtype=np.float64),
    )


class HighsBackend:
    """Apache/MIT HiGHS backend -- the default, license-free oracle."""

    name = "highs"

    def __init__(
        self,
        instance: VRPTWInstance,
        seed_columns: list[tuple[float, list[int]]],
    ) -> None:
        import highspy

        self._inf = highspy.kHighsInf
        costs, n_rows, row_of_customer, starts, indices, values = _seed_lp_arrays(
            instance, seed_columns
        )
        if not seed_columns:
            raise ValueError("HighsBackend needs at least one seed column per build")
        self._row_of_customer = row_of_customer
        lp = highspy.HighsLp()
        lp.num_col_ = len(seed_columns)
        lp.num_row_ = n_rows
        lp.col_cost_ = costs
        lp.col_lower_ = np.zeros(len(seed_columns))
        lp.col_upper_ = np.full(len(seed_columns), self._inf)
        lp.row_lower_ = np.ones(n_rows)
        lp.row_upper_ = np.full(n_rows, self._inf)
        lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_ = starts
        lp.a_matrix_.index_ = indices
        lp.a_matrix_.value_ = values
        self._h = highspy.Highs()
        self._h.setOptionValue("output_flag", False)
        self._h.setOptionValue("threads", 1)  # determinism over speed
        status = self._h.passModel(lp)
        if status != highspy.HighsStatus.kOk:
            raise BackendUnavailableError(f"HiGHS rejected the seed model: {status}")

    def add_column(self, cost: float, covers: list[int]) -> int:
        rows = sorted(self._row_of_customer[c] for c in covers)
        num_nz = len(rows)
        idx = np.array(rows, dtype=np.int32)
        val = np.ones(num_nz)
        self._h.addCol(float(cost), 0.0, self._inf, num_nz, idx, val)
        return self._h.getNumCol() - 1

    def solve(self) -> RmpSolution:
        import highspy

        run_status = self._h.run()
        if run_status != highspy.HighsStatus.kOk:
            raise BackendUnavailableError(f"HiGHS run failed: {run_status}")
        model_status = self._h.getModelStatus()
        if model_status != highspy.HighsModelStatus.kOptimal:
            raise BackendUnavailableError(
                f"HiGHS status {self._h.modelStatusToString(model_status)} "
                "(master problem should never be infeasible: seed columns exist)"
            )
        solution = self._h.getSolution()
        return RmpSolution(
            objective=float(self._h.getObjectiveValue()),
            duals=np.array(solution.row_dual, dtype=np.float64),
            primal=np.array(solution.col_value, dtype=np.float64),
        )

    @property
    def n_columns(self) -> int:
        return int(self._h.getNumCol())

    def close(self) -> None:
        self._h.clear()


class GurobiBackend:
    """Optional gurobipy backend with identical semantics to HighsBackend."""

    name = "gurobi"

    def __init__(
        self,
        instance: VRPTWInstance,
        seed_columns: list[tuple[float, list[int]]],
    ) -> None:
        try:
            import gurobipy as gp
            from gurobipy import GRB
        except ImportError as exc:  # pragma: no cover - environment specific
            raise BackendUnavailableError(
                "gurobipy is not installed; install with: pip install bpvrptw[gurobi]"
            ) from exc

        self._gp = gp
        self._grb = GRB
        _, n_rows, row_of_customer, starts, indices, values = _seed_lp_arrays(
            instance, seed_columns
        )
        self._row_of_customer = row_of_customer
        try:
            self._model = gp.Model("bpvrptw-rmp")
        except gp.GurobiError as exc:  # pragma: no cover - no license
            raise BackendUnavailableError(
                "gurobipy could not create a Model (license problem?): "
                f"{exc}. Use lp_solver='highs' instead."
            ) from exc
        self._model.setParam("OutputFlag", 0)
        self._model.setParam("Seed", 0)

        constraints = [self._model.addConstr(gp.LinExpr() >= 1.0, name=f"cov_{c}")
                       for c in instance.customers]
        self._constraints = constraints
        self._vars: list[Any] = []
        for col_idx, (cost, covers) in enumerate(seed_columns):
            column = gp.Column(
                [1.0] * len(covers), [constraints[row_of_customer[c]] for c in covers]
            )
            var = self._model.addVar(lb=0.0, obj=float(cost), column=column,
                                     name=f"y{col_idx}")
            self._vars.append(var)
        self._model.update()

    def add_column(self, cost: float, covers: list[int]) -> int:
        column = self._gp.Column(
            [1.0] * len(covers),
            [self._constraints[self._row_of_customer[c]] for c in covers],
        )
        var = self._model.addVar(lb=0.0, obj=float(cost), column=column,
                                 name=f"y{len(self._vars)}")
        self._vars.append(var)
        self._model.update()
        return len(self._vars) - 1

    def solve(self) -> RmpSolution:
        self._model.optimize()
        if self._model.Status != self._grb.OPTIMAL:
            raise BackendUnavailableError(
                f"Gurobi status {self._model.Status} "
                "(master problem should never be infeasible: seed columns exist)"
            )
        duals = np.array([c.Pi for c in self._constraints], dtype=np.float64)
        primal = np.array([v.X for v in self._vars], dtype=np.float64)
        return RmpSolution(objective=float(self._model.ObjVal), duals=duals, primal=primal)

    @property
    def n_columns(self) -> int:
        return len(self._vars)

    def close(self) -> None:
        self._model.dispose()


def make_backend(
    name: str,
    instance: VRPTWInstance,
    seed_columns: list[tuple[float, list[int]]],
) -> RMPBackend:
    """Instantiate an RMP backend by name.

    Args:
        name: ``"highs"``, ``"gurobi"`` or ``"auto"``. Auto prefers Gurobi
            when importable AND able to create models, else falls back to
            HiGHS.
        instance: The instance being solved.
        seed_columns: ``(cost, covers)`` pairs forming the initial RMP.

    Returns:
        A ready-to-use backend.

    Raises:
        BackendUnavailableError: When an explicit backend cannot be used.
    """
    if name == "highs":
        return HighsBackend(instance, seed_columns)
    if name == "gurobi":
        return GurobiBackend(instance, seed_columns)
    if name == "auto":
        try:
            return GurobiBackend(instance, seed_columns)
        except BackendUnavailableError as exc:
            _logger.debug("gurobi unavailable (%s); falling back to highs", exc)
            return HighsBackend(instance, seed_columns)
    raise BackendUnavailableError(
        f"unknown lp_solver {name!r} (expected 'auto', 'highs' or 'gurobi')"
    )
