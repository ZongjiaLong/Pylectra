"""Runge-Kutta Higham-Hall adaptive ODE solver plugin."""
from __future__ import annotations

from pylectra.interfaces.ode_solver import ODESolver, StepResult
from pylectra.registry import register


@register("ode_solver", "rkhh")
class RKHHSolver(ODESolver):
    """Adaptive RK Higham-Hall (legacy method = 4)."""

    adaptive = True
    legacy_method_id = 4

    def step(self, system, t: float, dt: float) -> StepResult:
        raise NotImplementedError("Phase-2 only; SingleRunner uses legacy rundyn.")
