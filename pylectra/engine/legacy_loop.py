"""Native ``rundyn`` driver — power-system dynamic-simulation loop.

Faithful port of ``pylectra/_legacy/rundyn.py`` to native primitives:

* power flow      — :class:`pylectra.powerflow.newton.NewtonPowerFlow`
* data loaders    — :mod:`pylectra.io.dyn_loaders`
* init helpers    — :mod:`pylectra.engine.init_states`
* network math    — :mod:`pylectra.network`
* step functions  — :mod:`pylectra.engine.derivatives`
* steppers        — :mod:`pylectra.engine.legacy_solvers`
* frequency state — :func:`pylectra.core.freq.set_freq`

Bit-identical to the legacy ``rundyn`` on the supported solver methods
(1 = ModifiedEuler, 2 = RungeKutta, 3 = RKF, 4 = RKHH); validated by the
end-to-end golden tests (``tests/integration/test_batch_golden.py`` and
``tests/integration/test_cct_golden.py``).
"""
from __future__ import annotations

import time

import numpy as np

from pylectra.core.idx import idx_bus, idx_brch, idx_gen
from pylectra.core.freq import set_freq
from pylectra.core.case import NetworkCase
from pylectra.io.dyn_loaders import (
    loaddyn, loadgen, loadexc, loadgov, loadpss, loadevents,
)
from pylectra.powerflow.newton import NewtonPowerFlow
from pylectra.network import aug_ybus, machine_currents, solve_network
from pylectra.engine.init_states import (
    generator_init, exciter_init, governor_init, pss_init,
)
from pylectra.engine.derivatives import generator_step, exciter_step, governor_step
from pylectra.engine.legacy_solvers import (
    modified_euler_step, runge_kutta_step, rkf_step, rkhh_step,
)


def default_mdopt() -> np.ndarray:
    """Native replacement for legacy ``Mdoption()`` — same 6-element default vector."""
    return np.array([
        1.0,    # method (1=ME, 2=RK4, 3=RKF, 4=RKHH)
        1e-4,   # tol
        1e-3,   # minstepsize
        1e2,    # maxstepsize
        1.0,    # output (verbose)
        1.0,    # plots
    ])


def _grow(arr: np.ndarray, extra: int) -> np.ndarray:
    if arr.ndim == 1:
        return np.concatenate([arr, np.zeros(extra)])
    return np.vstack([arr, np.zeros((extra, arr.shape[1]))])


