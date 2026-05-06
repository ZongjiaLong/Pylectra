"""Native single-step ODE integrators (legacy ``rundyn`` semantics).

Direct numerical ports of:

* ``pylectra/_legacy/Solvers/ModifiedEuler.py``      → :func:`modified_euler_step`
* ``pylectra/_legacy/Solvers/RungeKutta.py``         → :func:`runge_kutta_step`
* ``pylectra/_legacy/Solvers/RungeKuttaFehlberg.py`` → :func:`rkf_step`
* ``pylectra/_legacy/Solvers/RungeKuttaHighamHall.py``→ :func:`rkhh_step`

Built on top of the native primitives in :mod:`pylectra.network` and
:mod:`pylectra.engine.derivatives`. Bit-identical to the legacy versions —
validated by ``tests/numerical/test_legacy_solvers_parity.py``.

PSS handling: only type-3 (no PSS) is supported, identical to the legacy
codebase. ``pss_step`` and ``pss_output`` collapse to no-ops, so we elide
them entirely in the modified-euler port (``Xpss`` is propagated unchanged).
"""
from __future__ import annotations

import numpy as np

from pylectra.network import machine_currents, solve_network
from pylectra.engine.derivatives import generator_step, exciter_step, governor_step


def _pss_zero(ngen: int) -> np.ndarray:
    return np.zeros((ngen, 1))


def _pss_output(Vpss0: np.ndarray) -> np.ndarray:
    """Mirror ``Auxiliary.PSSoutput``: returns a zero-filled output of the same shape."""
    return np.zeros_like(Vpss0)


