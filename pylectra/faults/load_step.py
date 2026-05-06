"""Load step disturbance — instantaneously changes PD/QD on a bus.

A common stress test for governor / AVR response.  Adds a step at
``t_step`` and optionally returns to the original value at
``t_step + duration``.

Parameters
----------
bus:
    1-based bus number.
t_step:
    Time at which the load changes [s].
delta_pd:
    Real-power adder applied to ``case.bus[bus, PD]`` [MW].
delta_qd:
    Reactive-power adder applied to ``case.bus[bus, QD]`` [MVAr].
duration:
    If non-None, the load step is reverted after this many seconds.
    ``None`` → permanent change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


# 1-based legacy column indices: 3 = PD, 4 = QD.
_PD_COL = 3
_QD_COL = 4


@register("fault", "load_step")
@dataclass
class LoadStep(FaultEvent):
    bus: int = 1
    t_step: float = 0.5
    delta_pd: float = 0.0
    delta_qd: float = 0.0
    duration: Optional[float] = None

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        events = []
        bus_rows: list[list[float]] = []
        # NOTE: legacy buschange writes *absolute* values to the column, not
        # increments — so callers should configure delta as the new total.
        # We emit two rows (PD and QD) at the step time, and optionally two
        # more at revert time.  Engines that don't honour QD changes simply
        # ignore the second row.
        if self.delta_pd != 0.0:
            events.append([self.t_step, 1])
            bus_rows.append([self.t_step, self.bus, _PD_COL, float(self.delta_pd)])
        if self.delta_qd != 0.0:
            events.append([self.t_step, 1])
            bus_rows.append([self.t_step, self.bus, _QD_COL, float(self.delta_qd)])

        if self.duration is not None:
            t_back = self.t_step + float(self.duration)
            if self.delta_pd != 0.0:
                events.append([t_back, 1])
                bus_rows.append([t_back, self.bus, _PD_COL, 0.0])
            if self.delta_qd != 0.0:
                events.append([t_back, 1])
                bus_rows.append([t_back, self.bus, _QD_COL, 0.0])

        event = np.asarray(events, dtype=float) if events else np.empty((0, 2), dtype=float)
        buschange = np.asarray(bus_rows, dtype=float) if bus_rows else np.empty((0, 4), dtype=float)
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
