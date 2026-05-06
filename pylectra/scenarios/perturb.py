"""Builtin scenario generators: load perturbation and random line outage.

Both subclasses are registered as ``scenario`` plugins and can be combined
inside a YAML config — the batch runner applies them in declaration order to
the *same* per-iteration case copy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

import numpy as np

from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.registry import register

from pylectra.core.idx import PD, QD, BR_STATUS

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase


# --------------------------------------------------------------------- helpers

def _ensure_scenario(s: Optional[Scenario], base_case: "NetworkCase") -> Scenario:
    """Pass-through Scenario or wrap fresh copy of base_case."""
    if s is None:
        return Scenario(case=base_case.copy(), metadata={})
    return s


# --------------------------------------------------------------------- plugins


@register("scenario", "load_perturb")
@dataclass
class LoadPerturbScenario(ScenarioGenerator):
    """Multiplicative random perturbation of all bus loads.

    Each bus's PD/QD is multiplied by ``1 + N(0, sigma_pct/100)`` (clipped to
    ``[1 - clip_pct/100, 1 + clip_pct/100]``).  Buses with zero load are left
    alone.
    """

    sigma_pct: float = 5.0
    clip_pct: float = 20.0
    seed_offset: int = 0

    def generate(
        self,
        base_case: "NetworkCase",
        rng: np.random.Generator,
    ) -> Scenario:
        scen = Scenario(case=base_case.copy(), metadata={})
        bus = scen.case.bus
        n = bus.shape[0]
        sigma = self.sigma_pct / 100.0
        clip = self.clip_pct / 100.0
        factor = 1.0 + rng.normal(0.0, sigma, size=n)
        factor = np.clip(factor, 1.0 - clip, 1.0 + clip)
        bus[:, PD] = bus[:, PD] * factor
        bus[:, QD] = bus[:, QD] * factor
        scen.metadata["load_perturb_sigma_pct"] = self.sigma_pct
        scen.metadata["load_perturb_factor_min"] = float(factor.min())
        scen.metadata["load_perturb_factor_max"] = float(factor.max())
        return scen


@register("scenario", "line_outage")
@dataclass
class LineOutageScenario(ScenarioGenerator):
    """Randomly trip ``n_outages`` branches with probability ``prob``.

    With probability ``1 - prob`` the scenario is left untouched (useful to
    mix N-0, N-1 and N-2 cases in one batch).
    """

    n_outages: int = 1
    prob: float = 1.0
    exclude_branches: List[int] = field(default_factory=list)

    def generate(
        self,
        base_case: "NetworkCase",
        rng: np.random.Generator,
    ) -> Scenario:
        scen = Scenario(case=base_case.copy(), metadata={})
        if rng.random() > self.prob:
            scen.metadata["line_outage_branches"] = []
            return scen
        branch = scen.case.branch
        n = branch.shape[0]
        candidates = np.array(
            [i for i in range(n) if i not in self.exclude_branches and branch[i, BR_STATUS] > 0]
        )
        k = min(self.n_outages, candidates.size)
        if k == 0:
            scen.metadata["line_outage_branches"] = []
            return scen
        chosen = rng.choice(candidates, size=k, replace=False)
        branch[chosen, BR_STATUS] = 0
        scen.metadata["line_outage_branches"] = [int(b) for b in chosen]
        return scen


@register("scenario", "noop")
@dataclass
class NoopScenario(ScenarioGenerator):
    """Pass-through scenario (handy as an explicit base or for tests)."""

    def generate(self, base_case, rng):
        return Scenario(case=base_case.copy(), metadata={"noop": True})
