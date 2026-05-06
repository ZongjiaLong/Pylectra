"""Phase 5 unit tests: ``small_signal_stable`` filter decisions."""
from __future__ import annotations

import math

import pytest

import pylectra  # noqa: F401
from pylectra.registry import get


class _SS:
    def __init__(self, margin: float):
        self.stability_margin = margin


class _Result:
    def __init__(self, margin):
        self.small_signal = _SS(margin) if margin is not None else None


def test_stable_equilibrium_passes():
    f = get("filter", "small_signal_stable")()  # margin_max default = 0
    d = f.judge(_Result(-0.42), None, None)
    assert d.passed is True
    assert d.metric == pytest.approx(-0.42)


def test_unstable_equilibrium_rejected():
    f = get("filter", "small_signal_stable")()
    d = f.judge(_Result(0.05), None, None)
    assert d.passed is False
    assert "unstable" in d.reason


def test_stricter_margin_rejects_marginal():
    f = get("filter", "small_signal_stable")(margin_max=-0.05)
    d = f.judge(_Result(-0.02), None, None)  # technically stable, but barely
    assert d.passed is False


def test_missing_small_signal_skips_filter():
    f = get("filter", "small_signal_stable")()
    d = f.judge(_Result(None), None, None)
    assert d.passed is True
    assert "absent" in d.reason
    assert math.isnan(d.metric)


def test_nan_margin_rejected():
    """NaN margin is treated as 'no stability info' → fail-safe rejection."""
    f = get("filter", "small_signal_stable")()
    d = f.judge(_Result(float("nan")), None, None)
    assert d.passed is False