def rundyn(casefile_pf, casefile_dyn, casefile_ev, mdopt=None,
           plot: bool = True, output=None) -> dict | None:
    """Run a transient dynamic simulation.

    Mirrors the legacy ``rundyn`` API and return-dict shape exactly. The
    ``plot`` argument is accepted for backwards compatibility but has no
    effect — plotting is now handled by ``SingleRunner`` post-hoc.
    """
    tic = time.time()

    (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM,
     VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN) = idx_bus()
    (F_BUS, T_BUS, *_rest_brch) = idx_brch()
    (GEN_BUS, _PG, _QG, _QMAX, _QMIN, _VG, _MBASE, GEN_STATUS, *_rest_g) = idx_gen()

    if mdopt is None:
        mdopt = default_mdopt()
    method = int(mdopt[0])
    tol = float(mdopt[1])
    minstepsize = float(mdopt[2])
    maxstepsize = float(mdopt[3])
    if output is None:
        output = int(mdopt[4])
    else:
        output = int(output)

    if output:
        print('> Loading dynamic simulation data...')
    freq, stepsize, stoptime = loaddyn(casefile_dyn)
    set_freq(freq)

    Pgen0 = loadgen(casefile_dyn, output)
    if Pgen0.shape[1] < 10:
        Pgen0 = np.hstack([Pgen0, np.zeros((Pgen0.shape[0], 10 - Pgen0.shape[1]))])
    Pgen0[:, 9] = Pgen0[:, 8]

    Pexc0 = loadexc(casefile_dyn)
    Ppss0 = loadpss(casefile_dyn)
    Pgov0 = loadgov(casefile_dyn)

    if casefile_ev is not None and casefile_ev != '':
        event, buschange, linechange = loadevents(casefile_ev)
    else:
        event = np.empty((0, 2))
        buschange = np.empty((0, 4))
        linechange = np.empty((0, 4))

    genmodel = Pgen0[:, 0].astype(int)
    excmodel = Pgen0[:, 1].astype(int)
    pssmodel = Pgen0[:, 2].astype(int)
    govmodel = Pgen0[:, 3].astype(int)

    # -------- Power flow (native NewtonPowerFlow plugin) --------
    case = (casefile_pf if isinstance(casefile_pf, NetworkCase)
            else NetworkCase.load(casefile_pf))
    NewtonPowerFlow().solve(case, {"verbose": 0})
    if not case.success:
        print('> Error: Power flow did not converge. Exiting...')
        return None
    if output:
        print('> Power flow converged')

    baseMVA = case.mpc["baseMVA"]
    bus = case.mpc["bus"]
    gen = case.mpc["gen"]
    branch = case.mpc["branch"]
    # NewtonPowerFlow.solve already returns 0-based numbering — no shift here.

    U0 = bus[:, VM] * (np.cos(bus[:, VA] * np.pi / 180.0)
                       + 1j * np.sin(bus[:, VA] * np.pi / 180.0))
    U00 = U0.copy()

    on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
    gbus = gen[on, GEN_BUS].astype(int)
    ngen = gbus.size
    nbus = U0.size

    if output:
        print('> Constructing augmented admittance matrix...')
    Pl = bus[:, PD] / baseMVA
    Ql = bus[:, QD] / baseMVA

    xd_tr = np.zeros(ngen)
    is_t2 = (genmodel == 2)
    xd_tr[is_t2] = Pgen0[is_t2, 8]

    Ly, Uy, Py = aug_ybus(baseMVA, bus, branch, xd_tr, gbus, Pl, Ql, U0)

    if output:
        print('> Calculating initial state...')
    Efd0, Xgen0 = generator_init(Pgen0, U0[gbus], gen, baseMVA, genmodel)
    omega0 = Xgen0[:, 1]
    Id0, Iq0, Pe0 = machine_currents(Xgen0, Pgen0, U0[gbus], genmodel)
    Vgen0 = np.column_stack([Id0, Iq0, Pe0])

    Vexc0 = U0[gbus]
    Xexc0, Pexc0 = exciter_init(Efd0, Xgen0, Pexc0, Vexc0, excmodel)

    Xpss0, Ppss0 = pss_init(Ppss0, pssmodel)
    Vpss0 = np.zeros((ngen, 2))

    Pm0 = Pe0
    Xgov0, Pgov0 = governor_init(Pm0, Pgov0, omega0, govmodel)
    Vgov0 = omega0

    # Steady-state checks (PSS step is identically zero for type 3 — skip).
    Fexc0 = exciter_step(Xexc0, Xgen0, Pexc0, Vexc0, Vpss0, excmodel)
    Fgov0 = governor_step(Xgov0, Pgov0, Vgov0, govmodel)
    Fgen0 = generator_step(Xgen0, Xexc0, Xgov0, Pgen0, Vgen0, genmodel)

    if np.sum(np.abs(Fgen0)) > 1e-6:
        print('> Error: Generator not in steady-state\n> Exiting...')
        return None
    if np.sum(np.abs(Fexc0)) > 1e-6:
        print('> Error: Exciter not in steady-state\n> Exiting...')
        return None
    if np.sum(np.abs(Fgov0)) > 1e-6:
        print('> Error: Governor not in steady-state\n> Exiting...')
        return None
    if output:
        print('> System in steady-state')

    # -------- Main integration loop --------
    t = -0.02   # 0.02 s of pre-event simulation
    errest = 0.0
    failed = 0
    eulerfailed = 0

    if method in (3, 4):
        stepsize = minstepsize

    ev = 0
    eventhappened = False
    i = -1
    chunk = 5000

    Time = np.zeros(chunk); Time[0] = t
    Errest = np.zeros(chunk); Errest[0] = errest
    Stepsize = np.zeros(chunk); Stepsize[0] = stepsize
    Tes = np.zeros((chunk, ngen)); Tes[0, :] = Pe0

    Voltages = np.zeros((chunk, nbus), dtype=complex); Voltages[0, :] = U0

    Angles = np.zeros((chunk, ngen)); Angles[0, :] = Xgen0[:, 0] * 180.0 / np.pi
    Speeds = np.zeros((chunk, ngen)); Speeds[0, :] = Xgen0[:, 1] / (2.0 * np.pi * freq)
    Eq_trs = np.zeros((chunk, ngen)); Eq_trs[0, :] = Xgen0[:, 2]
    Ed_trs = np.zeros((chunk, ngen)); Ed_trs[0, :] = Xgen0[:, 3]

    Efds = np.zeros((chunk, ngen)); Efds[0, :] = np.asarray(Efd0).ravel()
    Vss = np.zeros((chunk, ngen)); Vss[0, :] = Vpss0[:, 0]
    TM = np.zeros((chunk, ngen)); TM[0, :] = np.asarray(Pm0).ravel()

    if output:
        print('> Running dynamic simulation...')

    Pgen = Pgen0; Pexc = Pexc0; Ppss = Ppss0; Pgov = Pgov0

    while t < stoptime + stepsize:
        i += 1

        if method == 1:
            (Xgen0, Pgen, Vgen0, Xpss0, Ppss, Vpss0, Xexc0, Pexc, Vexc0,
             Xgov0, Pgov, Vgov0, U0, t, newstepsize) = modified_euler_step(
                t, Xgen0, Pgen, Vgen0, Xpss0, Ppss, Vpss0,
                Xexc0, Pexc, Vexc0, Xgov0, Pgov, Vgov0,
                Ly, Uy, Py, gbus, genmodel, pssmodel, excmodel, govmodel,
                stepsize, U0)
        elif method == 2:
            (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
             Xgov0, Pgov, Vgov0, U0, t, newstepsize) = runge_kutta_step(
                t, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                Xgov0, Pgov, Vgov0, Ly, Uy, Py, gbus,
                genmodel, excmodel, govmodel, stepsize)
        elif method == 3:
            (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
             Xgov0, Pgov, Vgov0, U0, errest, failed, t, newstepsize) = \
                rkf_step(
                    t, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                    Xgov0, Pgov, Vgov0, U0, Ly, Uy, Py, gbus,
                    genmodel, excmodel, govmodel, tol, maxstepsize, stepsize)
        elif method == 4:
            (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
             Xgov0, Pgov, Vgov0, U0, errest, failed, t, newstepsize) = \
                rkhh_step(
                    t, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                    Xgov0, Pgov, Vgov0, U0, Ly, Uy, Py, gbus,
                    genmodel, excmodel, govmodel, tol, maxstepsize, stepsize)
        else:
            raise NotImplementedError(f'rundyn: method {method} not implemented')

        if eulerfailed:
            print('> Error: No solution found. Exiting...')
            return None

        if failed:
            t = t - stepsize

        if t + newstepsize > stoptime:
            newstepsize = stoptime - t
        elif stepsize < minstepsize:
            print('> Error: No solution found with minimum step size. Exiting...')
            return None

        if i >= Time.shape[0]:
            Time = _grow(Time, chunk)
            Errest = _grow(Errest, chunk)
            Stepsize = _grow(Stepsize, chunk)
            Voltages = np.vstack([Voltages, np.zeros((chunk, nbus), dtype=complex)])
            Efds = _grow(Efds, chunk); TM = _grow(TM, chunk); Tes = _grow(Tes, chunk)
            Angles = _grow(Angles, chunk); Speeds = _grow(Speeds, chunk)
            Eq_trs = _grow(Eq_trs, chunk); Ed_trs = _grow(Ed_trs, chunk)
            Vss = _grow(Vss, chunk)

        Stepsize[i] = stepsize
        Errest[i] = errest
        Time[i] = t
        Voltages[i, :] = U0
        Efds[i, :] = Xexc0[:, 0]
        Vss[i, :] = Vpss0[:, 0]
        TM[i, :] = Xgov0[:, 0]
        Angles[i, :] = Xgen0[:, 0] * 180.0 / np.pi
        Speeds[i, :] = Xgen0[:, 1] / (2.0 * np.pi * freq)
        Eq_trs[i, :] = Xgen0[:, 2]
        Ed_trs[i, :] = Xgen0[:, 3]
        Tes[i, :] = Vgen0[:, 2]

        # Events
        if event.shape[0] > 0 and ev < event.shape[0]:
            for _k in range(ev, event.shape[0]):
                if abs(t - event[ev, 0]) > 10.0 * np.finfo(float).eps or ev >= event.shape[0]:
                    break
                eventhappened = True
                etype = int(event[ev, 1])
                if etype == 1:
                    bus[int(buschange[ev, 1]) - 1, int(buschange[ev, 2]) - 1] = buschange[ev, 3]
                elif etype == 2:
                    branch[int(linechange[ev, 1]) - 1, int(linechange[ev, 2]) - 1] = linechange[ev, 3]
                ev += 1

            if eventhappened:
                Ly, Uy, Py = aug_ybus(baseMVA, bus, branch, xd_tr, gbus,
                                       bus[:, PD] / baseMVA, bus[:, QD] / baseMVA, U00)
                U0 = solve_network(Xgen0, Pgen, Ly, Uy, Py, gbus, genmodel)
                Id0, Iq0, Pe0 = machine_currents(Xgen0, Pgen, U0[gbus], genmodel)
                Vgen0 = np.column_stack([Id0, Iq0, Pe0])
                Vexc0 = np.abs(U0[gbus])

                if method in (3, 4):
                    newstepsize = minstepsize

                i += 1
                if i >= Time.shape[0]:
                    Time = _grow(Time, chunk)
                    Errest = _grow(Errest, chunk)
                    Stepsize = _grow(Stepsize, chunk)
                    Voltages = np.vstack([Voltages, np.zeros((chunk, nbus), dtype=complex)])
                    Efds = _grow(Efds, chunk); TM = _grow(TM, chunk); Tes = _grow(Tes, chunk)
                    Angles = _grow(Angles, chunk); Speeds = _grow(Speeds, chunk)
                    Eq_trs = _grow(Eq_trs, chunk); Ed_trs = _grow(Ed_trs, chunk)
                    Vss = _grow(Vss, chunk)
                Stepsize[i] = stepsize
                Errest[i] = errest
                Time[i] = t
                Voltages[i, :] = U0
                Efds[i, :] = Xexc0[:, 0]
                Vss[i, :] = Vpss0[:, 0]
                TM[i, :] = Xgov0[:, 0]
                Angles[i, :] = Xgen0[:, 0] * 180.0 / np.pi
                Speeds[i, :] = Xgen0[:, 1] / (2.0 * np.pi * freq)
                Eq_trs[i, :] = Xgen0[:, 2]
                Ed_trs[i, :] = Xgen0[:, 3]
                Tes[i, :] = Vgen0[:, 2]

                eventhappened = False

        stepsize = newstepsize
        t = t + stepsize

    n = i + 1
    simulationtime = time.time() - tic
    if output:
        print(f'> Simulation completed in {simulationtime:5.2f} seconds')

    Time = Time[:n]; Voltages = Voltages[:n]; Efds = Efds[:n]
    Angles = Angles[:n]; Speeds = Speeds[:n]; Eq_trs = Eq_trs[:n]
    Ed_trs = Ed_trs[:n]; Tes = Tes[:n]; TM = TM[:n]; Vss = Vss[:n]
    Stepsize = Stepsize[:n]; Errest = Errest[:n]

    return {
        'Time': Time,
        'Voltages': Voltages,
        'Efds': Efds,
        'Angles': Angles,
        'Speeds': Speeds,
        'Eq_trs': Eq_trs,
        'Ed_trs': Ed_trs,
        'Tes': Tes,
        'TM': TM,
        'Vss': Vss,
        'Stepsize': Stepsize,
        'Errest': Errest,
        'simulationtime': simulationtime,
    }


__all__ = ["rundyn", "default_mdopt"]
