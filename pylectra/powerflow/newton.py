"""Newton power-flow plugin (native solver stack).

Builds Y-bus / S-bus, runs the Newton iteration, and writes the post-
solve state back via :func:`pfsoln_partial`. The MATPOWER ``ext2int``
state-management helper is kept for now (it manages out-of-service buses
and gen reordering — Phase 5 territory) but the heavy numerics are now
fully native.
"""
from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

import numpy as np

from pylectra.interfaces.power_flow import PowerFlowSolver
from pylectra.registry import register
from pylectra.core.idx import idx_bus, idx_brch, idx_gen
from pylectra.network.ybus import make_ybus
from pylectra.powerflow._solver import (
    NewtonOptions, make_sbus, bus_types, newton_solve, pfsoln_partial,
)
from pylectra.powerflow._extint import ext2int, int2ext

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase


@register("power_flow", "newton")
class NewtonPowerFlow(PowerFlowSolver):
    """Newton-Raphson AC power flow.

    Options accepted (all optional):

    * ``verbose``: int, default 0.
    * ``tol``:      float, default 1e-8.
    * ``max_it``:   int, default 10.
    """

    def solve(
        self,
        case: "NetworkCase",
        options: Optional[dict] = None,
    ) -> "NetworkCase":
        opts_in = options or {}
        opts = NewtonOptions(
            tol=float(opts_in.get("tol", 1e-8)),
            max_it=int(opts_in.get("max_it", 10)),
            verbose=int(opts_in.get("verbose", 0)),
        )
        t0 = time.time()

        mpc = case.mpc

        # Pad branch with PF/QF/PT/QT columns if missing (matches legacy runpf).
        (_F_BUS, _T_BUS, *_rest_brch) = idx_brch()
        QT = idx_brch()[14]
        if mpc["branch"].shape[1] < QT + 1:
            pad = np.zeros((mpc["branch"].shape[0], QT + 1 - mpc["branch"].shape[1]))
            mpc["branch"] = np.hstack([mpc["branch"], pad])

        mpc = ext2int(mpc)
        baseMVA = mpc["baseMVA"]
        bus = mpc["bus"]
        gen = mpc["gen"]
        branch = mpc["branch"]

        ref, pv, pq = bus_types(bus, gen)

        (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, VA,
         BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN) = idx_bus()
        (GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, *_) = idx_gen()

        on = np.flatnonzero(gen[:, GEN_STATUS] > 0)
        gbus = gen[on, GEN_BUS].astype(int)

        V0 = bus[:, VM] * np.exp(1j * np.pi / 180.0 * bus[:, VA])
        V0[gbus] = gen[on, VG] / np.abs(V0[gbus]) * V0[gbus]

        Ybus, Yf, Yt = make_ybus(baseMVA, bus, branch)
        Sbus = make_sbus(baseMVA, bus, gen)

        ref_scalar = ref[0] if hasattr(ref, "__len__") else ref
        V, success, _iters = newton_solve(Ybus, Sbus, V0, ref_scalar, pv, pq, opts)

        bus, gen, branch = pfsoln_partial(baseMVA, bus, gen, branch,
                                          Ybus, Yf, Yt, V, ref, pv, pq)

        mpc["et"] = time.time() - t0
        mpc["success"] = bool(success)
        mpc["bus"] = bus
        mpc["gen"] = gen
        mpc["branch"] = branch

        results = int2ext(mpc)

        off_gen = results["order"]["gen"]["status"].get("off", np.array([], dtype=int))
        if off_gen.size:
            results["gen"][off_gen, PG] = 0.0
            results["gen"][off_gen, QG] = 0.0
        off_br = results["order"]["branch"]["status"].get("off", np.array([], dtype=int))
        if off_br.size:
            (F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C,
             TAP, SHIFT, BR_STATUS, PF, QF, PT, QT_, *_rest_br) = idx_brch()
            results["branch"][off_br, PF] = 0.0
            results["branch"][off_br, QF] = 0.0
            results["branch"][off_br, PT] = 0.0
            results["branch"][off_br, QT_] = 0.0

        # Mirror the rundyn 1-based -> 0-based bus number adjustment.
        results["bus"][:, BUS_I] -= 1
        results["branch"][:, idx_brch()[0]] -= 1
        results["branch"][:, idx_brch()[1]] -= 1
        results["gen"][:, GEN_BUS] -= 1

        case.mpc["baseMVA"] = results["baseMVA"]
        case.mpc["bus"] = results["bus"]
        case.mpc["gen"] = results["gen"]
        case.mpc["branch"] = results["branch"]
        case.success = bool(success)
        case.mpc["success"] = case.success
        case.mpc["et"] = results.get("et", 0.0)
        return case
