"""scipy.integrate adaptive ODE solvers as ``pylectra`` plugins.

These wire up :class:`scipy.integrate.RK45`, :class:`DOP853`, :class:`LSODA`,
:class:`BDF`, :class:`Radau` to the native :class:`pylectra.engine.IntegrationLoop`.

Every class has class attribute ``uses_native_engine = True`` and a
``make_stepper(rhs, t0, y0, t_bound, **opts)`` static method returning a
fresh scipy ``OdeSolver`` instance.

Tunable options (forwarded as kwargs to the scipy class):

* ``rtol`` (float) — relative tolerance, default 1e-4.
* ``atol`` (float) — absolute tolerance, default 1e-6.
* ``max_step`` (float) — maximum integration step, default ``np.inf``.
* ``first_step`` (float | None) — initial step guess.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.integrate import RK45, RK23, DOP853, LSODA, BDF, Radau

from pylectra.interfaces.ode_solver import ODESolver, StepResult
from pylectra.registry import register


def _common_kwargs(opts: dict) -> dict[str, Any]:
    """Pull RK-style adaptive options from a YAML opts dict.

    Unknown keys are passed through verbatim; scipy accepts/ignores them.
    """
    kwargs: dict[str, Any] = {}
    for k in ("rtol", "atol", "max_step", "first_step", "vectorized"):
        if k in opts and opts[k] is not None:
            kwargs[k] = opts[k]
    return kwargs


class _ScipyAdaptive(ODESolver):
    """Base class for scipy-backed adaptive solvers.

    Subclasses set ``_scipy_cls`` to a scipy ``OdeSolver`` subclass.
    """
    uses_native_engine: bool = True
    engine_kind: str = "scipy"
    legacy_method_id: int | None = None  # not used in native path

    _scipy_cls: type

    @classmethod
    def make_stepper(cls, rhs, t0, y0, t_bound, **opts):
        kw = _common_kwargs(opts)
        return cls._scipy_cls(rhs, float(t0), np.asarray(y0, dtype=float),
                              float(t_bound), **kw)

    # The Phase-1 ABC requires step(); Phase-2 native engine doesn't call it
    # because it builds the scipy stepper directly via make_stepper.
    def step(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError(
            "scipy solvers are driven through IntegrationLoop, not via step()."
        )


@register("ode_solver", "scipy_rk45")
class ScipyRK45(_ScipyAdaptive):
    """Scipy adaptive Runge–Kutta 4(5) (Dormand–Prince).

    Recommended default for non-stiff power-system transients.
    """
    _scipy_cls = RK45


@register("ode_solver", "scipy_rk23")
class ScipyRK23(_ScipyAdaptive):
    """Scipy adaptive Runge–Kutta 2(3) (Bogacki–Shampine)."""
    _scipy_cls = RK23


@register("ode_solver", "scipy_dop853")
class ScipyDOP853(_ScipyAdaptive):
    """Scipy 8(5,3) Dormand–Prince — high-order, very accurate.

    Best choice when sample-quality matters more than speed (e.g. CCT search).
    """
    _scipy_cls = DOP853


@register("ode_solver", "scipy_lsoda")
class ScipyLSODA(_ScipyAdaptive):
    """Scipy LSODA — auto switches between non-stiff and stiff."""
    _scipy_cls = LSODA


@register("ode_solver", "scipy_bdf")
class ScipyBDF(_ScipyAdaptive):
    """Scipy BDF — implicit, for stiff systems."""
    _scipy_cls = BDF


@register("ode_solver", "scipy_radau")
class ScipyRadau(_ScipyAdaptive):
    """Scipy Radau IIA 5th order — implicit, A-stable, for stiff systems."""
    _scipy_cls = Radau
