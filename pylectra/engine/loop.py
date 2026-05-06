"""Integration driver — leg-by-leg adaptive ODE solve with structural events.

Mirrors the output format of legacy :func:`rundyn.rundyn` (same dict keys)
so :class:`pylectra.runners.single.SingleRunner` can consume either path.

The loop itself is solver-agnostic: it asks a *factory* callable for a fresh
:class:`scipy.integrate.OdeSolver` per leg, then drives ``solver.step()``
until ``solver.status != 'running'``.  This gives users access to all of
scipy's adaptive solvers (RK45, DOP853, LSODA, BDF, Radau) with proper
structural-event handling.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from pylectra.core.idx import idx_bus, idx_brch, idx_gen
from pylectra.core.case import NetworkCase
from pylectra.powerflow.newton import NewtonPowerFlow
from pylectra.io.dyn_loaders import (
    loaddyn as Loaddyn,
    loadgen as Loadgen,
    loadexc as Loadexc,
    loadpss as Loadpss,
    loadgov as Loadgov,
    loadevents as Loadevents,
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

# A solver factory is a callable
#     factory(rhs, t0, y0, t_bound, **opts) -> scipy.integrate.OdeSolver
SolverFactory = Callable[..., Any]


@dataclass
class IntegrationResult:
    """Mirror the legacy ``rundyn`` return dict so SingleRunner is agnostic."""
    Time: np.ndarray
    Voltages: np.ndarray
    Efds: np.ndarray
    Angles: np.ndarray
    Speeds: np.ndarray
    Eq_trs: np.ndarray
    Ed_trs: np.ndarray
    Tes: np.ndarray
    TM: np.ndarray
    Vss: np.ndarray
    Stepsize: np.ndarray
    Errest: np.ndarray
    simulationtime: float
    success: bool = True
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "Time": self.Time, "Voltages": self.Voltages, "Efds": self.Efds,
            "Angles": self.Angles, "Speeds": self.Speeds,
            "Eq_trs": self.Eq_trs, "Ed_trs": self.Ed_trs,
            "Tes": self.Tes, "TM": self.TM, "Vss": self.Vss,
            "Stepsize": self.Stepsize, "Errest": self.Errest,
            "simulationtime": self.simulationtime,
        }


def _failed_result(reason: str, n_bus: int, n_gen: int,
                   simulationtime: float) -> IntegrationResult:
    """Build a 1-row failed result so SingleRunner can downstream gracefully."""
    return IntegrationResult(
        Time=np.zeros(0),
        Voltages=np.zeros((0, n_bus), dtype=complex),
        Efds=np.zeros((0, n_gen)),
        Angles=np.zeros((0, n_gen)),
        Speeds=np.zeros((0, n_gen)),
        Eq_trs=np.zeros((0, n_gen)),
        Ed_trs=np.zeros((0, n_gen)),
        Tes=np.zeros((0, n_gen)),
        TM=np.zeros((0, n_gen)),
        Vss=np.zeros((0, n_gen)),
        Stepsize=np.zeros(0),
        Errest=np.zeros(0),
        simulationtime=simulationtime,
        success=False,
        message=reason,
    )


class IntegrationLoop:
    """Drive a scipy ``OdeSolver`` through a power-system transient.

    Parameters
    ----------
    casefile_pf, casefile_dyn, casefile_ev :
        Same conventions as legacy :func:`rundyn.rundyn` — string names or
        already-loaded dicts (Loadcase/Loaddyn/Loadevents accept both).
    solver_factory :
        Callable returning a fresh :class:`scipy.integrate.OdeSolver` per
        leg.  See :mod:`pylectra.solvers.scipy_solvers`.
    output, plot :
        Forwarded for parity with rundyn (``plot`` ignored by this engine —
        SingleRunner handles plotting separately).
    t0 :
        Pre-event simulation start (default ``-0.02``, matches rundyn).
    """

    def __init__(self,
                 casefile_pf,
                 casefile_dyn,
                 casefile_ev,
                 solver_factory: SolverFactory,
                 solver_options: Optional[dict] = None,
                 t0: float = -0.02,
                 output: int = 0):
        self.casefile_pf = casefile_pf
        self.casefile_dyn = casefile_dyn
        self.casefile_ev = casefile_ev
        self.solver_factory = solver_factory
        self.solver_options = solver_options or {}
        self.t0 = float(t0)
        self.output = int(output)

    # ---- public API ------------------------------------------------------

    def run(self) -> IntegrationResult:
        tic = time.time()

        # ---------------- Load data ----------------
        if self.output:
            print('> Loading dynamic simulation data...')
        freq, stepsize, stoptime = Loaddyn(self.casefile_dyn)
        _set_freq(freq)

        Pgen0 = Loadgen(self.casefile_dyn, 0)
        if Pgen0.shape[1] < 10:
            Pgen0 = np.hstack([Pgen0, np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
        Pgen0[:, 9] = Pgen0[:, 8]

        Pexc0 = Loadexc(self.casefile_dyn)
        Ppss0 = Loadpss(self.casefile_dyn)
        Pgov0 = Loadgov(self.casefile_dyn)

        if self.casefile_ev is not None and self.casefile_ev != '':
            event, buschange, linechange = Loadevents(self.casefile_ev)
        else:
            event = np.empty((0, 2))
            buschange = np.empty((0, 4))
            linechange = np.empty((0, 4))

        genmodel = Pgen0[:, 0].astype(int)
        excmodel = Pgen0[:, 1].astype(int)
        pssmodel = Pgen0[:, 2].astype(int)
        govmodel = Pgen0[:, 3].astype(int)

        # PSS-type validation (engine supports type 3 only).
        if np.any(pssmodel != 3):
            raise NotImplementedError(
                "Native engine supports PSS type 3 (no PSS) only; got "
                f"{np.unique(pssmodel).tolist()}.  Use a legacy solver "
                "(modified_euler / runge_kutta / rkf / rkhh) for PSS dynamics."
            )

        # ---------------- Power flow ----------------
        case = (self.casefile_pf if isinstance(self.casefile_pf, NetworkCase)
                else NetworkCase.load(self.casefile_pf))
        NewtonPowerFlow().solve(case, {"verbose": 0})
        success = case.success
        if not success:
            return _failed_result('power flow did not converge',
                                  n_bus=0, n_gen=0,
                                  simulationtime=time.time() - tic)
        if self.output:
            print('> Power flow converged')

        baseMVA = case.mpc["baseMVA"]
        bus = case.mpc["bus"]
        gen = case.mpc["gen"]
        branch = case.mpc["branch"]

        ib = idx_bus(); ig = idx_gen(); ibr = idx_brch()
        BUS_I = ib[4]; PD = ib[6]; QD = ib[7]; VM = ib[11]; VA = ib[12]
        F_BUS = ibr[0]; T_BUS = ibr[1]
        GEN_BUS = ig[0]; GEN_STATUS = ig[7]
        # NewtonPowerFlow.solve already converts to 0-based numbering.

        U0 = bus[:, VM] * (np.cos(bus[:, VA] * np.pi / 180.0)
                           + 1j * np.sin(bus[:, VA] * np.pi / 180.0))
        U00 = U0.copy()

        on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
        gbus = gen[on, GEN_BUS].astype(int)
        ngen = gbus.size
        nbus = U0.size

        # ---------------- AugYbus + initial state ----------------
        if self.output:
            print('> Constructing augmented admittance matrix...')

        xd_tr = np.zeros(ngen)
        xd_tr[genmodel == 2] = Pgen0[genmodel == 2, 8]

        network = NetworkSolver(baseMVA, bus, branch, gbus, xd_tr, U00)

        if self.output:
            print('> Calculating initial state...')
        Efd0, Xgen0 = GeneratorInit(Pgen0, U0[gbus], gen, baseMVA, genmodel)
        omega0 = Xgen0[:, 1]
        Id0, Iq0, Pe0 = MachineCurrents(Xgen0, Pgen0, U0[gbus], genmodel)
        Vgen0 = np.column_stack([Id0, Iq0, Pe0])

        Vexc0 = U0[gbus]
        Xexc0, Pexc0 = ExciterInit(Efd0, Xgen0, Pexc0, Vexc0, excmodel)
        Xpss0, Ppss0 = PSSInit(Ppss0, pssmodel)
        Vpss0 = np.zeros((ngen, 2))
        Pm0 = Pe0
        Xgov0, Pgov0 = GovernorInit(Pm0, Pgov0, omega0, govmodel)
        Vgov0 = omega0

        # Steady-state checks (same tolerances as legacy rundyn).
        Fexc0 = Exciter(Xexc0, Xgen0, Pexc0, Vexc0, Vpss0, excmodel)
        Fgov0 = Governor(Xgov0, Pgov0, Vgov0, govmodel)
        Fgen0 = Generator(Xgen0, Xexc0, Xgov0, Pgen0, Vgen0, genmodel)
        if np.sum(np.abs(Fgen0)) > 1e-6:
            return _failed_result('generator not in steady state',
                                  nbus, ngen, time.time() - tic)
        if np.sum(np.abs(Fexc0)) > 1e-6:
            return _failed_result('exciter not in steady state',
                                  nbus, ngen, time.time() - tic)
        if np.sum(np.abs(Fgov0)) > 1e-6:
            return _failed_result('governor not in steady state',
                                  nbus, ngen, time.time() - tic)
        if self.output:
            print('> System in steady-state')

        # ---------------- Set up RHS + state ----------------
        layout = StateLayout(ngen=ngen,
                             n_xgen=Xgen0.shape[1],
                             n_xexc=Xexc0.shape[1],
                             n_xgov=Xgov0.shape[1])

        rhs = DynamicsRHS(layout, network, Pgen0, Pexc0, Pgov0,
                          genmodel, excmodel, govmodel)

        y0 = layout.pack(Xgen0, Xexc0, Xgov0)
        t = self.t0

        # Build event time list.
        n_events = event.shape[0] if event.size else 0
        event_times = (event[:, 0].astype(float) if n_events else np.empty(0))

        # Pre-allocate output buffers (chunked, like rundyn).
        chunk = 5000
        Time = np.zeros(chunk); Time[0] = t
        Stepsize = np.zeros(chunk); Stepsize[0] = stepsize
        Errest = np.zeros(chunk)
        Voltages = np.zeros((chunk, nbus), dtype=complex); Voltages[0, :] = U0
        Angles = np.zeros((chunk, ngen)); Angles[0, :] = Xgen0[:, 0] * 180.0 / np.pi
        Speeds = np.zeros((chunk, ngen)); Speeds[0, :] = Xgen0[:, 1] / (2.0 * np.pi * freq)
        Eq_trs = np.zeros((chunk, ngen)); Eq_trs[0, :] = Xgen0[:, 2]
        Ed_trs = np.zeros((chunk, ngen)); Ed_trs[0, :] = Xgen0[:, 3]
        Efds = np.zeros((chunk, ngen)); Efds[0, :] = np.asarray(Efd0).ravel()
        Vss = np.zeros((chunk, ngen))
        TM = np.zeros((chunk, ngen)); TM[0, :] = np.asarray(Pm0).ravel()
        Tes = np.zeros((chunk, ngen)); Tes[0, :] = Pe0

        idx = 0  # last written row

        def _ensure(extra: int) -> None:
            nonlocal Time, Stepsize, Errest, Voltages, Angles, Speeds
            nonlocal Eq_trs, Ed_trs, Efds, Vss, TM, Tes
            need = idx + extra + 1
            if need <= Time.shape[0]:
                return
            grow = max(chunk, need - Time.shape[0])
            def _g1(a): return np.concatenate([a, np.zeros(grow)])
            def _g2(a): return np.vstack([a, np.zeros((grow, a.shape[1]))])
            def _g2c(a): return np.vstack([a, np.zeros((grow, a.shape[1]), dtype=complex)])
            Time = _g1(Time); Stepsize = _g1(Stepsize); Errest = _g1(Errest)
            Voltages = _g2c(Voltages)
            Angles = _g2(Angles); Speeds = _g2(Speeds)
            Eq_trs = _g2(Eq_trs); Ed_trs = _g2(Ed_trs)
            Efds = _g2(Efds); Vss = _g2(Vss); TM = _g2(TM); Tes = _g2(Tes)

        def _save_snapshot(t_val: float, step: float, y_vec: np.ndarray) -> None:
            """Append one row to the result buffers."""
            nonlocal idx
            idx += 1
            _ensure(0)
            Xg, Xe, Xv = layout.unpack(y_vec)
            # If RHS hasn't been evaluated at this exact y, recompute U/Vgen.
            if rhs._last_U is None or rhs._last_t != t_val:
                rhs(t_val, y_vec)
            U_now = rhs._last_U
            Vgen_now = rhs._last_Vgen
            Time[idx] = t_val
            Stepsize[idx] = step
            Voltages[idx, :] = U_now
            Angles[idx, :] = Xg[:, 0] * 180.0 / np.pi
            Speeds[idx, :] = Xg[:, 1] / (2.0 * np.pi * freq)
            Eq_trs[idx, :] = Xg[:, 2]
            Ed_trs[idx, :] = Xg[:, 3]
            Efds[idx, :] = Xe[:, 0]
            TM[idx, :] = Xv[:, 0]
            Tes[idx, :] = Vgen_now[:, 2]

        # ---------------- Main leg-by-leg integration ----------------
        if self.output:
            print('> Running dynamic simulation...')

        # Build leg boundaries: t0, then each unique event time (in order),
        # then stoptime.  Drop events <= t0 (they would never fire).
        leg_bounds = [t]
        for et_ in event_times:
            if et_ > t and (not leg_bounds or et_ > leg_bounds[-1] + 1e-15):
                leg_bounds.append(float(et_))
        if leg_bounds[-1] < stoptime:
            leg_bounds.append(float(stoptime))
        else:
            leg_bounds[-1] = float(stoptime)

        ev = 0  # event-row pointer
        y = y0
        for li in range(len(leg_bounds) - 1):
            t_start = leg_bounds[li]
            t_end = leg_bounds[li + 1]
            if t_end <= t_start:
                continue

            stepper = self.solver_factory(rhs, t_start, y, t_end,
                                          **self.solver_options)
            while True:
                msg = stepper.step()
                if stepper.status == 'failed':
                    n = idx + 1
                    return IntegrationResult(
                        Time=Time[:n], Voltages=Voltages[:n], Efds=Efds[:n],
                        Angles=Angles[:n], Speeds=Speeds[:n],
                        Eq_trs=Eq_trs[:n], Ed_trs=Ed_trs[:n], Tes=Tes[:n],
                        TM=TM[:n], Vss=Vss[:n],
                        Stepsize=Stepsize[:n], Errest=Errest[:n],
                        simulationtime=time.time() - tic,
                        success=False,
                        message=f'integrator failed: {msg or "no further info"}',
                    )
                _save_snapshot(stepper.t, stepper.step_size, stepper.y)
                if stepper.status == 'finished':
                    y = stepper.y
                    break

            # ---------- apply events scheduled at exactly t_end ----------
            applied_any = False
            while ev < n_events and abs(event_times[ev] - t_end) < 1e-12:
                etype = int(event[ev, 1])
                if etype == 1:
                    bus[int(buschange[ev, 1]) - 1, int(buschange[ev, 2]) - 1] = buschange[ev, 3]
                elif etype == 2:
                    branch[int(linechange[ev, 1]) - 1, int(linechange[ev, 2]) - 1] = linechange[ev, 3]
                ev += 1
                applied_any = True

            if applied_any:
                # Rebuild AugYbus + re-solve network at the new topology.
                network.rebuild()
                # Force a re-evaluation; this also caches the new U/Vgen.
                rhs(t_end, y)
                # Save the t+ snapshot (matches legacy "two rows for one t").
                _save_snapshot(t_end, 0.0, y)

        n = idx + 1
        simulationtime = time.time() - tic
        if self.output:
            print(f'> Simulation completed in {simulationtime:5.2f} seconds')

        return IntegrationResult(
            Time=Time[:n], Voltages=Voltages[:n], Efds=Efds[:n],
            Angles=Angles[:n], Speeds=Speeds[:n],
            Eq_trs=Eq_trs[:n], Ed_trs=Ed_trs[:n], Tes=Tes[:n],
            TM=TM[:n], Vss=Vss[:n], Stepsize=Stepsize[:n], Errest=Errest[:n],
            simulationtime=simulationtime, success=True,
        )
