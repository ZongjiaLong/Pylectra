"""pandapower power-flow plugin.

Wraps :func:`pandapower.converter.pypower.from_ppc` + ``runpp`` and converts
results back to the legacy ``(baseMVA, bus, gen, branch, success, et)`` tuple
that the rest of ``pylectra`` (and the legacy ``rundyn`` loop) expects.

The conversion is loss-less for the columns we touch (``VM, VA, QG``); the
remaining ``mpc`` columns are passed through unchanged.

This plugin is **optional**: pandapower is a heavy dependency, so the import is
lazy.  Importing this module without pandapower installed will raise at
``solve()`` time, not at registration time.
"""
from __future__ import annotations

import time
from copy import deepcopy
from typing import Optional, TYPE_CHECKING

import numpy as np

from pylectra.interfaces.power_flow import PowerFlowSolver
from pylectra.registry import register

from pylectra.core.idx import idx_bus, idx_brch, idx_gen

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase


def _import_pandapower():
    try:
        import pandapower as pp  # type: ignore
        from pandapower.converter.pypower import from_ppc  # type: ignore
        return pp, from_ppc
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "pandapower is not installed.  Install it with `pip install pandapower`"
            " to use the `power_flow.pandapower` plugin."
        ) from e


@register("power_flow", "pandapower")
class PandapowerPowerFlow(PowerFlowSolver):
    """AC power flow via pandapower's `runpp` (Newton-Raphson by default).

    Options accepted (all optional):

    * ``algorithm`` (str): ``nr`` (default), ``bfsw``, ``gs``, ``fdbx``, ``fdxb``.
    * ``tolerance_mva`` (float): convergence tolerance (default 1e-8).
    * ``max_iteration`` (int): maximum iterations (default 10).
    * ``f_hz`` (float): system frequency for the converter (default 60).
    * ``enforce_q_lims`` (bool): enforce reactive power limits (default False).
    * ``init`` (str): ``flat`` / ``dc`` / ``results`` initial guess.

    The case is mutated in-place to internal 0-based numbering (mirroring
    :class:`NewtonPowerFlow`) so the rest of ``rundyn``/the engine can index
    arrays directly.
    """

    def solve(
        self,
        case: "NetworkCase",
        options: Optional[dict] = None,
    ) -> "NetworkCase":
        pp, from_ppc = _import_pandapower()
        opts = options or {}

        # Build a ppc dict pandapower expects.  It needs ``baseMVA, bus, gen,
        # branch`` and ignores the rest.
        ppc = {
            "version": str(case.mpc.get("version", "2")),
            "baseMVA": float(case.baseMVA),
            "bus": np.asarray(case.bus, dtype=float).copy(),
            "gen": np.asarray(case.gen, dtype=float).copy(),
            "branch": np.asarray(case.branch, dtype=float).copy(),
        }
        # Some pp validators expect at least one optional generator-cost row,
        # which we lift verbatim if present.
        if "gencost" in case.mpc:
            ppc["gencost"] = np.asarray(case.mpc["gencost"], dtype=float).copy()

        f_hz = float(opts.get("f_hz", 60.0))
        net = from_ppc(ppc, f_hz=f_hz)

        run_kwargs = {
            "algorithm": str(opts.get("algorithm", "nr")),
            "tolerance_mva": float(opts.get("tolerance_mva", 1e-8)),
            "max_iteration": int(opts.get("max_iteration", 10)),
            "enforce_q_lims": bool(opts.get("enforce_q_lims", False)),
            "init": str(opts.get("init", "flat")),
            "calculate_voltage_angles": True,
        }

        tic = time.time()
        success = True
        try:
            pp.runpp(net, **run_kwargs)
        except Exception:  # pp raises on non-convergence
            success = bool(net.get("converged", False))
            if not success:
                # leave bus/gen unchanged; caller handles failure
                case.success = False
                case.mpc["success"] = False
                case.mpc["et"] = time.time() - tic
                _adjust_to_internal(case)
                return case
        et = time.time() - tic
        success = success and bool(net.converged)

        # ---- write results back into mpc arrays ----------------------------
        (_, _, _, _, BUS_I, _, PD, QD, GS, BS, _, VM, VA, BASE_KV, _,
         VMAX, VMIN, _, _, _, _) = idx_bus()
        (GEN_BUS, PG, QG, *_rest_g) = idx_gen()

        # pandapower preserves bus order (one row in res_bus per bus row in
        # ppc) when we use from_ppc.  Indexing is by net.bus.index which
        # corresponds row-for-row.
        res_bus = net.res_bus.sort_index()
        case.bus[:, VM] = res_bus["vm_pu"].to_numpy()
        case.bus[:, VA] = res_bus["va_degree"].to_numpy()

        # Generators: pp returns per-element results.  We need to map them
        # back to the original gen rows.  The ``ext_grid`` slack is a
        # separate table.
        n_gen = case.gen.shape[0]
        Pg = np.asarray(case.gen[:, PG], dtype=float).copy()
        Qg = np.asarray(case.gen[:, QG], dtype=float).copy()
        # Match by bus number.
        if not net.gen.empty:
            for _, row in net.gen.iterrows():
                bus_ext = int(row["bus"])
                # pandapower stores 0-based indices internally; original ppc
                # bus IDs are MATPOWER 1-based.  Find the matching gen row.
                bus_id = bus_ext + 1  # convert pp internal back to MATPOWER 1-based
                idx = np.where(case.gen[:, GEN_BUS].astype(int) == bus_id)[0]
                if idx.size:
                    Pg[idx[0]] = float(net.res_gen.loc[row.name, "p_mw"])
                    Qg[idx[0]] = float(net.res_gen.loc[row.name, "q_mvar"])
        if not net.ext_grid.empty:
            for _, row in net.ext_grid.iterrows():
                bus_ext = int(row["bus"])
                bus_id = bus_ext + 1
                idx = np.where(case.gen[:, GEN_BUS].astype(int) == bus_id)[0]
                if idx.size:
                    Pg[idx[0]] = float(net.res_ext_grid.loc[row.name, "p_mw"])
                    Qg[idx[0]] = float(net.res_ext_grid.loc[row.name, "q_mvar"])
        case.gen[:, PG] = Pg
        case.gen[:, QG] = Qg

        case.success = success
        case.mpc["success"] = success
        case.mpc["et"] = et

        _adjust_to_internal(case)
        return case


def _adjust_to_internal(case: "NetworkCase") -> None:
    """Subtract 1 from bus IDs (mirror legacy rundyn convention).

    Idempotent guard: if the smallest bus ID is already 0 we assume internal
    numbering is in effect and leave the arrays alone.
    """
    (_, _, _, _, BUS_I, *_b) = idx_bus()
    (F_BUS, T_BUS, *_) = idx_brch()
    (GEN_BUS, *_g) = idx_gen()
    if case.bus[:, BUS_I].min() <= 0:
        return  # already internal
    case.bus[:, BUS_I] -= 1
    case.branch[:, F_BUS] -= 1
    case.branch[:, T_BUS] -= 1
    case.gen[:, GEN_BUS] -= 1
