"""Single-simulation runner.

Routes one experiment through the ``pylectra`` plugin layer.  Three integration
backends, picked by ``solver_cls.engine_kind``:

* **Legacy** (``engine_kind = "legacy"``): the solver plugin exposes a
  ``legacy_method_id`` and the inner loop is :func:`rundyn.rundyn`
  (faithful MATLAB port).  Used by ``modified_euler / runge_kutta / rkf
  / rkhh``.
* **Scipy native** (``engine_kind = "scipy"``): the solver plugin sets
  ``uses_native_engine = True`` and the inner loop is
  :class:`pylectra.engine.IntegrationLoop` driving a :mod:`scipy.integrate`
  ``OdeSolver``.  Used by ``scipy_*``.
* **Torch** (``engine_kind = "torch"``, Phase 2c): the inner loop is
  :class:`pylectra.engine.torch_engine.TorchIntegrationLoop` driving a
  :mod:`torchdiffeq` ``odeint`` call on the chosen device.  Used by
  ``torch_*``.

All three backends return the same :class:`SimulationResult` shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from pylectra.engine.legacy_loop import rundyn as _native_rundyn, default_mdopt

from pylectra import registry
from pylectra.config import ExperimentConfig
from pylectra.core.case import NetworkCase
from pylectra.core.result import SimulationResult
from pylectra.core.system import DynamicSystem
from pylectra.interfaces.fault import FaultEvent
from pylectra.interfaces.scenario import Scenario


def _build_fault(cfg: ExperimentConfig) -> Optional[FaultEvent]:
    if cfg.fault is None:
        return None
    cls = registry.get("fault", cfg.fault.kind)
    return cls(**cfg.fault.params)


def _solver_class(cfg: ExperimentConfig):
    return registry.get("ode_solver", cfg.solver.kind)


def _engine_kind(solver_cls) -> str:
    """Resolve the engine for a solver class with backwards-compat fallback."""
    kind = getattr(solver_cls, "engine_kind", None)
    if kind:
        return str(kind)
    # Legacy fallback for plugins predating the engine_kind discriminator.
    if getattr(solver_cls, "uses_native_engine", False):
        return "scipy"
    return "legacy"


def _solver_method_id(cfg: ExperimentConfig) -> int:
    cls = _solver_class(cfg)
    method_id = getattr(cls, "legacy_method_id", None)
    if method_id is None:
        raise ValueError(
            f"solver plugin '{cfg.solver.kind}' does not expose a "
            f"`legacy_method_id` attribute and is not marked native; "
            f"cannot be driven by SingleRunner. Choose one of: "
            f"modified_euler, runge_kutta, rkf, rkhh, scipy_rk45, "
            f"scipy_dop853, scipy_lsoda, scipy_bdf, scipy_radau, scipy_rk23."
        )
    return int(method_id)


@dataclass
class SingleRunResult:
    """Bundle of one single-mode run output."""

    result: SimulationResult
    case: NetworkCase
    scenario: Optional[Scenario]
    fault: Optional[FaultEvent]


class SingleRunner:
    """Runs one simulation per call."""

    def __init__(self, cfg: ExperimentConfig):
        self.cfg = cfg
        self._mdopt = _build_mdopt(cfg)

    # ------------------------------------------------------------------
    def run(self, scenario: Optional[Scenario] = None) -> SingleRunResult:
        """Execute one simulation.

        If *scenario* is omitted, the base case from ``cfg.case_pf`` is used
        with no perturbation (mirrors the legacy ``TimedomainSim`` behaviour).

        When ``cfg.small_signal`` is set, a small-signal stability analysis is
        performed at the equilibrium point (after power flow, before integration).
        When ``cfg.skip_integration`` is True, the time-domain ODE is not run
        and the result contains only the equilibrium snapshot.
        """
        import time as _time
        cfg = self.cfg

        if scenario is None:
            case = NetworkCase.load(cfg.case_pf)
            scenario = Scenario(case=case, metadata={})
        else:
            case = scenario.case

        system = DynamicSystem.from_legacy(case, cfg.case_dyn)
        fault = _build_fault(cfg)
        ev_arg = fault.to_loadevents_dict() if fault is not None else None

        # ---- Optional: small-signal stability analysis ---------------
        ss_result = None
        eq = None
        if cfg.small_signal is not None or cfg.skip_integration:
            from pylectra.engine.equilibrium import compute_equilibrium
            pf_solver = None
            if cfg.power_flow.kind != "newton":
                pf_cls = registry.get("power_flow", cfg.power_flow.kind)
                pf_solver = pf_cls(**cfg.power_flow.params)
            eq = compute_equilibrium(
                casefile_pf=system.case.mpc,
                casefile_dyn=cfg.case_dyn,
                pf_solver=pf_solver,
                pf_options=cfg.power_flow.options or {},
                output=int(cfg.verbose),
            )
            if not eq.pf_success:
                res = SimulationResult.failed_powerflow(
                    n_bus=system.case.n_bus, n_gen=system.n_gen,
                    reason=eq.diagnostics.get("reason", ""))
                return SingleRunResult(result=res, case=system.case,
                                       scenario=scenario, fault=fault)

            if cfg.small_signal is not None:
                ss_cls = registry.get("small_signal", cfg.small_signal.kind)
                analyzer = ss_cls(**cfg.small_signal.params)
                ss_result = analyzer.analyze(eq.rhs, eq.y0, eq.layout)

        # ---- Skip integration if requested ---------------------------
        if cfg.skip_integration:
            t_eq = eq.diagnostics.get("wall_time_sec", 0.0)
            res = SimulationResult.from_equilibrium_only(
                eq, ss_result=ss_result, simulation_time=t_eq)
            res.metadata.setdefault("stoptime", float(system.stoptime))
            for k, v in (scenario.metadata or {}).items():
                res.metadata.setdefault(f"scenario:{k}", v)
            return SingleRunResult(result=res, case=system.case,
                                   scenario=scenario, fault=fault)

        # ---- Time-domain integration ---------------------------------
        solver_cls = _solver_class(cfg)
        engine = _engine_kind(solver_cls)
        plot = bool(cfg.plot)
        output = int(cfg.verbose)

        if engine == "torch":
            res = self._run_torch(system, ev_arg, solver_cls, output)
        elif engine == "scipy":
            res = self._run_native(system, ev_arg, solver_cls, output)
        else:
            res = self._run_legacy(system, ev_arg, plot, output)

        # Attach small-signal result if computed above.
        res.small_signal = ss_result

        # Surface stoptime so the SimulationCompletedFilter can use it.
        res.metadata.setdefault("stoptime", float(system.stoptime))
        # Forward scenario metadata (handy to log later without re-deriving).
        for k, v in (scenario.metadata or {}).items():
            res.metadata.setdefault(f"scenario:{k}", v)

        # Native / torch engines: SingleRunner handles plotting, the engines
        # themselves do not invoke PlotSG.  Mirror the legacy plot kwarg here.
        if engine in {"scipy", "torch"} and plot and res.pf_success:
            try:
                from pylectra.plotting.sg import plot_sg

                plot_sg(res.n_steps, res.Time, res.Voltages, res.Efds,
                        res.Angles, res.Speeds, res.Eq_trs, res.Ed_trs,
                        res.Tes, res.TM, res.Vss)
            except Exception:  # pragma: no cover — plotting is best-effort
                pass

        return SingleRunResult(result=res, case=system.case,
                               scenario=scenario, fault=fault)

    # ---- legacy path -------------------------------------------------

    def _run_legacy(self, system: "DynamicSystem", ev_arg, plot: bool,
                    output: int) -> SimulationResult:
        method_id = _solver_method_id(self.cfg)
        mdopt = self._mdopt.copy()
        mdopt[0] = method_id

        legacy_dict = _native_rundyn(
            system.case.mpc,
            system.to_dyn_dict(),
            ev_arg,
            mdopt,
            plot=plot,
            output=output,
        )
        if legacy_dict is None:
            return SimulationResult.failed_powerflow(
                n_bus=system.case.n_bus, n_gen=system.n_gen)
        return SimulationResult.from_legacy_dict(legacy_dict)

    # ---- native (Phase 2) path ---------------------------------------

    def _run_native(self, system: "DynamicSystem", ev_arg, solver_cls,
                    output: int) -> SimulationResult:
        from pylectra.engine import IntegrationLoop

        opts = dict(self.cfg.solver.options or {})

        loop = IntegrationLoop(
            casefile_pf=system.case.mpc,
            casefile_dyn=system.to_dyn_dict(),
            casefile_ev=ev_arg,
            solver_factory=solver_cls.make_stepper,
            solver_options=opts,
            output=output,
        )
        eng_res = loop.run()
        if not eng_res.success:
            return SimulationResult.failed_powerflow(
                n_bus=system.case.n_bus, n_gen=system.n_gen,
                reason=eng_res.message)
        return SimulationResult.from_legacy_dict(eng_res.as_dict())

    # ---- torch (Phase 2c) path ---------------------------------------

    def _run_torch(self, system: "DynamicSystem", ev_arg, solver_cls,
                   output: int) -> SimulationResult:
        from pylectra.engine.torch_engine import TorchIntegrationLoop

        opts = dict(self.cfg.solver.options or {})
        factory = solver_cls.make_torchdiffeq_call

        loop = TorchIntegrationLoop(
            casefile_pf=system.case.mpc,
            casefile_dyn=system.to_dyn_dict(),
            casefile_ev=ev_arg,
            solver_factory=factory,
            solver_options=opts,
            output=output,
        )
        eng_res = loop.run()
        if not eng_res.success:
            return SimulationResult.failed_powerflow(
                n_bus=system.case.n_bus, n_gen=system.n_gen,
                reason=eng_res.message)
        return SimulationResult.from_legacy_dict(eng_res.as_dict())


# ---------------------------------------------------------------------------

def _build_mdopt(cfg: ExperimentConfig) -> np.ndarray:
    """Build a 5-element mdopt array, applying solver/options overrides."""
    mdopt = np.asarray(default_mdopt(), dtype=float)
    opts = cfg.solver.options or {}
    if "tol" in opts:
        mdopt[1] = float(opts["tol"])
    if "minstepsize" in opts:
        mdopt[2] = float(opts["minstepsize"])
    if "maxstepsize" in opts:
        mdopt[3] = float(opts["maxstepsize"])
    if "output" in opts:
        mdopt[4] = float(opts["output"])
    return mdopt
