"""Sample filter that rejects equilibria failing small-signal stability."""
from __future__ import annotations

import math

from pylectra.registry import register
from pylectra.interfaces.filter import SampleFilter, FilterDecision


@register("filter", "small_signal_stable")
class SmallSignalStableFilter(SampleFilter):
    """Reject batch samples whose equilibrium is small-signal unstable.

    Requires that the experiment has a ``small_signal`` analyzer configured
    so that ``result.small_signal`` is populated.  If the field is absent
    (e.g. the analysis was not enabled), every sample passes with a warning
    stored in the ``FilterDecision`` reason string.

    Parameters
    ----------
    margin_max : float
        Reject if ``stability_margin > margin_max``.
        * Default ``0.0``  — accept only stable equilibria (Re(λ) ≤ 0).
        * Set to a negative value, e.g. ``-0.05``, to enforce a minimum
          decay rate (all eigenvalue real parts must be ≤ -0.05).
    """

    def __init__(self, margin_max: float = 0.0):
        self.margin_max = float(margin_max)

    def judge(self, result, scenario, case) -> FilterDecision:
        ss = getattr(result, "small_signal", None)
        if ss is None:
            return FilterDecision(
                passed=True,
                reason="small_signal result absent — filter skipped",
                metric=float("nan"),
            )
        margin = ss.stability_margin
        ok = (not math.isnan(margin)) and (margin <= self.margin_max)
        verdict = "stable" if ok else "unstable"
        reason = (
            f"small_signal {verdict}: margin={margin:.4g} "
            f"(limit {self.margin_max:+.4g})"
        )
        return FilterDecision(passed=ok, reason=reason, metric=margin)
