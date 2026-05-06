"""Typed bundle of time-domain simulation outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

import numpy as np

if TYPE_CHECKING:
    from pylectra.interfaces.small_signal import SmallSignalResult as _SmallSignalResult


@dataclass
class SimulationResult:
    """Output of a single time-domain simulation.

    Mirrors the dict returned by :func:`rundyn` but with explicit attribute
    access and helpful summary methods.

    Time-series shapes
    ------------------
    * ``Time``       — ``(n,)``
    * ``Voltages``   — ``(n, n_bus)`` complex
    * ``Angles``     — ``(n, n_gen)`` degrees
    * ``Speeds``     — ``(n, n_gen)`` p.u. (omega / 2*pi*freq)
    * ``Eq_trs``     — ``(n, n_gen)``
    * ``Ed_trs``     — ``(n, n_gen)``
    * ``Efds``       — ``(n, n_gen)``
    * ``Tes``        — ``(n, n_gen)``
    * ``TM``         — ``(n, n_gen)``
    * ``Vss``        — ``(n, n_gen)``
    * ``Stepsize``   — ``(n,)``
    * ``Errest``     — ``(n,)``
    """

    Time: np.ndarray
    Voltages: np.ndarray
    Angles: np.ndarray
    Speeds: np.ndarray
    Eq_trs: np.ndarray
    Ed_trs: np.ndarray
    Efds: np.ndarray
    Tes: np.ndarray
    TM: np.ndarray
    Vss: np.ndarray
    Stepsize: np.ndarray
    Errest: np.ndarray
    simulation_time: float = 0.0
    pf_success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional small-signal result attached after equilibrium analysis.
    small_signal: Optional["_SmallSignalResult"] = None

    @classmethod
    def from_legacy_dict(cls, d: dict) -> "SimulationResult":
        """Build from the dict returned by :func:`rundyn`."""
        return cls(
            Time=d["Time"],
            Voltages=d["Voltages"],
            Angles=d["Angles"],
            Speeds=d["Speeds"],
            Eq_trs=d["Eq_trs"],
            Ed_trs=d["Ed_trs"],
            Efds=d["Efds"],
            Tes=d["Tes"],
            TM=d["TM"],
            Vss=d["Vss"],
            Stepsize=d["Stepsize"],
            Errest=d["Errest"],
            simulation_time=float(d.get("simulationtime", 0.0)),
            pf_success=True,
        )

    @classmethod
    def from_equilibrium_only(
        cls,
        eq,
        ss_result=None,
        simulation_time: float = 0.0,
    ) -> "SimulationResult":
        """Build a minimal result when only the equilibrium (no integration) is needed.

        Used when ``skip_integration=True`` is set in the config.  The time axis
        contains a single point (t=0) holding the equilibrium snapshot.

        Parameters
        ----------
        eq :
            :class:`pylectra.engine.equilibrium.Equilibrium` — must have ``pf_success=True``.
        ss_result :
            Optional :class:`pylectra.interfaces.small_signal.SmallSignalResult`.
        simulation_time :
            Wall-clock seconds spent on equilibrium computation.
        """
        rhs = eq.rhs
        layout = eq.layout
        y0 = eq.y0
        ngen = layout.ngen
        nbus = eq.network.U_init.size

        # Force one RHS evaluation to populate _last_U / _last_Vgen.
        rhs(0.0, y0)
        U0 = rhs._last_U
        Vgen0 = rhs._last_Vgen

        Xgen0, Xexc0, Xgov0 = layout.unpack(y0)

        from pylectra.core import freq as _f
        freq = float(_f.freq)

        return cls(
            Time=np.array([0.0]),
            Voltages=U0[np.newaxis, :],
            Angles=Xgen0[:, 0:1].T * 180.0 / np.pi,
            Speeds=Xgen0[:, 1:2].T / (2.0 * np.pi * freq),
            Eq_trs=Xgen0[:, 2:3].T,
            Ed_trs=Xgen0[:, 3:4].T,
            Efds=Xexc0[:, 0:1].T,
            Tes=Vgen0[:, 2:3].T,
            TM=Xgov0[:, 0:1].T,
            Vss=np.zeros((1, ngen)),
            Stepsize=np.array([0.0]),
            Errest=np.array([0.0]),
            simulation_time=simulation_time,
            pf_success=True,
            metadata={"equilibrium_only": True,
                      **eq.diagnostics},
            small_signal=ss_result,
        )

    @classmethod
    def failed_powerflow(cls, n_bus: int = 0, n_gen: int = 0,
                         reason: str = "") -> "SimulationResult":
        """Empty result tagged with ``pf_success=False``."""
        meta: Dict[str, Any] = {}
        if reason:
            meta["failure_reason"] = reason
        return cls(
            Time=np.zeros(0),
            Voltages=np.zeros((0, n_bus), dtype=complex),
            Angles=np.zeros((0, n_gen)),
            Speeds=np.zeros((0, n_gen)),
            Eq_trs=np.zeros((0, n_gen)),
            Ed_trs=np.zeros((0, n_gen)),
            Efds=np.zeros((0, n_gen)),
            Tes=np.zeros((0, n_gen)),
            TM=np.zeros((0, n_gen)),
            Vss=np.zeros((0, n_gen)),
            Stepsize=np.zeros(0),
            Errest=np.zeros(0),
            pf_success=False,
            metadata=meta,
        )

    @property
    def n_steps(self) -> int:
        return int(self.Time.shape[0])

    @property
    def n_bus(self) -> int:
        return int(self.Voltages.shape[1]) if self.Voltages.ndim == 2 else 0

    @property
    def n_gen(self) -> int:
        return int(self.Angles.shape[1]) if self.Angles.ndim == 2 else 0

    @property
    def voltage_magnitude(self) -> np.ndarray:
        """``|V|`` over time, shape ``(n, n_bus)``."""
        return np.abs(self.Voltages)

    @property
    def max_angle_deviation_deg(self) -> Optional[float]:
        """Max absolute deviation from system mean angle (post-event proxy)."""
        if self.n_gen == 0 or self.n_steps == 0:
            return None
        rel = self.Angles - self.Angles.mean(axis=1, keepdims=True)
        return float(np.max(np.abs(rel)))
