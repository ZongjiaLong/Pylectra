# Add a new fault type

_Advanced_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md)

## Goal

Write a fault / event plugin selectable as `kind: my_fault` in YAML.

## How faults work

A fault = **a set of timed events**, each modifying one column of the bus or branch matrix at a specific time. pylectra fires events in chronological order and integrates between them.

The `FaultEvent` ABC has a single method that returns three arrays:

```python
def build_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (event, buschange, linechange).

    event:      shape (N, 2)   rows [time, kind] — kind=1 bus event, kind=2 branch event
    buschange:  shape (N, 4)   rows [time, bus(1-based), col(1-based), value]
    linechange: shape (N, 4)   rows [time, branch(1-based), col(1-based), value]
    """
```

## Working example: bus fault with adjustable impedance

```python
# pylectra/faults/bus_fault_impedance.py
"""Three-phase bus fault with finite impedance (not bolted)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "bus_fault_impedance")
@dataclass
class BusFaultWithImpedance(FaultEvent):
    bus: int = 1
    t_fault: float = 0.2
    duration: float = 0.05
    fault_susceptance: float = -100.0    # pu, negative = ground fault impedance

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # event: [time, kind=1 (bus event)]
        event = np.array([
            [self.t_fault,                   1],
            [self.t_fault + self.duration,   1],
        ], dtype=float)
        # buschange: [time, bus, col=6 (1-based BS shunt), value]
        buschange = np.array([
            [self.t_fault,                   self.bus, 6, self.fault_susceptance],
            [self.t_fault + self.duration,   self.bus, 6, 0.0],
        ], dtype=float)
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
```

YAML:

```yaml
fault:
  kind: bus_fault_impedance
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.10
    fault_susceptance: -50.0     # much milder than the bolted -1e10
```

## Column index reference (1-based, MATPOWER style)

| Array | Col 1 | Col 2 | Col 3 | Col 4 |
|---|---|---|---|---|
| `bus` | bus number | type (1=PQ, 2=PV, 3=REF) | **PD (active load)** | **QD (reactive load)** |
| `bus` (cont.) | ... 5 = GS | **6 = BS (shunt susceptance)** | 7 = area | 8 = VM |
| `branch` | F_BUS (from) | T_BUS (to) | BR_R | BR_X |
| `branch` (cont.) | ... 11 = **BR_STATUS (0=open, 1=closed)** | 12 = ANGMIN | ... | ... |

The full index table is in `pylectra/core/idx.py`.

## Built-in faults — comparison

| Name | What it changes | Typical use |
|---|---|---|
| `bus_fault` | bus col 6 (BS) → very negative | Three-phase ground fault |
| `line_trip` | branch col 11 (BR_STATUS) → 0 | Line outage |
| `load_step` | bus col 3/4 (PD/QD) → new value | Load step change |
| `composite` | nests sub-faults | Cascaded event sequence |

## Example 2: generator outage

```python
# pylectra/faults/gen_outage.py
"""Generator trip (outage)."""
import numpy as np
from dataclasses import dataclass
from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "gen_outage")
@dataclass
class GeneratorOutage(FaultEvent):
    gen_index: int = 1                # 1-based generator index (row of gen matrix)
    t_outage: float = 0.5

    def build_arrays(self):
        # The current event dispatcher only supports bus / branch changes.
        # To outage a generator, the cleanest workaround is to simulate
        # "no generation" by adding the generator's PG as a load step at
        # its bus:
        event     = np.array([[self.t_outage, 1]], dtype=float)
        # Schematic only — a real implementation must read PG from the case
        buschange = np.empty((0, 4), dtype=float)
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
```

> ⚠️ This example shows a **limitation of the current fault interface** — it has no native generator-outage primitive. Two workarounds:

> **Option A (simple)**: use `load_step` to add load equal to the lost generation at the same bus.
> **Option B (deep)**: extend the `FaultEvent` interface (this requires modifying pylectra internals — not just adding a plugin).

In practice 80 % of research uses bus_fault / line_trip / load_step / composite, which already cover most scenarios.

## Composite faults — chain events

No new plugin needed; nest in YAML:

```yaml
fault:
  kind: composite
  params:
    events:
      - kind: bus_fault
        params: {bus: 16, t_fault: 0.2, duration: 0.05}    # short-circuit
      - kind: line_trip
        params: {branch: 21, t_trip: 0.30}                  # outage
      - kind: load_step
        params: {bus: 4, t_step: 1.0, delta_pd: 100.0}      # load jump
```

`composite` `vstack`s sub-event arrays and time-sorts them.

## Test it

```python
# tests/unit/test_my_fault.py
import numpy as np
from pylectra.registry import get

def test_bus_fault_impedance_arrays():
    cls = get("fault", "bus_fault_impedance")
    f = cls(bus=10, t_fault=0.1, duration=0.05, fault_susceptance=-50.0)
    event, bus_arr, line_arr = f.build_arrays()

    assert event.shape == (2, 2)              # apply + clear
    assert bus_arr[0, 0] == 0.10              # apply time
    assert bus_arr[0, 3] == -50.0             # fault susceptance
    assert bus_arr[1, 0] == 0.15              # clearing time
    assert bus_arr[1, 3] == 0.0               # restore on clear
    assert line_arr.size == 0
```

## Troubleshooting

### Event isn't firing during simulation

The engine isn't seeing the event. Common causes:

- The `event` array isn't `float` dtype (the kind column must also be float!).
- `bus` / `branch` indices used 0-based — pylectra expects **1-based**.

### System doesn't recover after clearing

The clear-event value is wrong. For `bus_fault` the clear sets BS back to **0** — if the original BS was non-zero, restore it explicitly via a `composite` fault.

## Next steps

- [Add a new scenario generator](add-new-scenario.md) — batch-mode perturbation logic.
- [bus_fault source](https://github.com/pylectra/pylectra/blob/main/pylectra/faults/bus_fault.py) — the simplest built-in for reference.
