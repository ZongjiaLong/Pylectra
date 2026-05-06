"""Native dynamic derivatives — drop-in replacements for legacy step functions.

Direct ports of:
* ``pylectra/_legacy/Models/Generators/Generator.py``  (type 2: 4th-order)
* ``pylectra/_legacy/Models/Exciters/Exciter.py``      (types 3 & 4)
* ``pylectra/_legacy/Models/Governors/Governor.py``    (types 1 & 2)

Pure ``numpy``; ``Models._globals.freq`` reference replaced by
``pylectra.core.freq.freq``. Bit-identical to the legacy versions on the
supported types — validated by ``tests/numerical/test_derivatives_parity.py``.
"""
from __future__ import annotations

import numpy as np

from pylectra.core import freq as _freq


def generator_step(Xgen, Xexc, Xgov, Pgen, Vgen, gentype):
    """Return ``F`` — d/dt of generator state, type-2 4th-order.

    Layout columns (matching legacy): ``(ddelta, domega, dEq', dEd')``.
    """
    omegas = 2.0 * np.pi * _freq.freq
    F = np.zeros_like(Xgen)
    gentype = np.asarray(gentype).ravel()
    type2 = np.flatnonzero(gentype == 2)

    if type2.size:
        omega = Xgen[type2, 1]
        Eq_tr = Xgen[type2, 2]
        Ed_tr = Xgen[type2, 3]

        H = Pgen[type2, 6]
        D = np.zeros(gentype.size)
        xd_tr = Pgen[type2, 8]
        xq_tr = Pgen[type2, 9]
        xd = Pgen[type2, 10]
        xq = Pgen[type2, 11]
        Td0_tr = Pgen[type2, 12]
        Tq0_tr = Pgen[type2, 13]

        Id = Vgen[type2, 0]
        Iq = Vgen[type2, 1]
        Pe = Vgen[type2, 2]

        Efd = Xexc[type2, 0]
        Pm = Xgov[type2, 0]

        ddelta = omega - omegas
        domega = np.pi * _freq.freq / H * (-D[type2] * (omega - omegas) / omegas + Pm - Pe)
        dEq = 1.0 / Td0_tr * (Efd - Eq_tr + (xd - xd_tr) * Id)
        dEd = 1.0 / Tq0_tr * (-Ed_tr - (xq - xq_tr) * Iq)

        F[type2, 0] = ddelta
        F[type2, 1] = domega
        F[type2, 2] = dEq
        F[type2, 3] = dEd

    return F


def exciter_step(Xexc, Xgen, Pexc, Vexc, Vpss, exctype):
    """Return ``F`` — d/dt of exciter state. Types 3 (simple AVR) and 4 (passthrough)."""
    F = np.zeros_like(Xexc)
    exctype = np.asarray(exctype).ravel()
    type3 = np.flatnonzero(exctype == 3)
    type4 = np.flatnonzero(exctype == 4)

    if type3.size:
        Efd = Xexc[type3, 0]
        Tv = Pexc[type3, 1]
        mu = Pexc[type3, 2]
        k = Pexc[type3, 3]
        L = Pexc[type3, 6]

        Vexc_arr = np.asarray(Vexc)
        U1 = Vexc_arr[type3, 0] if Vexc_arr.ndim == 2 else Vexc_arr[type3]
        V = np.abs(U1)
        theta = np.angle(U1)
        delta = Xgen[type3, 0]

        dEfd = (-Efd - mu * k * V * np.cos(delta - theta) + L) / Tv
        F[type3, 0] = dEfd

    if type4.size:
        F[type4, 0] = 0.0

    return F


def governor_step(Xgov, Pgov, Vgov, govtype):
    """Return ``F`` — d/dt of governor state. Types 1 (constant) and 2 (IEEE turbine)."""
    omegas = 2.0 * np.pi * _freq.freq
    F = np.zeros_like(Xgov)
    govtype = np.asarray(govtype).ravel()
    type1 = np.flatnonzero(govtype == 1)
    type2 = np.flatnonzero(govtype == 2)

    if type1.size:
        F[type1, 0] = 0.0

    if type2.size:
        Pm = Xgov[type2, 0]
        P = Xgov[type2, 1]
        x = Xgov[type2, 2]
        z = Xgov[type2, 3]

        K = Pgov[type2, 1]
        T1 = Pgov[type2, 2]
        T2 = Pgov[type2, 3]
        T3 = Pgov[type2, 4]
        Pup = Pgov[type2, 5]
        Pdown = Pgov[type2, 6]
        Pmax = Pgov[type2, 7]
        Pmin = Pgov[type2, 8]
        P0 = Pgov[type2, 9]

        omega = Vgov[type2]
        omega = omega.ravel() if omega.ndim > 1 else omega

        dx = K * (-1.0 / T1 * x + (1.0 - T2 / T1) * (omega - omegas))
        dP = 1.0 / T1 * x + T2 / T1 * (omega - omegas)
        y = 1.0 / T3 * (P0 - P - Pm)

        y2 = y.copy()
        upmask = y > Pup
        if np.any(upmask):
            y2 = (~upmask) * y2 + upmask * Pup
        downmask = y < Pdown
        if np.any(downmask):
            y2 = (~downmask) * y2 + downmask * Pdown

        dz = y2.copy()
        dPm = y2.copy()
        zhi = z > Pmax
        if np.any(zhi):
            dPm = (~zhi) * dPm + zhi * 0.0
        zlo = z < Pmin
        if np.any(zlo):
            dPm = (~zlo) * dPm + zlo * 0.0

        F[type2, 0] = dPm
        F[type2, 1] = dP
        F[type2, 2] = dx
        F[type2, 3] = dz

    return F


__all__ = ["generator_step", "exciter_step", "governor_step"]
