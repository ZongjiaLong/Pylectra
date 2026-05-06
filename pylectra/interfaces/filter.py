"""Abstract base class for sample-quality filters.

Each filter judges *one* simulation result and decides whether the sample is
worth keeping in the training set.  Filters compose: the batch runner runs
them in declaration order and the first one to reject wins.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase
    from pylectra.core.result import SimulationResult
    from pylectra.interfaces.scenario import Scenario


@dataclass
class FilterDecision:
    """Outcome of a single filter."""

    passed: bool
    reason: str = ""
    #: Optional numeric metric the filter computed (logged to metadata).
    metric: Optional[float] = None


class SampleFilter(ABC):
    """Reject implausible / undesirable simulation samples."""

    @abstractmethod
    def judge(
        self,
        result: "SimulationResult",
        scenario: "Scenario",
        case: "NetworkCase",
    ) -> FilterDecision:
        """Return a :class:`FilterDecision`.

        ``case`` is the post-power-flow case (may be ``None`` if the PF did
        not converge — filters that depend on the PF should check
        ``result.pf_success`` first).
        """