def modified_euler_step(t, Xgen0, Pgen, Vgen0, Xpss0, Ppss, Vpss0, Xexc0, Pexc, Vexc0,
                        Xgov0, Pgov, Vgov0, Ly, Uy, Py, gbus, genmodel, pssmodel,
                        excmodel, govmodel, stepsize, U0):
    """Predictor–corrector Heun (Gauss-Seidel coupled across subsystems)."""
    # ---- First Euler step (predictor) ----
    Xpss1 = Xpss0  # PSS type 3 → derivative is zero
    Vpss1 = _pss_output(Vpss0)

    dFexc0 = exciter_step(Xexc0, Xgen0, Pexc, Vexc0, Vpss1, excmodel)
    Xexc1 = Xexc0 + stepsize * dFexc0

    dFgov0 = governor_step(Xgov0, Pgov, Vgov0, govmodel)
    Xgov1 = Xgov0 + stepsize * dFgov0

    dFgen0 = generator_step(Xgen0, Xexc1, Xgov1, Pgen, Vgen0, genmodel)
    Xgen1 = Xgen0 + stepsize * dFgen0

    U1 = solve_network(Xgen1, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id1, Iq1, Pe1 = machine_currents(Xgen1, Pgen, U1[gbus], genmodel)

    Vexc1 = U1[gbus]
    Vgen1 = np.column_stack([Id1, Iq1, Pe1])
    Vgov1 = Xgen1[:, 1].copy()

    # ---- Second Euler step (corrector) ----
    Xpss2 = Xpss1
    Vpss2 = _pss_output(Vpss1)

    dFexc1 = exciter_step(Xexc1, Xgen1, Pexc, Vexc1, Vpss2, excmodel)
    Xexc2 = Xexc0 + stepsize / 2.0 * (dFexc0 + dFexc1)

    dFgov1 = governor_step(Xgov1, Pgov, Vgov1, govmodel)
    Xgov2 = Xgov0 + stepsize / 2.0 * (dFgov0 + dFgov1)

    dFgen1 = generator_step(Xgen1, Xexc2, Xgov2, Pgen, Vgen1, genmodel)
    Xgen2 = Xgen0 + stepsize / 2.0 * (dFgen0 + dFgen1)

    U2 = solve_network(Xgen2, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id2, Iq2, Pe2 = machine_currents(Xgen2, Pgen, U2[gbus], genmodel)

    Vgen2 = np.column_stack([Id2, Iq2, Pe2])
    Vexc2 = U2[gbus]
    Vgov2 = Xgen2[:, 1].copy()

    return (Xgen2, Pgen, Vgen2, Xpss2, Ppss, Vpss2, Xexc2, Pexc, Vexc2,
            Xgov2, Pgov, Vgov2, U2, t, stepsize)


def runge_kutta_step(t0, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0, Xgov0, Pgov, Vgov0,
                     Ly, Uy, Py, gbus, genmodel, excmodel, govmodel, stepsize):
    """Classical 4th-order Runge–Kutta (fixed step).

    Note: Vexc is passed as ``np.abs(U[gbus])`` (real magnitude) — same shape
    as the legacy MATLAB port, distinct from :func:`modified_euler_step` which
    uses the complex bus voltage.  This idiosyncrasy is preserved verbatim.
    """
    a = np.array([
        [0,   0,   0, 0],
        [1/2, 0,   0, 0],
        [0,   1/2, 0, 0],
        [0,   0,   1, 0],
    ])
    b = np.array([1/6, 2/6, 2/6, 1/6])
    Vpss_zero = _pss_zero(Xexc0.shape[0])

    # K1
    Kexc1 = exciter_step(Xexc0, Xgen0, Pexc, Vexc0, Vpss_zero, excmodel)
    Xexc1 = Xexc0 + stepsize * a[1, 0] * Kexc1
    Kgov1 = governor_step(Xgov0, Pgov, Vgov0, govmodel)
    Xgov1 = Xgov0 + stepsize * a[1, 0] * Kgov1
    Kgen1 = generator_step(Xgen0, Xexc1, Xgov1, Pgen, Vgen0, genmodel)
    Xgen1 = Xgen0 + stepsize * a[1, 0] * Kgen1
    U1 = solve_network(Xgen1, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id1, Iq1, Pe1 = machine_currents(Xgen1, Pgen, U1[gbus], genmodel)
    Vexc1 = np.abs(U1[gbus])
    Vgen1 = np.column_stack([Id1, Iq1, Pe1])
    Vgov1 = Xgen1[:, 1].copy()

    # K2
    Kexc2 = exciter_step(Xexc1, Xgen1, Pexc, Vexc1, Vpss_zero, excmodel)
    Xexc2 = Xexc0 + stepsize * (a[2, 0] * Kexc1 + a[2, 1] * Kexc2)
    Kgov2 = governor_step(Xgov1, Pgov, Vgov1, govmodel)
    Xgov2 = Xgov0 + stepsize * (a[2, 0] * Kgov1 + a[2, 1] * Kgov2)
    Kgen2 = generator_step(Xgen1, Xexc2, Xgov2, Pgen, Vgen1, genmodel)
    Xgen2 = Xgen0 + stepsize * (a[2, 0] * Kgen1 + a[2, 1] * Kgen2)
    U2 = solve_network(Xgen2, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id2, Iq2, Pe2 = machine_currents(Xgen2, Pgen, U2[gbus], genmodel)
    Vexc2 = np.abs(U2[gbus])
    Vgen2 = np.column_stack([Id2, Iq2, Pe2])
    Vgov2 = Xgen2[:, 1].copy()

    # K3
    Kexc3 = exciter_step(Xexc2, Xgen2, Pexc, Vexc2, Vpss_zero, excmodel)
    Xexc3 = Xexc0 + stepsize * (a[3, 0] * Kexc1 + a[3, 1] * Kexc2 + a[3, 2] * Kexc3)
    Kgov3 = governor_step(Xgov2, Pgov, Vgov2, govmodel)
    Xgov3 = Xgov0 + stepsize * (a[3, 0] * Kgov1 + a[3, 1] * Kgov2 + a[3, 2] * Kgov3)
    Kgen3 = generator_step(Xgen2, Xexc3, Xgov3, Pgen, Vgen2, genmodel)
    Xgen3 = Xgen0 + stepsize * (a[3, 0] * Kgen1 + a[3, 1] * Kgen2 + a[3, 2] * Kgen3)
    U3 = solve_network(Xgen3, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id3, Iq3, Pe3 = machine_currents(Xgen3, Pgen, U3[gbus], genmodel)
    Vexc3 = np.abs(U3[gbus])
    Vgen3 = np.column_stack([Id3, Iq3, Pe3])
    Vgov3 = Xgen3[:, 1].copy()

    # K4 (final, weighted by b)
    Kexc4 = exciter_step(Xexc3, Xgen3, Pexc, Vexc3, Vpss_zero, excmodel)
    Xexc4 = Xexc0 + stepsize * (b[0] * Kexc1 + b[1] * Kexc2 + b[2] * Kexc3 + b[3] * Kexc4)
    Kgov4 = governor_step(Xgov3, Pgov, Vgov3, govmodel)
    Xgov4 = Xgov0 + stepsize * (b[0] * Kgov1 + b[1] * Kgov2 + b[2] * Kgov3 + b[3] * Kgov4)
    Kgen4 = generator_step(Xgen3, Xexc4, Xgov4, Pgen, Vgen3, genmodel)
    Xgen4 = Xgen0 + stepsize * (b[0] * Kgen1 + b[1] * Kgen2 + b[2] * Kgen3 + b[3] * Kgen4)
    U4 = solve_network(Xgen4, Pgen, Ly, Uy, Py, gbus, genmodel)
    Id4, Iq4, Pe4 = machine_currents(Xgen4, Pgen, U4[gbus], genmodel)
    Vexc4 = np.abs(U4[gbus])
    Vgen4 = np.column_stack([Id4, Iq4, Pe4])
    Vgov4 = Xgen4[:, 1].copy()

    return (Xgen4, Pgen, Vgen4, Xexc4, Pexc, Vexc4,
            Xgov4, Pgov, Vgov4, U4, t0, stepsize)


def _rk_adaptive_step(t0, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                      Xgov0, Pgov, Vgov0, U0, Ly, Uy, Py, gbus,
                      genmodel, excmodel, govmodel, tol, maxstepsize, stepsize,
                      a, b1, b2, n_stages):
    """Shared body of RKF45 / RKHH — explicit Butcher tableau ``(a, b1, b2)``."""
    eps_ = np.finfo(float).eps
    Vpss_zero = _pss_zero(Xexc0.shape[0])

    accept = False
    facmax = 4
    failed = 0
    t = t0

    while not accept:
        Kexc = [None] * n_stages
        Kgov = [None] * n_stages
        Kgen = [None] * n_stages
        # Stage 1 uses the entry state directly.
        Kexc[0] = exciter_step(Xexc0, Xgen0, Pexc, Vexc0, Vpss_zero, excmodel)
        Kgov[0] = governor_step(Xgov0, Pgov, Vgov0, govmodel)
        # First Xexc / Xgov / Xgen step uses a[1, 0] alone — handled in the loop.

        # We need to mirror the legacy ordering exactly: at each stage,
        # compute Xexc (sums of prior K's), Xgov, then Xgen using fresh
        # Xexc/Xgov, then solve network and machine currents.
        Xexc_stage = [Xexc0]
        Xgov_stage = [Xgov0]
        Xgen_stage = [Xgen0]
        Vexc_stage = [Vexc0]
        Vgen_stage = [Vgen0]
        Vgov_stage = [Vgov0]

        for s in range(1, n_stages):
            sum_exc = sum(a[s, j] * Kexc[j] for j in range(s))
            Xe = Xexc0 + stepsize * sum_exc
            sum_gov = sum(a[s, j] * Kgov[j] for j in range(s))
            Xg = Xgov0 + stepsize * sum_gov
            sum_gen = sum(a[s, j] * Kgen[j] for j in range(s)) if s > 1 else a[s, 0] * Kgen[0]
            # NB: stage 1 has Kgen[0] not yet computed — handled below.
            if s == 1:
                Kgen[0] = generator_step(Xgen0, Xe, Xg, Pgen, Vgen0, genmodel)
                sum_gen = a[s, 0] * Kgen[0]
            Xn = Xgen0 + stepsize * sum_gen
            Un = solve_network(Xn, Pgen, Ly, Uy, Py, gbus, genmodel)
            Idn, Iqn, Pen = machine_currents(Xn, Pgen, Un[gbus], genmodel)
            Ve = np.abs(Un[gbus])
            Vn = np.column_stack([Idn, Iqn, Pen])
            Vg = Xn[:, 1].copy()

            Xexc_stage.append(Xe); Xgov_stage.append(Xg); Xgen_stage.append(Xn)
            Vexc_stage.append(Ve); Vgen_stage.append(Vn); Vgov_stage.append(Vg)

            # K[s]
            Kexc[s] = exciter_step(Xe, Xn, Pexc, Ve, Vpss_zero, excmodel)
            Kgov[s] = governor_step(Xg, Pgov, Vg, govmodel)
            # Kgen for stage s uses Xexc/Xgov/Xgen of stage s, but the legacy code
            # actually uses Xexc/Xgov from the *next* sum. Below we recompute Kgen
            # at the same stage since the legacy unrolled form does it in-line.
            # Re-derive Xexc/Xgov for the current stage's Kgen call by replicating
            # the unrolled construction:
            sum_exc_next = sum(a[s, j] * Kexc[j] for j in range(s + 1))
            Xe_next = Xexc0 + stepsize * sum_exc_next
            sum_gov_next = sum(a[s, j] * Kgov[j] for j in range(s + 1))
            Xg_next = Xgov0 + stepsize * sum_gov_next
            Kgen[s] = generator_step(Xn, Xe_next, Xg_next, Pgen, Vn, genmodel)

        # Stage n_stages-1 results are the "nominal" (b1) trajectory.
        # Final K stage: compute K[n_stages-1] using stage (n_stages-1) outputs,
        # then aggregate b1 weights for the final state.
        # The construction above already places K[s] for s=0..n_stages-1.
        # Now compute the b1 / b2 weighted combinations.
        Xexc_b1 = Xexc0 + stepsize * sum(b1[j] * Kexc[j] for j in range(n_stages))
        Xgov_b1 = Xgov0 + stepsize * sum(b1[j] * Kgov[j] for j in range(n_stages))
        Xgen_b1 = Xgen0 + stepsize * sum(b1[j] * Kgen[j] for j in range(n_stages))

        Xexc_b2 = Xexc0 + stepsize * sum(b2[j] * Kexc[j] for j in range(n_stages))
        Xgov_b2 = Xgov0 + stepsize * sum(b2[j] * Kgov[j] for j in range(n_stages))
        Xgen_b2 = Xgen0 + stepsize * sum(b2[j] * Kgen[j] for j in range(n_stages))

        # Network / currents at the b1 solution (matches legacy behaviour).
        U_b1 = solve_network(Xgen_b1, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id_b1, Iq_b1, Pe_b1 = machine_currents(Xgen_b1, Pgen, U_b1[gbus], genmodel)
        Vexc_b1 = np.abs(U_b1[gbus])
        Vgen_b1 = np.column_stack([Id_b1, Iq_b1, Pe_b1])
        Vgov_b1 = Xgen_b1[:, 1].copy()

        errest = max(np.max(np.abs(Xexc_b2 - Xexc_b1)) if Xexc_b1.size else 0.0,
                     np.max(np.abs(Xgov_b2 - Xgov_b1)) if Xgov_b1.size else 0.0,
                     np.max(np.abs(Xgen_b2 - Xgen_b1)) if Xgen_b1.size else 0.0)
        if errest < eps_:
            errest = eps_
        q = 0.84 * (tol / errest) ** 0.25

        if errest < tol:
            accept = True
            U0 = U_b1
            Vgen0 = Vgen_b1; Vgov0 = Vgov_b1; Vexc0 = Vexc_b1
            Xgen0 = Xgen_b1; Xexc0 = Xexc_b1; Xgov0 = Xgov_b1
            Pgen0 = Pgen; Pexc0 = Pexc; Pgov0 = Pgov
            t = t0
        else:
            failed += 1
            facmax = 1
            t = t0
            stepsize = min(max(q, 0.1), facmax) * stepsize
            return (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                    Xgov0, Pgov, Vgov0, U0, errest, failed, t, stepsize)

        stepsize = min(max(q, 0.1), facmax) * stepsize
        if stepsize > maxstepsize:
            stepsize = maxstepsize

    return (Xgen0, Pgen0, Vgen0, Xexc0, Pexc0, Vexc0,
            Xgov0, Pgov0, Vgov0, U0, errest, failed, t, stepsize)


# Adaptive RK uses a Butcher tableau where each stage's K_s uses only K_0..K_{s-1}.
# The legacy unrolled code does *not* match that pattern naively — it interleaves
# Xexc / Xgov updates across stages (Gauss-Seidel-like).  The shared
# ``_rk_adaptive_step`` above tries to reproduce that ordering, but verifying
# bit-identity requires direct unrolled ports below.  We keep dedicated unrolled
# functions for RKF and RKHH to guarantee numerical parity.


def rkf_step(t0, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
             Xgov0, Pgov, Vgov0, U0, Ly, Uy, Py, gbus,
             genmodel, excmodel, govmodel, tol, maxstepsize, stepsize):
    """Adaptive Runge-Kutta-Fehlberg 4(5)."""
    a = np.array([
        [0,            0,         0,           0,         0],
        [1/4,          0,         0,           0,         0],
        [3/32,         9/32,      0,           0,         0],
        [1932/2197,   -7200/2197, 7296/2197,   0,         0],
        [439/216,     -8,         3680/513,   -845/4104,  0],
        [-8/27,        2,        -3544/2565,   1859/4104, -11/40],
    ])
    b1 = np.array([25/216, 0, 1408/2565, 2197/4104, -1/5, 0])
    b2 = np.array([16/135, 0, 6656/12825, 28561/56430, -9/50, 2/55])
    Vpss_zero = _pss_zero(Xexc0.shape[0])

    accept = False
    facmax = 4
    failed = 0
    eps_ = np.finfo(float).eps

    while not accept:
        Kexc1 = exciter_step(Xexc0, Xgen0, Pexc, Vexc0, Vpss_zero, excmodel)
        Xexc1 = Xexc0 + stepsize * a[1, 0] * Kexc1
        Kgov1 = governor_step(Xgov0, Pgov, Vgov0, govmodel)
        Xgov1 = Xgov0 + stepsize * a[1, 0] * Kgov1
        Kgen1 = generator_step(Xgen0, Xexc1, Xgov1, Pgen, Vgen0, genmodel)
        Xgen1 = Xgen0 + stepsize * a[1, 0] * Kgen1
        U1 = solve_network(Xgen1, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id1, Iq1, Pe1 = machine_currents(Xgen1, Pgen, U1[gbus], genmodel)
        Vexc1 = np.abs(U1[gbus]); Vgen1 = np.column_stack([Id1, Iq1, Pe1]); Vgov1 = Xgen1[:, 1].copy()

        Kexc2 = exciter_step(Xexc1, Xgen1, Pexc, Vexc1, Vpss_zero, excmodel)
        Xexc2 = Xexc0 + stepsize * (a[2, 0]*Kexc1 + a[2, 1]*Kexc2)
        Kgov2 = governor_step(Xgov1, Pgov, Vgov1, govmodel)
        Xgov2 = Xgov0 + stepsize * (a[2, 0]*Kgov1 + a[2, 1]*Kgov2)
        Kgen2 = generator_step(Xgen1, Xexc2, Xgov2, Pgen, Vgen1, genmodel)
        Xgen2 = Xgen0 + stepsize * (a[2, 0]*Kgen1 + a[2, 1]*Kgen2)
        U2 = solve_network(Xgen2, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id2, Iq2, Pe2 = machine_currents(Xgen2, Pgen, U2[gbus], genmodel)
        Vexc2 = np.abs(U2[gbus]); Vgen2 = np.column_stack([Id2, Iq2, Pe2]); Vgov2 = Xgen2[:, 1].copy()

        Kexc3 = exciter_step(Xexc2, Xgen2, Pexc, Vexc2, Vpss_zero, excmodel)
        Xexc3 = Xexc0 + stepsize * (a[3, 0]*Kexc1 + a[3, 1]*Kexc2 + a[3, 2]*Kexc3)
        Kgov3 = governor_step(Xgov2, Pgov, Vgov2, govmodel)
        Xgov3 = Xgov0 + stepsize * (a[3, 0]*Kgov1 + a[3, 1]*Kgov2 + a[3, 2]*Kgov3)
        Kgen3 = generator_step(Xgen2, Xexc3, Xgov3, Pgen, Vgen2, genmodel)
        Xgen3 = Xgen0 + stepsize * (a[3, 0]*Kgen1 + a[3, 1]*Kgen2 + a[3, 2]*Kgen3)
        U3 = solve_network(Xgen3, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id3, Iq3, Pe3 = machine_currents(Xgen3, Pgen, U3[gbus], genmodel)
        Vexc3 = np.abs(U3[gbus]); Vgen3 = np.column_stack([Id3, Iq3, Pe3]); Vgov3 = Xgen3[:, 1].copy()

        Kexc4 = exciter_step(Xexc3, Xgen3, Pexc, Vexc3, Vpss_zero, excmodel)
        Xexc4 = Xexc0 + stepsize * (a[4, 0]*Kexc1 + a[4, 1]*Kexc2 + a[4, 2]*Kexc3 + a[4, 3]*Kexc4)
        Kgov4 = governor_step(Xgov3, Pgov, Vgov3, govmodel)
        Xgov4 = Xgov0 + stepsize * (a[4, 0]*Kgov1 + a[4, 1]*Kgov2 + a[4, 2]*Kgov3 + a[4, 3]*Kgov4)
        Kgen4 = generator_step(Xgen3, Xexc4, Xgov4, Pgen, Vgen3, genmodel)
        Xgen4 = Xgen0 + stepsize * (a[4, 0]*Kgen1 + a[4, 1]*Kgen2 + a[4, 2]*Kgen3 + a[4, 3]*Kgen4)
        U4 = solve_network(Xgen4, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id4, Iq4, Pe4 = machine_currents(Xgen4, Pgen, U4[gbus], genmodel)
        Vexc4 = np.abs(U4[gbus]); Vgen4 = np.column_stack([Id4, Iq4, Pe4]); Vgov4 = Xgen4[:, 1].copy()

        Kexc5 = exciter_step(Xexc4, Xgen4, Pexc, Vexc4, Vpss_zero, excmodel)
        Xexc5 = Xexc0 + stepsize * (a[5, 0]*Kexc1 + a[5, 1]*Kexc2 + a[5, 2]*Kexc3 + a[5, 3]*Kexc4 + a[5, 4]*Kexc5)
        Kgov5 = governor_step(Xgov4, Pgov, Vgov4, govmodel)
        Xgov5 = Xgov0 + stepsize * (a[5, 0]*Kgov1 + a[5, 1]*Kgov2 + a[5, 2]*Kgov3 + a[5, 3]*Kgov4 + a[5, 4]*Kgov5)
        Kgen5 = generator_step(Xgen4, Xexc5, Xgov5, Pgen, Vgen4, genmodel)
        Xgen5 = Xgen0 + stepsize * (a[5, 0]*Kgen1 + a[5, 1]*Kgen2 + a[5, 2]*Kgen3 + a[5, 3]*Kgen4 + a[5, 4]*Kgen5)
        U5 = solve_network(Xgen5, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id5, Iq5, Pe5 = machine_currents(Xgen5, Pgen, U5[gbus], genmodel)
        Vexc5 = np.abs(U5[gbus]); Vgen5 = np.column_stack([Id5, Iq5, Pe5]); Vgov5 = Xgen5[:, 1].copy()

        # K6 / b1 (5th-order)
        Kexc6 = exciter_step(Xexc5, Xgen5, Pexc, Vexc5, Vpss_zero, excmodel)
        Xexc6 = Xexc0 + stepsize * (b1[0]*Kexc1 + b1[1]*Kexc2 + b1[2]*Kexc3 + b1[3]*Kexc4 + b1[4]*Kexc5 + b1[5]*Kexc6)
        Kgov6 = governor_step(Xgov5, Pgov, Vgov5, govmodel)
        Xgov6 = Xgov0 + stepsize * (b1[0]*Kgov1 + b1[1]*Kgov2 + b1[2]*Kgov3 + b1[3]*Kgov4 + b1[4]*Kgov5 + b1[5]*Kgov6)
        Kgen6 = generator_step(Xgen5, Xexc6, Xgov6, Pgen, Vgen5, genmodel)
        Xgen6 = Xgen0 + stepsize * (b1[0]*Kgen1 + b1[1]*Kgen2 + b1[2]*Kgen3 + b1[3]*Kgen4 + b1[4]*Kgen5 + b1[5]*Kgen6)
        U6 = solve_network(Xgen6, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id6, Iq6, Pe6 = machine_currents(Xgen6, Pgen, U6[gbus], genmodel)
        Vexc6 = np.abs(U6[gbus]); Vgen6 = np.column_stack([Id6, Iq6, Pe6]); Vgov6 = Xgen6[:, 1].copy()

        # b2 (higher-order) for error estimation
        Xexc62 = Xexc0 + stepsize * (b2[0]*Kexc1 + b2[1]*Kexc2 + b2[2]*Kexc3 + b2[3]*Kexc4 + b2[4]*Kexc5 + b2[5]*Kexc6)
        Xgov62 = Xgov0 + stepsize * (b2[0]*Kgov1 + b2[1]*Kgov2 + b2[2]*Kgov3 + b2[3]*Kgov4 + b2[4]*Kgov5 + b2[5]*Kgov6)
        Xgen62 = Xgen0 + stepsize * (b2[0]*Kgen1 + b2[1]*Kgen2 + b2[2]*Kgen3 + b2[3]*Kgen4 + b2[4]*Kgen5 + b2[5]*Kgen6)

        errest = max(np.max(np.abs(Xexc62 - Xexc6)) if Xexc6.size else 0.0,
                     np.max(np.abs(Xgov62 - Xgov6)) if Xgov6.size else 0.0,
                     np.max(np.abs(Xgen62 - Xgen6)) if Xgen6.size else 0.0)
        if errest < eps_:
            errest = eps_
        q = 0.84 * (tol / errest) ** 0.25

        if errest < tol:
            accept = True
            U0 = U6
            Vgen0 = Vgen6; Vgov0 = Vgov6; Vexc0 = Vexc6
            Xgen0 = Xgen6; Xexc0 = Xexc6; Xgov0 = Xgov6
            Pgen0 = Pgen; Pexc0 = Pexc; Pgov0 = Pgov
            t = t0
        else:
            failed += 1
            facmax = 1
            t = t0
            stepsize = min(max(q, 0.1), facmax) * stepsize
            return (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                    Xgov0, Pgov, Vgov0, U0, errest, failed, t, stepsize)

        stepsize = min(max(q, 0.1), facmax) * stepsize
        if stepsize > maxstepsize:
            stepsize = maxstepsize

    return (Xgen0, Pgen0, Vgen0, Xexc0, Pexc0, Vexc0,
            Xgov0, Pgov0, Vgov0, U0, errest, failed, t, stepsize)


def rkhh_step(t0, Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
              Xgov0, Pgov, Vgov0, U0, Ly, Uy, Py, gbus,
              genmodel, excmodel, govmodel, tol, maxstepsize, stepsize):
    """Adaptive Higham–Hall Runge-Kutta."""
    a = np.array([
        [0,        0,        0,       0,        0,      0],
        [2/9,      0,        0,       0,        0,      0],
        [1/12,     1/4,      0,       0,        0,      0],
        [1/8,      0,        3/8,     0,        0,      0],
        [91/500,  -27/100,   78/125,  8/125,    0,      0],
        [-11/20,   27/20,    12/5,   -36/5,     5,      0],
        [1/12,     0,        27/32,  -4/3,     125/96,  5/48],
    ])
    b1 = np.array([1/12, 0, 27/32, -4/3, 125/96, 5/48, 0])
    b2 = np.array([2/15, 0, 27/80, -2/15, 25/48, 1/24, 1/10])
    Vpss_zero = _pss_zero(Xexc0.shape[0])

    accept = False
    facmax = 4
    failed = 0
    eps_ = np.finfo(float).eps

    while not accept:
        Kexc1 = exciter_step(Xexc0, Xgen0, Pexc, Vexc0, Vpss_zero, excmodel)
        Xexc1 = Xexc0 + stepsize * a[1, 0] * Kexc1
        Kgov1 = governor_step(Xgov0, Pgov, Vgov0, govmodel)
        Xgov1 = Xgov0 + stepsize * a[1, 0] * Kgov1
        Kgen1 = generator_step(Xgen0, Xexc1, Xgov1, Pgen, Vgen0, genmodel)
        Xgen1 = Xgen0 + stepsize * a[1, 0] * Kgen1
        U1 = solve_network(Xgen1, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id1, Iq1, Pe1 = machine_currents(Xgen1, Pgen, U1[gbus], genmodel)
        Vexc1 = np.abs(U1[gbus]); Vgen1 = np.column_stack([Id1, Iq1, Pe1]); Vgov1 = Xgen1[:, 1].copy()

        Kexc2 = exciter_step(Xexc1, Xgen1, Pexc, Vexc1, Vpss_zero, excmodel)
        Xexc2 = Xexc0 + stepsize * (a[2, 0]*Kexc1 + a[2, 1]*Kexc2)
        Kgov2 = governor_step(Xgov1, Pgov, Vgov1, govmodel)
        Xgov2 = Xgov0 + stepsize * (a[2, 0]*Kgov1 + a[2, 1]*Kgov2)
        Kgen2 = generator_step(Xgen1, Xexc2, Xgov2, Pgen, Vgen1, genmodel)
        Xgen2 = Xgen0 + stepsize * (a[2, 0]*Kgen1 + a[2, 1]*Kgen2)
        U2 = solve_network(Xgen2, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id2, Iq2, Pe2 = machine_currents(Xgen2, Pgen, U2[gbus], genmodel)
        Vexc2 = np.abs(U2[gbus]); Vgen2 = np.column_stack([Id2, Iq2, Pe2]); Vgov2 = Xgen2[:, 1].copy()

        Kexc3 = exciter_step(Xexc2, Xgen2, Pexc, Vexc2, Vpss_zero, excmodel)
        Xexc3 = Xexc0 + stepsize * (a[3, 0]*Kexc1 + a[3, 1]*Kexc2 + a[3, 2]*Kexc3)
        Kgov3 = governor_step(Xgov2, Pgov, Vgov2, govmodel)
        Xgov3 = Xgov0 + stepsize * (a[3, 0]*Kgov1 + a[3, 1]*Kgov2 + a[3, 2]*Kgov3)
        Kgen3 = generator_step(Xgen2, Xexc3, Xgov3, Pgen, Vgen2, genmodel)
        Xgen3 = Xgen0 + stepsize * (a[3, 0]*Kgen1 + a[3, 1]*Kgen2 + a[3, 2]*Kgen3)
        U3 = solve_network(Xgen3, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id3, Iq3, Pe3 = machine_currents(Xgen3, Pgen, U3[gbus], genmodel)
        Vexc3 = np.abs(U3[gbus]); Vgen3 = np.column_stack([Id3, Iq3, Pe3]); Vgov3 = Xgen3[:, 1].copy()

        Kexc4 = exciter_step(Xexc3, Xgen3, Pexc, Vexc3, Vpss_zero, excmodel)
        Xexc4 = Xexc0 + stepsize * (a[4, 0]*Kexc1 + a[4, 1]*Kexc2 + a[4, 2]*Kexc3 + a[4, 3]*Kexc4)
        Kgov4 = governor_step(Xgov3, Pgov, Vgov3, govmodel)
        Xgov4 = Xgov0 + stepsize * (a[4, 0]*Kgov1 + a[4, 1]*Kgov2 + a[4, 2]*Kgov3 + a[4, 3]*Kgov4)
        Kgen4 = generator_step(Xgen3, Xexc4, Xgov4, Pgen, Vgen3, genmodel)
        Xgen4 = Xgen0 + stepsize * (a[4, 0]*Kgen1 + a[4, 1]*Kgen2 + a[4, 2]*Kgen3 + a[4, 3]*Kgen4)
        U4 = solve_network(Xgen4, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id4, Iq4, Pe4 = machine_currents(Xgen4, Pgen, U4[gbus], genmodel)
        Vexc4 = np.abs(U4[gbus]); Vgen4 = np.column_stack([Id4, Iq4, Pe4]); Vgov4 = Xgen4[:, 1].copy()

        Kexc5 = exciter_step(Xexc4, Xgen4, Pexc, Vexc4, Vpss_zero, excmodel)
        Xexc5 = Xexc0 + stepsize * (a[5, 0]*Kexc1 + a[5, 1]*Kexc2 + a[5, 2]*Kexc3 + a[5, 3]*Kexc4 + a[5, 4]*Kexc5)
        Kgov5 = governor_step(Xgov4, Pgov, Vgov4, govmodel)
        Xgov5 = Xgov0 + stepsize * (a[5, 0]*Kgov1 + a[5, 1]*Kgov2 + a[5, 2]*Kgov3 + a[5, 3]*Kgov4 + a[5, 4]*Kgov5)
        Kgen5 = generator_step(Xgen4, Xexc5, Xgov5, Pgen, Vgen4, genmodel)
        Xgen5 = Xgen0 + stepsize * (a[5, 0]*Kgen1 + a[5, 1]*Kgen2 + a[5, 2]*Kgen3 + a[5, 3]*Kgen4 + a[5, 4]*Kgen5)
        U5 = solve_network(Xgen5, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id5, Iq5, Pe5 = machine_currents(Xgen5, Pgen, U5[gbus], genmodel)
        Vexc5 = np.abs(U5[gbus]); Vgen5 = np.column_stack([Id5, Iq5, Pe5]); Vgov5 = Xgen5[:, 1].copy()

        Kexc6 = exciter_step(Xexc5, Xgen5, Pexc, Vexc5, Vpss_zero, excmodel)
        Xexc6 = Xexc0 + stepsize * (a[6, 0]*Kexc1 + a[6, 1]*Kexc2 + a[6, 2]*Kexc3 + a[6, 3]*Kexc4 + a[6, 4]*Kexc5 + a[6, 5]*Kexc6)
        Kgov6 = governor_step(Xgov5, Pgov, Vgov5, govmodel)
        Xgov6 = Xgov0 + stepsize * (a[6, 0]*Kgov1 + a[6, 1]*Kgov2 + a[6, 2]*Kgov3 + a[6, 3]*Kgov4 + a[6, 4]*Kgov5 + a[6, 5]*Kgov6)
        Kgen6 = generator_step(Xgen5, Xexc6, Xgov6, Pgen, Vgen5, genmodel)
        Xgen6 = Xgen0 + stepsize * (a[6, 0]*Kgen1 + a[6, 1]*Kgen2 + a[6, 2]*Kgen3 + a[6, 3]*Kgen4 + a[6, 4]*Kgen5 + a[6, 5]*Kgen6)
        U6 = solve_network(Xgen6, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id6, Iq6, Pe6 = machine_currents(Xgen6, Pgen, U6[gbus], genmodel)
        Vexc6 = np.abs(U6[gbus]); Vgen6 = np.column_stack([Id6, Iq6, Pe6]); Vgov6 = Xgen6[:, 1].copy()

        # K7 / b1 (nominal)
        Kexc7 = exciter_step(Xexc6, Xgen6, Pexc, Vexc6, Vpss_zero, excmodel)
        Xexc7 = Xexc0 + stepsize * (b1[0]*Kexc1 + b1[1]*Kexc2 + b1[2]*Kexc3 + b1[3]*Kexc4 + b1[4]*Kexc5 + b1[5]*Kexc6 + b1[6]*Kexc7)
        Kgov7 = governor_step(Xgov6, Pgov, Vgov6, govmodel)
        Xgov7 = Xgov0 + stepsize * (b1[0]*Kgov1 + b1[1]*Kgov2 + b1[2]*Kgov3 + b1[3]*Kgov4 + b1[4]*Kgov5 + b1[5]*Kgov6 + b1[6]*Kgov7)
        Kgen7 = generator_step(Xgen6, Xexc7, Xgov7, Pgen, Vgen6, genmodel)
        Xgen7 = Xgen0 + stepsize * (b1[0]*Kgen1 + b1[1]*Kgen2 + b1[2]*Kgen3 + b1[3]*Kgen4 + b1[4]*Kgen5 + b1[5]*Kgen6 + b1[6]*Kgen7)
        U7 = solve_network(Xgen7, Pgen, Ly, Uy, Py, gbus, genmodel)
        Id7, Iq7, Pe7 = machine_currents(Xgen7, Pgen, U7[gbus], genmodel)
        Vexc7 = np.abs(U7[gbus]); Vgen7 = np.column_stack([Id7, Iq7, Pe7]); Vgov7 = Xgen7[:, 1].copy()

        Xexc72 = Xexc0 + stepsize * (b2[0]*Kexc1 + b2[1]*Kexc2 + b2[2]*Kexc3 + b2[3]*Kexc4 + b2[4]*Kexc5 + b2[5]*Kexc6 + b2[6]*Kexc7)
        Xgov72 = Xgov0 + stepsize * (b2[0]*Kgov1 + b2[1]*Kgov2 + b2[2]*Kgov3 + b2[3]*Kgov4 + b2[4]*Kgov5 + b2[5]*Kgov6 + b2[6]*Kgov7)
        Xgen72 = Xgen0 + stepsize * (b2[0]*Kgen1 + b2[1]*Kgen2 + b2[2]*Kgen3 + b2[3]*Kgen4 + b2[4]*Kgen5 + b2[5]*Kgen6 + b2[6]*Kgen7)

        errest = max(np.max(np.abs(Xexc72 - Xexc7)) if Xexc7.size else 0.0,
                     np.max(np.abs(Xgov72 - Xgov7)) if Xgov7.size else 0.0,
                     np.max(np.abs(Xgen72 - Xgen7)) if Xgen7.size else 0.0)
        if errest < eps_:
            errest = eps_
        q = 0.84 * (tol / errest) ** 0.25

        if errest < tol:
            accept = True
            U0 = U7
            Vgen0 = Vgen7; Vgov0 = Vgov7; Vexc0 = Vexc7
            Xgen0 = Xgen7; Xexc0 = Xexc7; Xgov0 = Xgov7
            Pgen0 = Pgen; Pexc0 = Pexc; Pgov0 = Pgov
            t = t0
        else:
            failed += 1
            facmax = 1
            t = t0
            stepsize = min(max(q, 0.1), facmax) * stepsize
            return (Xgen0, Pgen, Vgen0, Xexc0, Pexc, Vexc0,
                    Xgov0, Pgov, Vgov0, U0, errest, failed, t, stepsize)

        stepsize = min(max(q, 0.1), facmax) * stepsize
        if stepsize > maxstepsize:
            stepsize = maxstepsize

    return (Xgen0, Pgen0, Vgen0, Xexc0, Pexc0, Vexc0,
            Xgov0, Pgov0, Vgov0, U0, errest, failed, t, stepsize)


__all__ = ["modified_euler_step", "runge_kutta_step", "rkf_step", "rkhh_step"]
