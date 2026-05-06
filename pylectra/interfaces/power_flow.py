"""Abstract base class for power-flow solvers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.case import NetworkCase


class PowerFlowSolver(ABC):
    """Solve the steady-state power flow on a :class:`NetworkCase`.

    Implementations may wrap MATPOWER-derived Newton (the default), pandapower,
    or any custom algorithm.  They must update ``case.bus[:, VM/VA]`` and
    ``case.gen[:, QG]`` in place (or return a new case) and set the
    ``success`` flag.
    """

    @abstractmethod
    def solve(
        self,
        case: "NetworkCase",
        options: Optional[dict] = None,
    ) -> "NetworkCase":
        """Solve the power flow and return the (possibly new) case.

        Sets ``case.success`` and ``case.iterations``.
        """
