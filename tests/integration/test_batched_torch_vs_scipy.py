"""Phase 6 — batched torch engine vs scipy native: numerical regression.

Builds B perturbed case39 cases (load_perturb only, deterministic seeds),
runs them through both engines, and asserts per-sample agreement on
Angles, Speeds, and bus-voltage magnitudes within RK4-vs-DOP853
truncation-error scale.

Skipped cleanly when torch is not installed.  Marked ``slow`` — each
batch is several seconds on CPU torch.
"""
from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import pylectra  # noqa: F401  (after importorskip)
from pylectra.core.case import NetworkCase
from pylectra.core.idx import PD, QD
from pylectra.engine.torch_engine_batched import (
    BatchedRunSpec, BatchedTorchIntegrationLoop)
from pylectra.engine.loop import IntegrationLoop
from pylectra.faults.bus_fault import BusFault
from pylectra.solvers import scipy_solvers  # noqa: F401  — registers DOP853
from pylectra import registry


B = 4
SEED = 1234


def _make_perturbed_cases(n: int):
    base = NetworkCase.load("case39")
    rng = np.random.default_rng(SEED)
    cases = []
    for _ in range(n):
        c = base.copy()
        f = 1.0 + rng.normal(0.0, 0.03, c.bus.shape[0])
        f = np.clip(f, 0.9, 1.1)
        c.bus[:, PD] *= f
        c.bus[:, QD] *= f
        cases.append(c)
    return cases


def _scipy_run_one(case: NetworkCase, ev_arg):
    cls = registry.get("ode_solver", "scipy_dop853")
    factory = cls.make_stepper
    loop = IntegrationLoop(
        casefile_pf=case.mpc,
        casefile_dyn="case39dyn",
        casefile_ev=ev_arg,
        solver_factory=factory,
        solver_options={"rtol": 1e-7, "atol": 1e-9},
        output=0,
    )
    return loop.run()


@pytest.mark.slow
def test_batched_torch_vs_scipy_native():
    """Batched torch RK4 (B=4) trajectories agree with scipy DOP853."""
    cases = _make_perturbed_cases(B)

    fault = BusFault(bus=16, t_fault=0.2, duration=0.05)
    ev_arg = fault.to_loadevents_dict()

    # Reference: scipy native, sample-by-sample.
    scipy_results = [_scipy_run_one(c, ev_arg) for c in cases]
    assert all(r.success for r in scipy_results), "scipy reference failed"

    # Batched torch (CPU is fine for the regression — the math doesn't
    # depend on the device).
    spec = BatchedRunSpec(
        batch_size=B, fixed_step=5e-4, dense_n=400,
        device_pref="cpu", torch_dtype="float64",
    )
    loop = BatchedTorchIntegrationLoop(
        casefile_pf=cases[0].mpc,
        casefile_dyn="case39dyn",
        casefile_ev=ev_arg,
        spec=spec,
        output=0,
    )
    torch_results = loop.run_perturbed(cases)
    assert all(r.success for r in torch_results), "batched torch failed"

    # Compare on a shared dense grid — the two engines record at
    # different t_eval, so resample by linear interp on a few probe
    # times in the post-fault window.
    probe_t = np.linspace(0.5, 1.5, 11)

    def interp_at(res, name, t_query, take_abs=False):
        T = np.asarray(res.Time).ravel()
        Y = np.asarray(getattr(res, name))
        if take_abs:
            Y = np.abs(Y)
        if Y.ndim == 1:
            return np.interp(t_query, T, Y)
        out = np.empty((t_query.size, Y.shape[1]))
        for j in range(Y.shape[1]):
            out[:, j] = np.interp(t_query, T, Y[:, j])
        return out

    for i in range(B):
        a_t = interp_at(torch_results[i], "Angles", probe_t)
        a_s = interp_at(scipy_results[i], "Angles", probe_t)
        s_t = interp_at(torch_results[i], "Speeds", probe_t)
        s_s = interp_at(scipy_results[i], "Speeds", probe_t)
        v_t = interp_at(torch_results[i], "Voltages", probe_t, take_abs=True)
        v_s = interp_at(scipy_results[i], "Voltages", probe_t, take_abs=True)

        # Truncation-error tolerances: RK4@0.5 ms vs DOP853 adaptive over
        # 1.5 s of post-fault rotor swing.  RK4 4th-order trails DOP853
        # 8th-order by O(h^4); 1° abs / 4% rel is the realistic envelope.
        np.testing.assert_allclose(a_t, a_s, rtol=5e-2, atol=1.0,
                                   err_msg=f"sample {i} Angles diverge")
        np.testing.assert_allclose(s_t, s_s, rtol=1e-3, atol=1e-3,
                                   err_msg=f"sample {i} Speeds diverge")
        np.testing.assert_allclose(v_t, v_s, rtol=5e-3, atol=1e-2,
                                   err_msg=f"sample {i} |U| diverges")
