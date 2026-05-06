"""Native ``makeYbus`` and ``AugYbus`` (sparse admittance + LU factorisation).

Bus indexing convention: assumes 0-based contiguous bus numbering
(BUS_I = 0..nb-1, F_BUS/T_BUS likewise 0-based) — matches the post-``ext2int``
state of the legacy code.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix, diags
from scipy.sparse.linalg import splu

from pylectra.core.idx import idx_bus, idx_brch


def make_ybus(baseMVA, bus=None, branch=None):
    """Return ``(Ybus, Yf, Yt)`` as CSC sparse matrices.

    May be called with a single ``mpc`` dict (then ``bus``/``branch`` are
    pulled from it) or with the three explicit arguments.
    """
    if bus is None and branch is None:
        mpc = baseMVA
        baseMVA = mpc["baseMVA"]
        bus = mpc["bus"]
        branch = mpc["branch"]

    nb = bus.shape[0]
    nl = branch.shape[0]

    (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM,
     VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN) = idx_bus()
    (F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C,
     TAP, SHIFT, BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST,
     ANGMIN, ANGMAX, MU_ANGMIN, MU_ANGMAX) = idx_brch()

    if np.any(bus[:, BUS_I].astype(int) != np.arange(nb)):
        raise ValueError("make_ybus: buses must appear in order by bus number")

    stat = branch[:, BR_STATUS]
    Ys = stat / (branch[:, BR_R] + 1j * branch[:, BR_X])
    Bc = stat * branch[:, BR_B]
    tap = np.ones(nl, dtype=complex)
    nz = branch[:, TAP] != 0
    tap[nz] = branch[nz, TAP]
    tap = tap * np.exp(1j * np.pi / 180.0 * branch[:, SHIFT])

    Ytt = Ys + 1j * Bc / 2.0
    Yff = Ytt / (tap * np.conj(tap))
    Yft = -Ys / np.conj(tap)
    Ytf = -Ys / tap

    Ysh = (bus[:, GS] + 1j * bus[:, BS]) / baseMVA

    f = branch[:, F_BUS].astype(int)
    t = branch[:, T_BUS].astype(int)

    rows = np.concatenate([np.arange(nl), np.arange(nl)])
    cols_f = np.concatenate([f, t])
    Yf = csr_matrix((np.concatenate([Yff, Yft]), (rows, cols_f)), shape=(nl, nb))
    Yt = csr_matrix((np.concatenate([Ytf, Ytt]), (rows, cols_f)), shape=(nl, nb))

    Cf = csr_matrix((np.ones(nl), (np.arange(nl), f)), shape=(nl, nb))
    Ct = csr_matrix((np.ones(nl), (np.arange(nl), t)), shape=(nl, nb))

    Ybus = (Cf.T.tocsr() @ Yf + Ct.T.tocsr() @ Yt
            + csr_matrix((Ysh, (np.arange(nb), np.arange(nb))), shape=(nb, nb)))

    return Ybus.tocsc(), Yf.tocsc(), Yt.tocsc()


def aug_ybus(baseMVA, bus, branch, xd_tr, gbus, P, Q, U0):
    """Augment ``Ybus`` with constant-impedance loads + generator transient
    reactance, return ``(lu, None, None)``.

    Two trailing ``None``s preserve the legacy ``[Ly, Uy, Py]`` tuple shape
    consumed by :func:`solve_network`.
    """
    Ybus, _, _ = make_ybus(baseMVA, bus, branch)

    yload = (P - 1j * Q) / (np.abs(U0) ** 2)

    nb = Ybus.shape[0]
    ygen = np.zeros(nb, dtype=complex)
    ygen[gbus] = 1.0 / (1j * xd_tr)

    Y = (Ybus + diags(ygen + yload, 0, shape=(nb, nb), format="csc")).tocsc()
    lu = splu(Y)
    return lu, None, None
