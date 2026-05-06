"""Compute the equilibrium state vector and RHS callable for a power system.

This function extracts the initialization logic that was previously inlined
inside :class:`pylectra.engine.loop.IntegrationLoop`.  By exposing it as a
standalone callable, small-signal analyzers (and other tools that only need
the equilibrium, not a full trajectory) can reuse it without constructing a
complete integration loop.

The returned :class:`Equilibrium` object holds:
  * ``rhs``    — callable ``f(t, y) -> dy/dt`` (the full nonlinear ODE)
  * ``y0``     — flat equilibrium state vector, shape ``(9 * ngen,)``
  * ``layout`` — :class:`pylectra.engine.state.StateLayout` (pack/unpack helpers)
  * ``network``— :class:`pylectra.engine.rhs.NetworkSolver` (augmented Y-bus)
  * ``pf_success`` — False if the power-flow solver did not converge
  * ``diagnostics`` — dict with ``ngen``, ``nbus``, ``freq``, wall time, etc.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np

from pylectra.core.idx import idx_bus, idx_gen
from pylectra.io.dyn_loaders import (
    loaddyn as Loaddyn,
    loadgen as Loadgen,
    loadexc as Loadexc,
    loadpss as Loadpss,
    loadgov as Loadgov,
)

from pylectra.network import machine_currents as MachineCurrents
from pylectra.core.freq import set_freq as _set_freq
from pylectra.engine.init_states import (
    generator_init as GeneratorInit,
    exciter_init as ExciterInit,
    governor_init as GovernorInit,
    pss_init as PSSInit,
)
from pylectra.engine.derivatives import (
    generator_step as Generator,
    exciter_step as Exciter,
    governor_step as Governor,
)

from .rhs import DynamicsRHS, NetworkSolver
from .state import StateLayout


@dataclass
class Equilibrium:
    """Result of a successful equilibrium computation."""

    rhs: DynamicsRHS
    y0: np.ndarray
    layout: StateLayout
    network: NetworkSolver
    pf_success: bool
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def compute_equilibrium(
    casefile_pf,
    casefile_dyn: str,
    *,
    pf_solver=None,
    pf_options: Optional[dict] = None,
    output: int = 0,
) -> Equilibrium:
    """Run power flow + state initialisation and return an Equilibrium.

    Parameters
    ----------
    casefile_pf :
        Power-flow case — a string name (e.g. ``"case39"``) or an already-
        loaded ``mpc`` dict (numpy arrays for bus/gen/branch).
    casefile_dyn :
        Dynamic case name (e.g. ``"case39dyn"``).
    pf_solver :
        A :class:`pylectra.interfaces.PowerFlowSolver` instance.  If ``None``
        the legacy Newton solver is used so the function is self-contained.
    pf_options :
        Extra kwargs forwarded to ``pf_solver.solve()``.
    output :
        Verbosity level (0 = silent).

    Returns
    -------
    Equilibrium
        If power flow fails, returns an ``Equilibrium`` with
        ``pf_success=False`` and ``rhs=None``, ``y0=None``.
    """
    tic = time.perf_counter()

    # ---- Load dynamic data ----------------------------------------
    freq, _stepsize, _stoptime = Loaddyn(casefile_dyn)
    _set_freq(freq)

    Pgen0 = Loadgen(casefile_dyn, 0)
    if Pgen0.shape[1] < 10:
        Pgen0 = np.hstack([Pgen0, np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
    Pgen0[:, 9] = Pgen0[:, 8]

    Pexc0 = Loadexc(casefile_dyn)
    Ppss0 = Loadpss(casefile_dyn)
    Pgov0 = Loadgov(casefile_dyn)

    genmodel = Pgen0[:, 0].astype(int)
    excmodel = Pgen0[:, 1].astype(int)
    pssmodel = Pgen0[:, 2].astype(int)
    govmodel = Pgen0[:, 3].astype(int)

    if np.any(pssmodel != 3):
        raise NotImplementedError(
            "compute_equilibrium supports PSS type 3 (no PSS) only; got "
            f"{np.unique(pssmodel).tolist()}."
        )

    # ---- Power flow -----------------------------------------------
    if pf_solver is not None:
        from pylectra.core.case import NetworkCase
        case = NetworkCase.load(casefile_pf)
        case = pf_solver.solve(case, pf_options or {})
        if not case.success:
            return Equilibrium(
                rhs=None, y0=None, layout=None, network=None,
                pf_success=False,
                diagnostics={"reason": "power flow did not converge",
                              "wall_time_sec": time.perf_counter() - tic},
            )
        mpc = case.mpc
        baseMVA = mpc["baseMVA"]
        bus = mpc["bus"].copy()
        gen = mpc["gen"].copy()
        branch = mpc["branch"].copy()
    else:
        # Fallback: use the native Newton solver via the registered plugin.
        from pylectra.core.case import NetworkCase
        from pylectra.powerflow.newton import NewtonPowerFlow
        case_local = (casefile_pf if isinstance(casefile_pf, NetworkCase)
                      else NetworkCase.load(casefile_pf))
        NewtonPowerFlow().solve(case_local, {"verbose": 0})
        if not case_local.success:
            return Equilibrium(
                rhs=None, y0=None, layout=None, network=None,
                pf_success=False,
                diagnostics={"reason": "power flow did not converge",
                              "wall_time_sec": time.perf_counter() - tic},
            )
        baseMVA = case_local.mpc["baseMVA"]
        bus = case_local.mpc["bus"]
        gen = case_local.mpc["gen"]
        branch = case_local.mpc["branch"]

    if output:
        print("> Power flow converged")

    # NewtonPowerFlow.solve already returns 0-based numbering; pf_solver
    # branch may also do so via its own contract — both code paths now agree.
    ib = idx_bus()
    ig = idx_gen()
    BUS_I = ib[4]; VM = ib[11]; VA = ib[12]
    GEN_BUS = ig[0]; GEN_STATUS = ig[7]

    U0 = bus[:, VM] * (
        np.cos(bus[:, VA] * np.pi / 180.0)
        + 1j * np.sin(bus[:, VA] * np.pi / 180.0)
    )
    U00 = U0.copy()

    on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
    gbus = gen[on, GEN_BUS].astype(int)
    ngen = gbus.size
    nbus = U0.size

    # ---- Augmented Y-bus ------------------------------------------
    if output:
        print("> Constructing augmented admittance matrix...")

    xd_tr = np.zeros(ngen)
    xd_tr[genmodel == 2] = Pgen0[genmodel == 2, 8]
    network = NetworkSolver(baseMVA, bus, branch, gbus, xd_tr, U00)

    # ---- Generator / Exciter / Governor initialisation -----------
    if output:
        print("> Calculating initial state...")

    Efd0, Xgen0 = GeneratorInit(Pgen0, U0[gbus], gen, baseMVA, genmodel)
    omega0 = Xgen0[:, 1]
    Id0, Iq0, Pe0 = MachineCurrents(Xgen0, Pgen0, U0[gbus], genmodel)
    Vgen0 = np.column_stack([Id0, Iq0, Pe0])

    Vexc0 = U0[gbus]
    Xexc0, Pexc0 = ExciterInit(Efd0, Xgen0, Pexc0, Vexc0, excmodel)
    _Xpss0, _Ppss0 = PSSInit(Ppss0, pssmodel)
    Vpss0 = np.zeros((ngen, 2))
    Pm0 = Pe0
    Xgov0, Pgov0 = GovernorInit(Pm0, Pgov0, omega0, govmodel)

    # ---- Steady-state check (tolerance matches legacy rundyn) ----
    Fgen0 = Generator(Xgen0, Xexc0, Xgov0, Pgen0, Vgen0, genmodel)
    Fexc0 = Exciter(Xexc0, Xgen0, Pexc0, Vexc0, Vpss0, excmodel)
    Fgov0 = Governor(Xgov0, Pgov0, omega0, govmodel)

    ss_err = max(float(np.sum(np.abs(Fgen0))),
                 float(np.sum(np.abs(Fexc0))),
                 float(np.sum(np.abs(Fgov0))))
    if ss_err > 1e-6:
        return Equilibrium(
            rhs=None, y0=None, layout=None, network=None,
            pf_success=False,
            diagnostics={"reason": f"steady-state check failed (err={ss_err:.2e})",
                         "wall_time_sec": time.perf_counter() - tic},
        )

    if output:
        print("> System in steady-state")

    # ---- Build RHS + state vector --------------------------------
    layout = StateLayout(ngen=ngen,
                         n_xgen=Xgen0.shape[1],
                         n_xexc=Xexc0.shape[1],
                         n_xgov=Xgov0.shape[1])

    rhs = DynamicsRHS(layout, network, Pgen0, Pexc0, Pgov0,
                      genmodel, excmodel, govmodel)

    y0 = layout.pack(Xgen0, Xexc0, Xgov0)

    return Equilibrium(
        rhs=rhs,
        y0=y0,
        layout=layout,
        network=network,
        pf_success=True,
        diagnostics={
            "ngen": int(ngen),
            "nbus": int(nbus),
            "freq": float(freq),
            "steady_state_error": ss_err,
            "wall_time_sec": time.perf_counter() - tic,
        },
    )
