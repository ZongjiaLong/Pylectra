"""Phase 4 unit tests: scenario / filter plugin discovery and basic semantics.

These are fast (no simulation), so they catch most regressions without the
~50 s slow-batch test.
"""
from __future__ import annotations

import numpy as np
import pytest

import pylectra  # noqa: F401  (triggers discovery)
from pylectra.registry import get, list_plugins


# ---------------------------------------------------------- registration
def test_all_required_scenarios_registered():
    names = list_plugins("scenario")["scenario"]
    for must in ("load_perturb", "line_outage", "noop"):
        assert must in names, f"missing scenario plugin {must!r}"


def test_all_required_filters_registered():
    names = list_plugins("filter")["filter"]
    for must in ("pf_converged", "voltage_range",
                 "angle_stability", "simulation_completed"):
        assert must in names, f"missing filter plugin {must!r}"


# ---------------------------------------------------------- scenario semantics
def test_load_perturb_is_seed_deterministic():
    """Same seed → same output factors regardless of call count."""
    cls = get("scenario", "load_perturb")
    s = cls(sigma_pct=5.0, clip_pct=20.0)
    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)

    # Build a minimal NetworkCase-like stub: only ``mpc['bus']`` is touched.
    from pylectra.core.case import NetworkCase
    bus = np.zeros((5, 13))
    bus[:, 2] = [100.0, 50.0, 80.0, 30.0, 60.0]   # PD
    bus[:, 3] = [10.0, 5.0, 8.0, 3.0, 6.0]        # QD
    case_a = NetworkCase({"baseMVA": 100.0, "bus": bus.copy(),
                          "gen": np.zeros((1, 21)), "branch": np.zeros((1, 13))})
    case_b = NetworkCase({"baseMVA": 100.0, "bus": bus.copy(),
                          "gen": np.zeros((1, 21)), "branch": np.zeros((1, 13))})
    out_a = s.generate(case_a, rng_a)
    out_b = s.generate(case_b, rng_b)
    np.testing.assert_array_equal(out_a.case.bus[:, 2], out_b.case.bus[:, 2])
    np.testing.assert_array_equal(out_a.case.bus[:, 3], out_b.case.bus[:, 3])


def test_load_perturb_respects_sigma_zero():
    """sigma_pct=0 → no change."""
    cls = get("scenario", "load_perturb")
    s = cls(sigma_pct=0.0, clip_pct=20.0)

    from pylectra.core.case import NetworkCase
    bus = np.zeros((3, 13))
    bus[:, 2] = [100.0, 50.0, 80.0]
    case = NetworkCase({"baseMVA": 100.0, "bus": bus.copy(),
                        "gen": np.zeros((1, 21)), "branch": np.zeros((1, 13))})
    out = s.generate(case, np.random.default_rng(0))
    np.testing.assert_array_equal(out.case.bus[:, 2], [100.0, 50.0, 80.0])


# ---------------------------------------------------------- filter semantics
def test_pf_converged_filter_decisions():
    cls = get("filter", "pf_converged")
    f = cls()

    class _Stub:
        pass

    res_ok = _Stub(); res_ok.pf_success = True
    res_bad = _Stub(); res_bad.pf_success = False

    assert f.judge(res_ok, None, None).passed is True
    d = f.judge(res_bad, None, None)
    assert d.passed is False
    assert "converge" in d.reason.lower()
