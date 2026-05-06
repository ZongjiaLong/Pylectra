"""Native init helpers — drop-in replacements for legacy ``*Init`` functions.

These are direct numerical ports of the legacy MATLAB code in
``pylectra/_legacy/Models/{Generators,Exciters,Governors,PSS}/*Init.py``,
expressed in pure ``numpy`` without legacy globals (the ``_globals.freq``
reference is replaced by ``pylectra.core.freq.freq``).

Bit-identical to the legacy versions on supported types (validated by
``tests/numerical/test_init_states_parity.py``):

* generators: type 2 (two-axis 4th-order)
* exciters:   type 3 (simple AVR), type 4 (passthrough)
* governors:  type 1 (constant), type 2 (IEEE turbine)
* PSS:        type 3 (no-op)

Other type IDs leave the corresponding rows zero, matching the legacy
fall-through behavior — the legacy code only branches on the same set.
"""
from __future__ import annotations

import numpy as np

from pylectra.core.idx import idx_gen
from pylectra.core import freq as _freq


def generator_init(Pgen, U0, gen, baseMVA, gentype):
    """Return ``(Efd0, Xgen0)`` — initial field voltage and gen state.

    ``Xgen0[:, :] = (delta, omega, Eq', Ed')`` for type-2 rows, zero
    otherwise.
    """
    (GEN_BUS, PG, QG, *_rest) = idx_gen()
    ngen = Pgen.shape[0]
    Xgen0 = np.zeros((ngen, 4))
    Efd0 = np.zeros(ngen)
    gentype = np.asarray(gentype).ravel()
    type2 = np.flatnonzero(gentype == 2)

    if type2.size:
        xd_tr = Pgen[type2, 8]
        xq_tr = Pgen[type2, 9]
        xd = Pgen[type2, 10]
        xq = Pgen[type2, 11]

        omega0 = np.ones(type2.size) * 2.0 * np.pi * _freq.freq

        Ia0 = (gen[type2, PG] - 1j * gen[type2, QG]) / np.conj(U0[type2]) / baseMVA
        phi0 = np.angle(Ia0)

        Eq0 = U0[type2] + 1j * xq * Ia0
        delta0 = np.angle(Eq0)

        Id0 = -np.abs(Ia0) * np.sin(delta0 - phi0)
        Iq0 = np.abs(Ia0) * np.cos(delta0 - phi0)

        Efd0[type2] = np.abs(Eq0) - (xd - xq) * Id0

        Eq_tr0 = Efd0[type2] + (xd - xd_tr) * Id0
        Ed_tr0 = -(xq - xq_tr) * Iq0

        Xgen0[type2, 0] = delta0
        Xgen0[type2, 1] = omega0
        Xgen0[type2, 2] = Eq_tr0
        Xgen0[type2, 3] = Ed_tr0

    return Efd0, Xgen0


def exciter_init(Xexc, Xgen, Pexc, Vexc, exctype):
    """Return ``(Xexc0, Pexc0)`` — initial exciter state and parameters."""
    Xexc = np.asarray(Xexc, dtype=float)
    if Xexc.ndim == 1:
        Xexc = Xexc.reshape(-1, 1)
    ngen, c = Xexc.shape
    Xexc0 = np.zeros((ngen, max(c, 1)))
    Pexc0 = np.zeros((Pexc.shape[0], max(Pexc.shape[1], 7)))
    exctype = np.asarray(exctype).ravel()

    type3 = np.flatnonzero(exctype == 3)
    type4 = np.flatnonzero(exctype == 4)

    if type3.size:
        Efd0 = Xexc[type3, 0]
        Tv = Pexc[type3, 1]
        mu = Pexc[type3, 2]
        k = Pexc[type3, 3]
        Efd_min = Pexc[type3, 4]
        Efd_max = Pexc[type3, 4]  # legacy MATLAB typo: col 5 used for both bounds

        delta = Xgen[type3, 0]
        Vexc_arr = np.asarray(Vexc)
        U1 = Vexc_arr[type3, 0] if Vexc_arr.ndim == 2 else Vexc_arr[type3]
        V = np.abs(U1)
        theta = np.angle(U1)

        L = Efd0 + mu * k * V * np.cos(delta - theta)

        Pexc0[type3, 0] = Pexc[type3, 0]
        Pexc0[type3, 1] = Tv
        Pexc0[type3, 2] = mu
        Pexc0[type3, 3] = k
        Pexc0[type3, 4] = Efd_min
        Pexc0[type3, 5] = Efd_max
        Pexc0[type3, 6] = L
        Xexc0[type3, 0] = Efd0

    if type4.size:
        Xexc0[type4, 0] = Xexc[type4, 0]

    return Xexc0, Pexc0


def governor_init(Xgov, Pgov, Vgov, govtype):
    """Return ``(Xgov0, Pgov0)`` — initial governor state and parameters."""
    Xgov = np.asarray(Xgov, dtype=float)
    if Xgov.ndim == 1:
        Xgov = Xgov.reshape(-1, 1)
    ngen, c = Xgov.shape
    Xgov0 = np.zeros((ngen, max(c, 4)))
    pcols = Pgov.shape[1]
    Pgov0 = np.zeros((Pgov.shape[0], pcols + 2))
    govtype = np.asarray(govtype).ravel()

    type1 = np.flatnonzero(govtype == 1)
    type2 = np.flatnonzero(govtype == 2)

    if type1.size:
        Xgov0[type1, 0] = Xgov[type1, 0]

    if type2.size:
        Pm0 = Xgov[type2, 0]
        K = Pgov[type2, 1]
        T1 = Pgov[type2, 2]
        T2 = Pgov[type2, 3]
        T3 = Pgov[type2, 4]
        Pup = Pgov[type2, 5]
        Pdown = Pgov[type2, 6]
        Pmax = Pgov[type2, 7]
        Pmin = Pgov[type2, 8]

        omega0 = np.asarray(Vgov[type2]).ravel()

        zz0 = Pm0
        PP0 = Pm0

        P0 = K * (2.0 * np.pi * _freq.freq - omega0)
        xx0 = T1 * (1.0 - T2 / T1) * (2.0 * np.pi * _freq.freq - omega0)

        Xgov0[type2, 0] = Pm0
        Xgov0[type2, 1] = P0
        Xgov0[type2, 2] = xx0
        Xgov0[type2, 3] = zz0

        Pgov0[type2, 0] = Pgov[type2, 0]
        Pgov0[type2, 1] = K
        Pgov0[type2, 2] = T1
        Pgov0[type2, 3] = T2
        Pgov0[type2, 4] = T3
        Pgov0[type2, 5] = Pup
        Pgov0[type2, 6] = Pdown
        Pgov0[type2, 7] = Pmax
        Pgov0[type2, 8] = Pmin
        Pgov0[type2, 9] = PP0

    return Xgov0, Pgov0


def pss_init(Ppss, psstype):
    """Return ``(Xpss0, Ppss0)`` — initial PSS state and parameters."""
    Ppss = np.asarray(Ppss, dtype=float)
    if Ppss.size == 0:
        return np.zeros((0, 1)), Ppss
    if Ppss.ndim == 1:
        Ppss = Ppss.reshape(-1, 1)
    ngen = Ppss.shape[0]
    Xpss0 = np.zeros((ngen, 1))
    Ppss0 = Ppss.copy()
    psstype = np.asarray(psstype).ravel()
    type3 = np.flatnonzero(psstype == 3)
    if type3.size:
        Xpss0[type3, 0] = 0.0
    return Xpss0, Ppss0


__all__ = ["generator_init", "exciter_init", "governor_init", "pss_init"]
