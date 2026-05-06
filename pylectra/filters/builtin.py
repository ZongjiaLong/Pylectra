"""Builtin sample filters.

* :class:`PFConvergedFilter` — reject scenarios whose initial PF diverged.
* :class:`VoltageRangeFilter` — reject samples that ever leave [vmin, vmax].
* :class:`AngleStabilityFilter` — reject samples whose max generator angle
  deviation exceeds a threshold (a simple stability proxy).
* :class:`SimulationCompletedFilter` — reject samples that didn't reach
  ``stoptime`` (e.g. solver gave up).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from pylectra.interfaces.filter import FilterDecision, SampleFilter
from pylectra.registry import register

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase
    from pylectra.core.result import SimulationResult
    from pylectra.interfaces.scenario import Scenario


@register("filter", "pf_converged")
@dataclass
class PFConvergedFilter(SampleFilter):
    """Pass only when the initial steady-state PF converged."""

    def judge(self, result: "SimulationResult", scenario: "Scenario", case: "NetworkCase") -> FilterDecision:
        if not result.pf_success:
            return FilterDecision(False, "power flow did not converge")
        return FilterDecision(True)


@register("filter", "voltage_range")
@dataclass
class VoltageRangeFilter(SampleFilter):
    """Reject samples where any bus voltage leaves ``[vmin, vmax]`` p.u.

    By default every time step is checked.  Set ``tail_fraction`` in
    ``(0, 1]`` to only check the last fraction of the simulation — useful to
    ignore the deep voltage dip during a bolted fault and look only at the
    post-clearing recovery.

    Skipped if PF failed (no time-series data) — combine with
    :class:`PFConvergedFilter` to reject those upfront.
    """

    vmin: float = 0.85
    vmax: float = 1.15
    tail_fraction: float = 1.0

    def judge(self, result: "SimulationResult", scenario: "Scenario", case: "NetworkCase") -> FilterDecision:
        if not result.pf_success or result.n_steps == 0:
            return FilterDecision(True)  # nothing to test
        vm = result.voltage_magnitude
        if 0.0 < self.tail_fraction < 1.0:
            n = vm.shape[0]
            i0 = max(0, n - int(np.ceil(n * self.tail_fraction)))
            vm = vm[i0:]
        v_min = float(vm.min())
        v_max = float(vm.max())
        if v_min < self.vmin:
            return FilterDecision(False, f"voltage min {v_min:.3f} < {self.vmin}", metric=v_min)
        if v_max > self.vmax:
            return FilterDecision(False, f"voltage max {v_max:.3f} > {self.vmax}", metric=v_max)
        return FilterDecision(True, metric=max(v_max - 1.0, 1.0 - v_min))


@register("filter", "angle_stability")
@dataclass
class AngleStabilityFilter(SampleFilter):
    """Reject samples whose max generator angle deviation exceeds a threshold.

    Uses :attr:`SimulationResult.max_angle_deviation_deg` (deviation from
    system mean) — a coarse proxy for first-swing stability.
    """

    max_dev_deg: float = 180.0

    def judge(self, result: "SimulationResult", scenario: "Scenario", case: "NetworkCase") -> FilterDecision:
        if not result.pf_success or result.n_steps == 0:
            return FilterDecision(True)
        dev = result.max_angle_deviation_deg
        if dev is None:
            return FilterDecision(True)
        if dev > self.max_dev_deg:
            return FilterDecision(False, f"angle dev {dev:.1f}° > {self.max_dev_deg}°", metric=dev)
        return FilterDecision(True, metric=dev)


@register("filter", "simulation_completed")
@dataclass
class SimulationCompletedFilter(SampleFilter):
    """Reject samples whose final time is more than ``tol`` below ``stoptime``."""

    tol: float = 1e-3

    def judge(self, result: "SimulationResult", scenario: "Scenario", case: "NetworkCase") -> FilterDecision:
        # We stash stoptime in metadata['stoptime'] from the runner.
        stoptime = result.metadata.get("stoptime")
        if stoptime is None or result.n_steps == 0:
            return FilterDecision(True)
        last_t = float(result.Time[-1])
        if last_t < stoptime - self.tol:
            return FilterDecision(False, f"sim stopped at t={last_t:.3f} < {stoptime}", metric=last_t)
        return FilterDecision(True, metric=last_t)
