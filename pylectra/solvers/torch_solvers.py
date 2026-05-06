"""``torchdiffeq``-backed ODE solver plugins.

Routes integration through :func:`torchdiffeq.odeint`.  Each plugin sets
``engine_kind = "torch"`` so :class:`pylectra.runners.single.SingleRunner`
dispatches it to :class:`pylectra.engine.torch_engine.TorchIntegrationLoop`.

The factory signature is intentionally different from the scipy plugins
(no ``OdeSolver`` object — torchdiffeq is a one-shot ``odeint`` call):

    ``factory(rhs, y0, t_eval, **opts) -> torch.Tensor``

where ``rhs(t, y) -> dy/dt`` is a callable on torch tensors and ``t_eval``
is a 1-D torch tensor of sample times.  Returns a tensor of shape
``(len(t_eval), state_dim)``.

The plugins are *only* registered if ``torch`` and ``torchdiffeq`` are both
importable; otherwise the module is a no-op (silent).  Selecting a torch
solver in a YAML config without these dependencies produces a clear runtime
error from :class:`pylectra.engine.torch_engine.TorchIntegrationLoop`.
"""
from __future__ import annotations

from typing import Any, Dict

from pylectra import registry
from pylectra.interfaces.ode_solver import ODESolver, StepResult


_TORCH_AVAILABLE = True
_TORCH_IMPORT_ERROR: Exception | None = None
try:  # pragma: no cover — import guard
    import torch  # type: ignore  # noqa: F401
    import torchdiffeq  # type: ignore  # noqa: F401
except Exception as _e:  # pragma: no cover
    _TORCH_AVAILABLE = False
    _TORCH_IMPORT_ERROR = _e


# Method names supported by torchdiffeq we want to surface as plugins.
# Mapping from our plugin name -> torchdiffeq method string + default opts.
_TORCH_METHODS: Dict[str, Dict[str, Any]] = {
    "torch_dopri5": {"method": "dopri5", "rtol": 1e-7, "atol": 1e-9, "adaptive": True},
    "torch_dopri8": {"method": "dopri8", "rtol": 1e-7, "atol": 1e-9, "adaptive": True},
    "torch_rk4":    {"method": "rk4",    "options": {"step_size": 5e-3}, "adaptive": False},
    "torch_euler":  {"method": "euler",  "options": {"step_size": 5e-3}, "adaptive": False},
}


def _make_factory(method: str, defaults: Dict[str, Any]):
    """Return a ``factory(rhs, y0, t_eval, **opts)`` for a given method."""
    def factory(rhs, y0, t_eval, **opts):
        from torchdiffeq import odeint  # type: ignore

        # Merge defaults with caller overrides.
        rtol = float(opts.pop("rtol", defaults.get("rtol", 1e-7)))
        atol = float(opts.pop("atol", defaults.get("atol", 1e-9)))
        # Per-method extra options (e.g. fixed step_size).
        method_opts = dict(defaults.get("options", {}))
        if "step_size" in opts:
            method_opts["step_size"] = float(opts.pop("step_size"))
        # Drop loop-level options that don't apply here.
        opts.pop("max_step", None)
        opts.pop("first_step", None)
        return odeint(
            rhs, y0, t_eval,
            method=method,
            rtol=rtol, atol=atol,
            options=method_opts if method_opts else None,
        )
    factory.__name__ = f"torchdiffeq_{method}_factory"
    return factory


def _build_solver_class(name: str, method: str, defaults: Dict[str, Any]):
    factory = _make_factory(method, defaults)

    class _TorchODE(ODESolver):
        """torchdiffeq-backed solver plugin (Phase 2c).

        Driven by :class:`pylectra.engine.torch_engine.TorchIntegrationLoop` —
        the ``step`` method is *not* used by the runner; it raises if
        called, so the legacy single-step API stays meaningful for legacy
        plugins only.
        """

        adaptive: bool = bool(defaults.get("adaptive", False))
        uses_native_engine: bool = False  # not the scipy native loop
        engine_kind: str = "torch"
        torch_method: str = method
        # Expose the factory for the loop.
        make_torchdiffeq_call = staticmethod(factory)

        def step(self, system, t: float, dt: float) -> StepResult:  # pragma: no cover
            raise NotImplementedError(
                f"{name} runs through TorchIntegrationLoop, not per-step API"
            )

    _TorchODE.__name__ = f"_TorchODE_{name}"
    _TorchODE.__qualname__ = _TorchODE.__name__
    return _TorchODE


