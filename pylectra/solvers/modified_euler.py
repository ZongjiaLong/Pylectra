"""Modified-Euler ODE solver plugin (legacy default)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pylectra.interfaces.ode_solver import ODESolver, StepResult
from pylectra.registry import register

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.system import DynamicSystem


@register("ode_solver", "modified_euler")
class ModifiedEulerSolver(ODESolver):
    """Modified Euler (predictor-corrector); fixed step.

    Phase 1: forwarded to legacy :func:`rundyn` via ``method = 1``.
    Phase 2: ``step`` will dispatch through the registered model plugins.
    """

    adaptive = False
    legacy_method_id = 1

    def step(self, system: "DynamicSystem", t: float, dt: float) -> StepResult:
        raise NotImplementedError(
            "ModifiedEulerSolver.step() is reserved for the Phase-2 native "
            "ODE loop. The Phase-1 SingleRunner uses the legacy rundyn "
            "loop selected via legacy_method_id=1."
        )
