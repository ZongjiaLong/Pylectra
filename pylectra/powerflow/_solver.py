"""Native AC Newton power-flow internals.

Pure ``numpy`` / ``scipy.sparse`` ports of:
* ``makeSbus`` (complex bus power injection vector)
* ``bustypes`` (REF / PV / PQ index arrays)
* ``dSbus_dV`` (sparse Jacobian of bus injections)
* ``newton_solve`` (one Newton power-flow solve — no qlim, no printing)

Bit-identical to the legacy versions, validated by
``tests/numerical/test_newton_parity.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix, diags, issparse, hstack as sphstack, vstack as spvstack
from scipy.sparse.linalg import spsolve

from pylectra.core.idx import idx_bus, idx_gen


@dataclass
class NewtonOptions:
    """Replaces the MATPOWER 116-element ``mpoption`` vector.

    Only the fields actually consulted by ``newton_solve`` are exposed —
    the legacy default of ``tol=1e-8``, ``max_it=10``, ``verbose=0``.
    """

    tol: float = 1e-8
    max_it: int = 10
    verbose: int = 0


def make_sbus(baseMVA, bus, gen):
    """Return ``Sbus`` — complex bus power injection vector (``ndarray``)."""
    (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM,
     VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN) = idx_bus()
    (GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, *_rest) = idx_gen()

    on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
    gbus = gen[on, GEN_BUS].astype(int)

    nb = bus.shape[0]
    ngon = on.size

    Cg = csr_matrix((np.ones(ngon), (gbus, np.arange(ngon))), shape=(nb, ngon))
    Sg = gen[on, PG] + 1j * gen[on, QG]
    Sd = bus[:, PD] + 1j * bus[:, QD]
    Sbus = (Cg @ Sg - Sd) / baseMVA
    return np.asarray(Sbus).ravel()


def bus_types(bus, gen):
    """Return ``(ref, pv, pq)`` 0-based index arrays."""
    (PQ, PV, REF, *_rest_b) = idx_bus()[:4]
    BUS_TYPE = idx_bus()[5]
    (GEN_BUS, _PG, _QG, _QMAX, _QMIN, _VG, _MBASE, GEN_STATUS, *_rest_g) = idx_gen()

    nb = bus.shape[0]
    ng = gen.shape[0]
    rows = gen[:, GEN_BUS].astype(int)
    cols = np.arange(ng)
    data = (gen[:, GEN_STATUS] > 0).astype(float)
    Cg = csr_matrix((data, (rows, cols)), shape=(nb, ng))
    bus_gen_status = np.asarray(Cg.dot(np.ones(ng))).flatten() > 0

    bt = bus[:, BUS_TYPE]
    ref = np.flatnonzero((bt == REF) & bus_gen_status)
    pv = np.flatnonzero((bt == PV) & bus_gen_status)
    pq = np.flatnonzero((bt == PQ) | (~bus_gen_status))

    if ref.size == 0:
        ref = pv[:1]
        pv = pv[1:]

    return ref, pv, pq


def dSbus_dV(Ybus, V):
    """Return ``(dSbus_dVm, dSbus_dVa)`` — sparse Jacobian blocks."""
    n = V.size
    Ibus = Ybus @ V
    Vnorm = V / np.abs(V)

    if issparse(Ybus):
        diagV = diags(V, 0, shape=(n, n), format="csr")
        diagIbus = diags(Ibus, 0, shape=(n, n), format="csr")
        diagVnorm = diags(Vnorm, 0, shape=(n, n), format="csr")
        dSbus_dVm = diagV @ (Ybus @ diagVnorm).conjugate() + diagIbus.conjugate() @ diagVnorm
        dSbus_dVa = 1j * diagV @ (diagIbus - Ybus @ diagV).conjugate()
    else:
        diagV = np.diag(V)
        diagIbus = np.diag(Ibus)
        diagVnorm = np.diag(Vnorm)
        dSbus_dVm = diagV @ np.conj(Ybus @ diagVnorm) + np.conj(diagIbus) @ diagVnorm
        dSbus_dVa = 1j * diagV @ np.conj(diagIbus - Ybus @ diagV)
    return dSbus_dVm, dSbus_dVa


def newton_solve(Ybus, Sbus, V0, ref, pv, pq, opts: NewtonOptions | None = None):
    """Run the AC Newton iteration. Returns ``(V, converged, iterations)``."""
    if opts is None:
        opts = NewtonOptions()
    tol = float(opts.tol)
    max_it = int(opts.max_it)
    verbose = int(opts.verbose)

    converged = 0
    i = 0
    V = V0.astype(complex).copy()
    Va = np.angle(V)
    Vm = np.abs(V)

    npv = pv.size
    npq = pq.size
    j1, j2 = 0, npv
    j3, j4 = j2, j2 + npq
    j5, j6 = j4, j4 + npq

    pvpq = np.concatenate([pv, pq])

    mis = V * np.conj(Ybus @ V) - Sbus
    F = np.concatenate([mis[pvpq].real, mis[pq].imag])

    if np.linalg.norm(F, np.inf) < tol:
        converged = 1

    while not converged and i < max_it:
        i += 1
        dSbus_dVm_, dSbus_dVa_ = dSbus_dV(Ybus, V)

        if issparse(dSbus_dVa_):
            j11 = dSbus_dVa_[pvpq, :][:, pvpq].real
            j12 = dSbus_dVm_[pvpq, :][:, pq].real
            j21 = dSbus_dVa_[pq, :][:, pvpq].imag
            j22 = dSbus_dVm_[pq, :][:, pq].imag
            J = spvstack([sphstack([j11, j12]), sphstack([j21, j22])], format="csr")
        else:
            j11 = dSbus_dVa_[np.ix_(pvpq, pvpq)].real
            j12 = dSbus_dVm_[np.ix_(pvpq, pq)].real
            j21 = dSbus_dVa_[np.ix_(pq, pvpq)].imag
            j22 = dSbus_dVm_[np.ix_(pq, pq)].imag
            J = np.block([[j11, j12], [j21, j22]])

        if issparse(J):
            dx = -spsolve(J.tocsc(), F)
        else:
            dx = -np.linalg.solve(J, F)

        if npv:
            Va[pv] = Va[pv] + dx[j1:j2]
        if npq:
            Va[pq] = Va[pq] + dx[j3:j4]
            Vm[pq] = Vm[pq] + dx[j5:j6]
        V = Vm * np.exp(1j * Va)
        Vm = np.abs(V)
        Va = np.angle(V)

        mis = V * np.conj(Ybus @ V) - Sbus
        F = np.concatenate([mis[pv].real, mis[pq].real, mis[pq].imag])

        if np.linalg.norm(F, np.inf) < tol:
            converged = 1

    if verbose and converged:
        print(f"Newton's method power flow converged in {i} iterations.")
    elif verbose:
        print(f"Newton's method power flow did not converge in {i} iterations.")

    return V, converged, i


def pfsoln_partial(baseMVA, bus0, gen0, branch0, Ybus, Yf, Yt, V, ref, pv, pq):
    """Native ``pfsoln`` — write Vm/Va, gen Q, swing-bus P, and branch flows back.

    Faithful port of the legacy ``pfsoln`` (no behavioural change); the
    ``_partial`` suffix only signals that this function is the post-Newton
    state-update step of the legacy ``runpf``, not the full ``runpf``
    pipeline.
    """
    (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM,
     VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN) = idx_bus()
    (GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, *_rest) = idx_gen()
    from pylectra.core.idx import idx_brch
    (F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C,
     TAP, SHIFT, BR_STATUS, PF, QF, PT, QT, *_rest_br) = idx_brch()

    bus = bus0.copy()
    gen = gen0.copy()
    branch = branch0.copy()

    bus[:, VM] = np.abs(V)
    bus[:, VA] = np.angle(V) * 180.0 / np.pi

    on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
    gbus = gen[on, GEN_BUS].astype(int)

    ref_arr = np.atleast_1d(ref)
    refgen = np.flatnonzero(gbus == ref_arr[0])

    Sg = V[gbus] * np.conj(np.asarray(Ybus[gbus, :] @ V).ravel())

    gen[:, QG] = 0.0
    gen[on, QG] = Sg.imag * baseMVA + bus[gbus, QD]

    if on.size > 1:
        nb = bus.shape[0]
        ngon = on.size
        Cg = csr_matrix((np.ones(ngon), (np.arange(ngon), gbus)), shape=(ngon, nb))

        ngg = np.asarray(Cg @ np.asarray(Cg.sum(axis=0)).ravel()).ravel()
        gen[on, QG] = gen[on, QG] / ngg

        Cmin = csr_matrix((gen[on, QMIN], (np.arange(ngon), gbus)), shape=(ngon, nb))
        Cmax = csr_matrix((gen[on, QMAX], (np.arange(ngon), gbus)), shape=(ngon, nb))
        Qg_tot = np.asarray(Cg.T @ gen[on, QG]).ravel()
        Qg_min = np.asarray(Cmin.sum(axis=0)).ravel()
        Qg_max = np.asarray(Cmax.sum(axis=0)).ravel()
        ig = np.flatnonzero(np.asarray(Cg @ Qg_min).ravel() == np.asarray(Cg @ Qg_max).ravel())
        Qg_save = gen[on[ig], QG].copy()
        eps = np.finfo(float).eps
        scale = np.asarray(Cg @ ((Qg_tot - Qg_min) / (Qg_max - Qg_min + eps))).ravel()
        gen[on, QG] = gen[on, QMIN] + scale * (gen[on, QMAX] - gen[on, QMIN])
        gen[on[ig], QG] = Qg_save

    gen[on[refgen[0]], PG] = Sg[refgen[0]].real * baseMVA + bus[ref_arr[0], PD]
    if refgen.size > 1:
        gen[on[refgen[0]], PG] -= np.sum(gen[on[refgen[1:]], PG])

    out = np.flatnonzero(branch[:, BR_STATUS] == 0)
    br = np.flatnonzero(branch[:, BR_STATUS])
    f_idx = branch[br, F_BUS].astype(int)
    t_idx = branch[br, T_BUS].astype(int)
    Sf = V[f_idx] * np.conj(np.asarray(Yf[br, :] @ V).ravel()) * baseMVA
    St = V[t_idx] * np.conj(np.asarray(Yt[br, :] @ V).ravel()) * baseMVA
    branch[br, PF] = Sf.real
    branch[br, QF] = Sf.imag
    branch[br, PT] = St.real
    branch[br, QT] = St.imag
    branch[out, PF] = 0.0
    branch[out, QF] = 0.0
    branch[out, PT] = 0.0
    branch[out, QT] = 0.0

    return bus, gen, branch


__all__ = [
    "NewtonOptions", "make_sbus", "bus_types", "dSbus_dV",
    "newton_solve", "pfsoln_partial",
]
