"""Composite fault — concatenates multiple sub-faults into one event log.

Parameters
----------
events:
    List of dicts ``{"kind": "<plugin name>", "params": {...}}``.  Each entry
    is resolved through the ``"fault"`` registry, instantiated, and its
    ``build_arrays()`` output stitched into a combined log sorted by time.

Example (YAML)::

    fault:
      kind: composite
      params:
        events:
          - kind: bus_fault
            params: {bus: 16, t_fault: 0.20, duration: 0.05}
          - kind: line_trip
            params: {branch: 21, t_trip: 0.30}
          - kind: load_step
            params: {bus: 4, t_step: 1.0, delta_pd: 100.0}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import get, register


@register("fault", "composite")
@dataclass
class CompositeFault(FaultEvent):
    events: List[dict] = field(default_factory=list)

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        ev_chunks: list[np.ndarray] = []
        bc_chunks: list[np.ndarray] = []
        lc_chunks: list[np.ndarray] = []

        for spec in self.events:
            kind = spec["kind"]
            params = spec.get("params", {})
            cls = get("fault", kind)
            sub = cls(**params)
            ev, bc, lc = sub.build_arrays()
            if ev.size:
                ev_chunks.append(ev)
            if bc.size:
                bc_chunks.append(bc)
            if lc.size:
                lc_chunks.append(lc)

        event = np.vstack(ev_chunks) if ev_chunks else np.empty((0, 2), dtype=float)
        buschange = np.vstack(bc_chunks) if bc_chunks else np.empty((0, 4), dtype=float)
        linechange = np.vstack(lc_chunks) if lc_chunks else np.empty((0, 4), dtype=float)

        # Sort everything by time (column 0).  Stable sort preserves user-
        # provided order for events at exactly the same time.
        if event.size:
            event = event[np.argsort(event[:, 0], kind="stable")]
        if buschange.size:
            buschange = buschange[np.argsort(buschange[:, 0], kind="stable")]
        if linechange.size:
            linechange = linechange[np.argsort(linechange[:, 0], kind="stable")]
        return event, buschange, linechange
