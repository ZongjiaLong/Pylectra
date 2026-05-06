"""Abstract base class for scenario generators.

A *scenario generator* turns a base case into a perturbed case + fault, ready
for one batch sample.  Examples include random load fluctuation, N-1 / N-2
random line outage and combinations thereof.

The generator owns the random source: callers pass in a seeded
``numpy.random.Generator`` so batch runs are reproducible.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase
    from pylectra.interfaces.fault import FaultEvent


@dataclass
class Scenario:
    """One element of a batch sample sweep.

    Attributes
    ----------
    case:
        Perturbed network case (deep copy of the base case).
    fault:
        Optional fault to apply during simulation.  ``None`` means "no fault"
        — the simulation runs to ``stoptime`` from steady state.
    metadata:
        Free-form dict logged into the Parquet metadata table.  Scenario
        generators record their perturbation choices here.
    """

    case: "NetworkCase"
    fault: Optional["FaultEvent"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScenarioGenerator(ABC):
    """Yield perturbed cases + faults for batch sample generation."""

    @abstractmethod
    def generate(
        self,
        base_case: "NetworkCase",
        rng: np.random.Generator,
    ) -> Scenario:
        """Return one scenario.

        Implementations must not mutate ``base_case`` — use
        ``base_case.copy()``.
        """
