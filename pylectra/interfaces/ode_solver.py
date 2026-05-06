"""Abstract base class for time-domain ODE solvers.

Solvers operate on the entire :class:`pylectra.core.system.DynamicSystem` rather
than the raw state vector — this keeps the network admittance solve, machine
currents and per-bank derivative dispatch encapsulated in one place.

A solver advances the system by one step and returns a :class:`StepResult`.
The runner is responsible for the outer loop, event handling and bookkeeping.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — circular-import guard
    from pylectra.core.system import DynamicSystem


@dataclass
class StepResult:
    """Outcome of one solver step.

    Attributes
    ----------
    new_t:
        Time after the step (possibly equal to ``t`` for a rejected adaptive
        step — in which case ``failed`` is ``True``).
    new_stepsize:
        Suggested next step size (adaptive solvers use this; fixed-step
        solvers return their nominal step).
    error_estimate:
        Per-step error estimate (0.0 for fixed-step solvers).
    failed:
        ``True`` if the step was rejected and must be retried with a smaller
        step (adaptive solvers).
    """

    new_t: float
    new_stepsize: float
    error_estimate: float = 0.0
    failed: bool = False


class ODESolver(ABC):
    """Abstract integrator that advances a :class:`DynamicSystem` in time."""

    #: Whether the solver supports adaptive step control.
    adaptive: bool = False

    #: True for Phase-2 solvers driven by :class:`pylectra.engine.IntegrationLoop`
    #: via ``make_stepper``.  False for Phase-1 wrappers around legacy
    #: hand-coded integrators (driven by :func:`rundyn.rundyn`).
    uses_native_engine: bool = False

    #: Engine discriminator used by :class:`pylectra.runners.single.SingleRunner`
    #: to pick the right integration loop.  Allowed values:
    #:
    #: * ``"legacy"`` — driven by :func:`rundyn.rundyn` (Phase 1 plugins).
    #: * ``"scipy"``  — driven by :class:`pylectra.engine.IntegrationLoop`
    #:   (Phase 2a scipy plugins; ``uses_native_engine`` is also True).
    #: * ``"torch"``  — driven by
    #:   :class:`pylectra.engine.torch_engine.TorchIntegrationLoop` (Phase 2c).
    engine_kind: str = "legacy"

    @abstractmethod
    def step(self, system: "DynamicSystem", t: float, dt: float) -> StepResult:
        """Advance *system* in place by ``dt``.

        Implementations mutate the system's state arrays
        (``Xgen``, ``Xexc``, ``Xgov``, ``Xpss``, ``U``, ``Vgen``, ``Vexc``,
        ``Vgov``, ``Vpss``) and return the new time and step-size.
        """