def _make_unavailable_stub(name: str):
    """Stub solver registered when torch/torchdiffeq import failed.

    Surfaces the original ImportError as the ``__cause__`` instead of letting
    the user hit a misleading ``unknown plugin`` KeyError at the registry layer.
    """
    err = _TORCH_IMPORT_ERROR

    def _unavailable(*args, **kwargs):
        raise RuntimeError(
            f"Solver '{name}' requires torch + torchdiffeq, but importing "
            f"them failed: {type(err).__name__}: {err}. "
            "Install them via `pip install -r requirements-torch.txt`."
        ) from err

    class _TorchUnavailable(ODESolver):
        engine_kind: str = "torch"
        torch_method: str = name
        make_torchdiffeq_call = staticmethod(_unavailable)

        def __init__(self, *args, **kwargs):
            _unavailable()


        def step(self, system, t: float, dt: float) -> StepResult:  # pragma: no cover
            _unavailable()

    _TorchUnavailable.__name__ = f"_TorchUnavailable_{name}"
    _TorchUnavailable.__qualname__ = _TorchUnavailable.__name__
    return _TorchUnavailable


if _TORCH_AVAILABLE:
    for _name, _spec in _TORCH_METHODS.items():
        _cls = _build_solver_class(_name, _spec["method"], _spec)
        registry.register("ode_solver", _name)(_cls)
else:
    for _name in _TORCH_METHODS:
        registry.register("ode_solver", _name)(_make_unavailable_stub(_name))


def batched_rk4(rhs, y0, t_eval, *, max_step: float | None = None, **_unused):
    """Pure-torch batched fixed-step RK4.

    Parameters
    ----------
    rhs:
        Callable ``f(t, y) -> dy/dt`` where ``y`` and the returned tensor
        share the **same** shape ``(B, S)``.  ``t`` is a 0-d real torch
        tensor on the device.
    y0:
        ``(B, S)`` real torch tensor — initial state for ``B`` samples.
    t_eval:
        1-D real torch tensor of times at which to record the trajectory.
        Sub-stepping inside an interval is controlled by ``max_step``.
    max_step:
        Optional cap on the RK4 step size (seconds).  If set, the integrator
        sub-divides each ``(t_eval[k], t_eval[k+1])`` interval into
        ``ceil(dt / max_step)`` equal RK4 steps.  ``None`` (default) takes
        one RK4 step per interval — fine when ``t_eval`` is already dense.

    Returns
    -------
    traj:
        ``(T, B, S)`` real torch tensor on the same device as ``y0``.
    """
    if not _TORCH_AVAILABLE:
        raise RuntimeError(
            "batched_rk4 requires torch; install via `pip install torch`"
        ) from _TORCH_IMPORT_ERROR
    import torch

    T = int(t_eval.shape[0])
    out = torch.empty((T,) + tuple(y0.shape), dtype=y0.dtype, device=y0.device)
    out[0] = y0
    y = y0
    with torch.no_grad():
        for k in range(T - 1):
            t0 = t_eval[k]
            t1 = t_eval[k + 1]
            dt_total = (t1 - t0).item()
            if max_step is not None and max_step > 0.0 and dt_total > max_step:
                n_sub = int((dt_total / max_step) + 0.999999)
            else:
                n_sub = 1
            h = dt_total / n_sub
            t = t0
            for _s in range(n_sub):
                k1 = rhs(t, y)
                k2 = rhs(t + 0.5 * h, y + 0.5 * h * k1)
                k3 = rhs(t + 0.5 * h, y + 0.5 * h * k2)
                k4 = rhs(t + h,       y + h       * k3)
                y = y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
                t = t + h
            out[k + 1] = y
    return out


__all__ = [
    "_TORCH_AVAILABLE", "_TORCH_IMPORT_ERROR", "_TORCH_METHODS",
    "batched_rk4",
]
