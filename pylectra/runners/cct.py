"""Critical clearing time (CCT) runner — bisection search.

Given a base case + a fault location and onset time, find the maximum fault
duration for which the system remains stable, where stability is judged by a
configurable filter (default: ``angle_stability`` with ``max_dev_deg=180``).

The search is a simple bisection on ``fault.duration`` between
``cfg.cct.low`` and ``cfg.cct.high``, bracketed so that:

* duration = low  → stable (passes filter)
* duration = high → unstable (fails filter)

If either bracket condition is violated, the runner returns the corresponding
``low`` (no instability inside [low, high]) or ``-inf`` flag and prints a
warning.  Bisection stops when ``high - low < cfg.cct.tol``.

Note on quantisation
--------------------
The legacy ``rundyn`` event loop only fires the fault on/off events when the
simulation time lands within machine epsilon of the scheduled time.  Because
the integrator uses a fixed ``stepsize`` from the dynamic case file, we snap
each candidate fault duration to the nearest integer multiple of ``stepsize``.
This keeps the bisection well-defined in the legacy semantics; a smooth
"fire-on-or-after-event-time" mode is a Phase-2 enhancement.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Loaddyn import deferred to runtime — see _load_stepsize() below.

from pylectra import registry
from pylectra.config import ExperimentConfig, PluginSpec
from pylectra.runners.single import SingleRunner


def _load_stepsize(case_dyn) -> float:
    """Read the integration step size from a legacy dynamic-case file.

    Imports the legacy ``Loaddyn`` lazily so the dependency is contained
    to this single helper — a smaller surface to migrate when the legacy
    package is finally retired.  The function is the only call site of
    ``PowerFlow.Loaddyn`` in the runners layer.
    """
    from pylectra.io.dyn_loaders import loaddyn
    _, stepsize, _ = loaddyn(case_dyn)
    return stepsize


@dataclass
class CCTResult:
    cct: float
    iterations: int
    bracket_low: float
    bracket_high: float
    converged: bool
    note: str = ""


def _is_stable(single: SingleRunner, duration: float, cfg: ExperimentConfig, stab_filter) -> bool:
    """Run one simulation with the given fault duration; return True if stable."""
    # Override fault duration just for this call.
    fault_spec = cfg.fault or PluginSpec(kind="bus_fault", params={})
    new_params = dict(fault_spec.params)
    new_params.setdefault("bus", cfg.cct.bus)
    new_params.setdefault("t_fault", cfg.cct.t_fault)
    new_params["duration"] = float(duration)

    cfg_local = ExperimentConfig.from_dict(
        {
            **{
                k: getattr(cfg, k)
                for k in (
                    "case_pf",
                    "case_dyn",
                    "verbose",
                )
            },
            "mode": "single",
            "plot": False,
            "fault": {"kind": fault_spec.kind, "params": new_params},
            "solver": {"kind": cfg.solver.kind, "options": dict(cfg.solver.options)},
            "power_flow": {"kind": cfg.power_flow.kind, "options": dict(cfg.power_flow.options)},
        }
    )

    runner = SingleRunner(cfg_local)
    out = runner.run()
    decision = stab_filter.judge(out.result, out.scenario, out.case)
    return bool(decision.passed)


class CCTRunner:
    """Find CCT via bisection."""

    def __init__(self, cfg: ExperimentConfig):
        self.cfg = cfg
        cls = registry.get("filter", cfg.cct.stability_filter.kind)
        self.stability_filter = cls(**cfg.cct.stability_filter.params)
        # Build a SingleRunner once for re-use; we still re-create per-call cfgs
        # because fault duration changes.
        self.single = SingleRunner(cfg)
        # Pull stepsize from the dynamic case so we can snap candidates to the
        # rundyn integration grid (see module-level note).  The native engine
        # fires events exactly on schedule (leg-by-leg integration), so we
        # only snap for legacy fixed-step solvers.
        self._stepsize = _load_stepsize(cfg.case_dyn)
        try:
            solver_cls = registry.get("ode_solver", cfg.solver.kind)
            self._native = bool(getattr(solver_cls, "uses_native_engine", False))
        except KeyError:
            self._native = False

    def _snap(self, duration: float) -> float:
        """Round *duration* to the nearest multiple of the integration step.

        Native-engine solvers honour event times exactly and need no snap.
        """
        if self._native or self._stepsize <= 0:
            return duration
        return round(duration / self._stepsize) * self._stepsize

    def run(self) -> CCTResult:
        cfg = self.cfg
        lo, hi = float(cfg.cct.low), float(cfg.cct.high)
        tol = float(cfg.cct.tol)
        max_iter = int(cfg.cct.max_iter)

        lo = self._snap(lo)
        hi = self._snap(hi)

        # Bracket sanity: low must be stable, high must be unstable.
        if cfg.verbose:
            mode = "native (no snap)" if self._native else f"snapped to step {self._stepsize}"
            print(f"[cct] bracket check: low={lo}, high={hi} ({mode})")
        lo_stable = _is_stable(self.single, lo, cfg, self.stability_filter)
        hi_stable = _is_stable(self.single, hi, cfg, self.stability_filter)

        if not lo_stable:
            return CCTResult(
                cct=lo,
                iterations=0,
                bracket_low=lo,
                bracket_high=hi,
                converged=False,
                note=f"system unstable even at duration={lo}; CCT lies below the bracket",
            )
        if hi_stable:
            return CCTResult(
                cct=hi,
                iterations=0,
                bracket_low=lo,
                bracket_high=hi,
                converged=False,
                note=f"system stable even at duration={hi}; CCT lies above the bracket",
            )

        it = 0
        while (hi - lo) > tol and it < max_iter:
            mid = self._snap(0.5 * (lo + hi))
            # Avoid revisiting an endpoint after snapping.
            if mid <= lo or mid >= hi:
                break
            stable = _is_stable(self.single, mid, cfg, self.stability_filter)
            if cfg.verbose:
                print(
                    f"[cct] iter {it+1:2d}: duration={mid:.4f} → "
                    f"{'stable' if stable else 'unstable'}"
                )
            if stable:
                lo = mid
            else:
                hi = mid
            it += 1

        cct = lo  # last known stable
        converged = (hi - lo) <= tol or (
            not self._native and (hi - lo) <= self._stepsize * 1.5
        )
        return CCTResult(
            cct=cct,
            iterations=it,
            bracket_low=lo,
            bracket_high=hi,
            converged=converged,
            note="" if converged else f"hit max_iter={max_iter}",
        )
