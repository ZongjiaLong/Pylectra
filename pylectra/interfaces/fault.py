"""Abstract base class for fault events.

A *fault* is anything that mutates the network during the time-domain
simulation: bus shunt change, branch trip, generator drop, etc.  The abstract
interface hides the legacy ``event / buschange / linechange`` triplet behind a
single :meth:`build_arrays` method.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class FaultSpec:
    """User-facing description of a fault (kind plus parameters).

    ``kind`` selects the registered ``fault`` plugin; ``params`` is forwarded
    to its constructor.  Used by :class:`pylectra.config.ExperimentConfig`.
    """

    kind: str
    params: dict


class FaultEvent(ABC):
    """Concrete fault implementation."""

    @abstractmethod
    def build_arrays(
        self,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return the legacy ``(event, buschange, linechange)`` arrays.

        ``event`` is ``(N, 2)`` with rows ``[time, kind]`` (kind=1 bus,
        kind=2 branch).  ``buschange`` and ``linechange`` are ``(N, 4)``.
        Rows of the wrong kind are zero — see :func:`PowerFlow.Loadevents`.
        """

    def to_loadevents_dict(self) -> dict:
        """Return the dict shape accepted by :func:`PowerFlow.Loadevents`."""
        ev, bc, lc = self.build_arrays()
        return {"event": ev, "buschange": bc, "linechange": lc}
