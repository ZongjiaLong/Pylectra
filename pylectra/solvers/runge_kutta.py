"""Classic RK4 ODE solver plugin."""
from __future__ import annotations

from pylectra.interfaces.ode_solver import ODESolver, StepResult
from pylectra.registry import register


@register("ode_solver", "runge_kutta")
class RungeKuttaSolver(ODESolver):
    """Classic 4th-order Runge-Kutta; fixed step (legacy method = 2)."""

    adaptive = False
    legacy_method_id = 2

    def step(self, system, t: float, dt: float) -> StepResult:
        raise NotImplementedError("Phase-2 only; SingleRunner uses legacy rundyn.")
