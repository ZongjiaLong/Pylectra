"""Power-flow-only result container and bridge to ``SimulationResult``.

The :class:`PowerFlowSnapshot` captures the post-PF state of a network
(VM/VA on every bus, PG/QG on every generator, PF/QF/PT/QT on every
branch) for the ``batch_pf`` runner.  :func:`to_simulation_result`
wraps a snapshot in a single-step :class:`SimulationResult` so the
existing ``pf_converged`` and ``voltage_range`` filters can be reused
without modification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np

from pylectra.core.case import NetworkCase
from pylectra.core.idx import idx_brch, idx_bus, idx_gen
from pylectra.core.result import SimulationResult


@dataclass
class PowerFlowSnapshot:
    """Compact snapshot of one converged (or failed) power-flow solution."""

    bus: np.ndarray            # full mpc['bus'], includes VM/VA
    gen: np.ndarray            # full mpc['gen'], includes PG/QG
    branch: np.ndarray         # full mpc['branch'], includes PF/QF/PT/QT
    baseMVA: float
    success: bool
    et: float                  # PF wall-clock seconds
    n_bus: int
    n_gen: int
    metadata: Dict[str, Any] = field(default_factory=dict)


def from_solved_case(case: NetworkCase, et: float) -> PowerFlowSnapshot:
    """Capture the post-solve state of a :class:`NetworkCase`."""
    return PowerFlowSnapshot(
        bus=np.array(case.mpc["bus"], copy=True),
        gen=np.array(case.mpc["gen"], copy=True),
        branch=np.array(case.mpc["branch"], copy=True),
        baseMVA=float(case.mpc["baseMVA"]),
        success=bool(case.success),
        et=float(et),
        n_bus=int(case.n_bus),
        n_gen=int(case.n_gen),
    )


def to_simulation_result(snap: PowerFlowSnapshot) -> SimulationResult:
    """Wrap a snapshot in a single-step :class:`SimulationResult`.

    The resulting object satisfies the contracts of ``pf_converged``
    (uses ``pf_success``) and ``voltage_range`` (uses ``voltage_magnitude``,
    a ``(1, n_bus)`` array).  Filters that need full time-series fields
    (``angle_stability``, ``simulation_completed``) become no-ops because
    ``Angles``/``Time`` carry no informative data here, but they already
    short-circuit when ``n_steps == 0`` or ``stoptime`` is missing.
    """
    if not snap.success:
        return SimulationResult.failed_powerflow(
            n_bus=snap.n_bus, n_gen=snap.n_gen,
            reason="power flow did not converge",
        )

    VM = idx_bus()[11]
    VA = idx_bus()[12]
    vm = snap.bus[:, VM]
    va_rad = snap.bus[:, VA] * np.pi / 180.0
    voltages = (vm * np.exp(1j * va_rad)).reshape(1, -1)

    return SimulationResult(
        Time=np.array([0.0]),
        Voltages=voltages,
        Angles=np.zeros((1, snap.n_gen)),
        Speeds=np.zeros((1, snap.n_gen)),
        Eq_trs=np.zeros((1, snap.n_gen)),
        Ed_trs=np.zeros((1, snap.n_gen)),
        Efds=np.zeros((1, snap.n_gen)),
        Tes=np.zeros((1, snap.n_gen)),
        TM=np.zeros((1, snap.n_gen)),
        Vss=np.zeros((1, snap.n_gen)),
        Stepsize=np.array([0.0]),
        Errest=np.array([0.0]),
        simulation_time=snap.et,
        pf_success=True,
        metadata={"pf_only": True, **snap.metadata},
    )
