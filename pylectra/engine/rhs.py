"""Right-hand side ``f(t, y)`` callable for the native ODE engine.

Encapsulates one network solve + one ``Generator/Exciter/Governor`` derivative
evaluation, in the same order as the legacy hand-coded solvers (but with
*Jacobi* updates: all derivatives evaluated at the same state ``y``, rather
than the *Gauss-Seidel* staggering of legacy ``ModifiedEuler``).
"""
from __future__ import annotations

import numpy as np

from pylectra.network import (
    aug_ybus as AugYbus,
    machine_currents as MachineCurrents,
    solve_network as SolveNetwork,
)
from pylectra.engine.derivatives import (
    generator_step as Generator,
    exciter_step as Exciter,
    governor_step as Governor,
)

from .state import StateLayout


class NetworkSolver:
    """Wraps the augmented Y-bus + LU factorisation; rebuildable on events."""

    __slots__ = ("baseMVA", "bus", "branch", "gbus", "xd_tr", "U_init",
                 "Ly", "Uy", "Py")

    def __init__(self, baseMVA: float, bus: np.ndarray, branch: np.ndarray,
                 gbus: np.ndarray, xd_tr: np.ndarray, U_init: np.ndarray):
        self.baseMVA = float(baseMVA)
        self.bus = bus
        self.branch = branch
        self.gbus = np.asarray(gbus, dtype=int)
        self.xd_tr = np.asarray(xd_tr, dtype=float)
        self.U_init = np.asarray(U_init, dtype=complex)
        self.rebuild()

    def rebuild(self) -> None:
        from pylectra.core.idx import idx_bus
        ib = idx_bus()
        PD, QD = ib[6], ib[7]
        Pl = self.bus[:, PD] / self.baseMVA
        Ql = self.bus[:, QD] / self.baseMVA
        self.Ly, self.Uy, self.Py = AugYbus(
            self.baseMVA, self.bus, self.branch, self.xd_tr,
            self.gbus, Pl, Ql, self.U_init)

    def solve_for_U(self, Xgen: np.ndarray, Pgen: np.ndarray,
                    genmodel: np.ndarray) -> np.ndarray:
        return SolveNetwork(Xgen, Pgen, self.Ly, self.Uy, self.Py,
                            self.gbus, genmodel)


class DynamicsRHS:
    """Callable ``f(t, y) -> dy/dt`` for the full power-system dynamics."""

    __slots__ = ("layout", "network", "Pgen", "Pexc", "Pgov",
                 "genmodel", "excmodel", "govmodel", "_zero_vpss",
                 "_last_U", "_last_Vgen", "_last_t")

    def __init__(self, layout: StateLayout, network: NetworkSolver,
                 Pgen: np.ndarray, Pexc: np.ndarray, Pgov: np.ndarray,
                 genmodel: np.ndarray, excmodel: np.ndarray,
                 govmodel: np.ndarray):
        self.layout = layout
        self.network = network
        self.Pgen = Pgen
        self.Pexc = Pexc
        self.Pgov = Pgov
        self.genmodel = np.asarray(genmodel, dtype=int)
        self.excmodel = np.asarray(excmodel, dtype=int)
        self.govmodel = np.asarray(govmodel, dtype=int)
        # Vpss is always zero for PSS type-3 (the only supported type here).
        self._zero_vpss = np.zeros((layout.ngen, 2), dtype=float)
        # Cache the most recent network solve so the loop can read it back
        # after a step — the loop saves U and Pe in the result arrays.
        self._last_U: np.ndarray | None = None
        self._last_Vgen: np.ndarray | None = None
        self._last_t: float = -np.inf

    def __call__(self, t: float, y: np.ndarray) -> np.ndarray:
        Xgen, Xexc, Xgov = self.layout.unpack(y)
        U = self.network.solve_for_U(Xgen, self.Pgen, self.genmodel)
        Vexc = U[self.network.gbus]
        Id, Iq, Pe = MachineCurrents(Xgen, self.Pgen, U[self.network.gbus],
                                     self.genmodel)
        Vgen = np.column_stack([Id, Iq, Pe])
        Vgov = Xgen[:, 1].copy()  # omega

        dXexc = Exciter(Xexc, Xgen, self.Pexc, Vexc, self._zero_vpss,
                        self.excmodel)
        dXgov = Governor(Xgov, self.Pgov, Vgov, self.govmodel)
        dXgen = Generator(Xgen, Xexc, Xgov, self.Pgen, Vgen, self.genmodel)

        # Cache for state-snapshot writers in the loop.
        self._last_U = U
        self._last_Vgen = Vgen
        self._last_t = float(t)

        return self.layout.pack(dXgen, dXexc, dXgov)
