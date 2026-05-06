"""Branch trip fault — opens a line at ``t_trip`` (and optionally re-closes).

Mutates column ``BR_STATUS`` (1-based col 11 / 0-based col 10) of the
branch matrix from 1 → 0 at ``t_trip``.  If ``reclose_after`` is set, the
breaker re-closes (status → 1) at ``t_trip + reclose_after``.

Parameters
----------
branch:
    1-based branch index (row of ``case.branch``).
t_trip:
    Time at which the line opens [s].
reclose_after:
    If non-None, time after trip at which the line is re-energised [s].
    ``None`` → permanent outage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "line_trip")
@dataclass
class LineTrip(FaultEvent):
    branch: int = 1
    t_trip: float = 0.2
    reclose_after: Optional[float] = None

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Branch event uses kind=2 in the legacy event log.
        events = [[self.t_trip, 2]]
        # linechange row format: [time, branch(1-based), col(1-based), value]
        # col 11 (1-based) = BR_STATUS.
        linechange = [[self.t_trip, self.branch, 11, 0.0]]
        if self.reclose_after is not None:
            t_close = self.t_trip + float(self.reclose_after)
            events.append([t_close, 2])
            linechange.append([t_close, self.branch, 11, 1.0])

        event = np.asarray(events, dtype=float)
        buschange = np.empty((0, 4), dtype=float)
        linechange_arr = np.asarray(linechange, dtype=float)
        return event, buschange, linechange_arr
