"""Three-phase bus-fault plugin (the demo fault used by ``TimedomainSim``).

Replaces the global ``tf, fd, fb`` writes on
:mod:`Cases.Events.fault` with explicit constructor parameters.  The plugin
hands :func:`PowerFlow.Loadevents.Loadevents` a ready-to-consume dict so no
temporary case file is ever written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "bus_fault")
@dataclass
class BusFault(FaultEvent):
    """Bolted three-phase bus fault, cleared after ``duration`` seconds.

    Parameters
    ----------
    bus:
        1-based bus number (matches the convention of the legacy fault file).
    t_fault:
        Time at which the fault is applied [s].
    duration:
        Fault clearing time [s].  ``t_fault + duration`` is the moment of
        clearing.
    """

    bus: int = 1
    t_fault: float = 0.2
    duration: float = 0.05

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Same column layout as Cases/Events/fault.py:
        #   event:      [time, kind=1 (bus event)]
        #   buschange:  [time, bus(1-based), col(1-based, 6 = BS shunt), value]
        # During the fault we add a huge negative shunt (bolted short);
        # at clearing we restore zero.
        event = np.array(
            [
                [self.t_fault, 1],
                [self.t_fault + self.duration, 1],
            ],
            dtype=float,
        )
        buschange = np.array(
            [
                [self.t_fault, self.bus, 6, -1e10],
                [self.t_fault + self.duration, self.bus, 6, 0],
            ],
            dtype=float,
        )
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
