"""Runge-Kutta-Fehlberg adaptive ODE solver plugin."""
from __future__ import annotations

from pylectra.interfaces.ode_solver import ODESolver, StepResult
from pylectra.registry import register


@register("ode_solver", "rkf")
class RKFSolver(ODESolver):
    """Adaptive RKF45 (legacy method = 3)."""

    adaptive = True
    legacy_method_id = 3

    def step(self, system, t: float, dt: float) -> StepResult:
        raise NotImplementedError("Phase-2 only; SingleRunner uses legacy rundyn.")
