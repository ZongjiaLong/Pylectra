# Load a MATPOWER `.m` case

_Intermediate_

**Prerequisites:** [Single deterministic simulation](../tutorials/01-single-run.md)

## Goal

Feed a MATPOWER `.m` case file into pylectra.



## Before you start — built-in cases

The standard IEEE benchmark systems are already wired up. If your need
matches one of these, **no conversion is required** — reference the name
directly in YAML:

| Case name (`case_pf`) | Dynamic name (`case_dyn`) | Buses / Gens |
| --------------------- | ------------------------- | ------------ |
| `case9`               | `case9dyn`                | 9 / 3        |
| `case14`              | `case14dyn`               | 14 / 5       |
| `case30`              | `case30dyn`               | 30 / 6       |
| `case39`              | `case39dyn`               | 39 / 10      |
| `case57`              | `case57dyn`               | 57 / 7       |
| `case68`              | `case68dyn`               | 68 / 16      |
| `case118`             | `case118dyn`              | 118 / 54     |

The three paths below are for cases **outside** that list (IEEE 145, 300,
custom utility models, etc.).

## Three paths

### Path A — convert with pandapower → JSON

Most reliable. pandapower ships a MATPOWER parser; convert once, save as JSON, then use the result like any built-in case.

```python
import pandapower as pp
from pandapower.converter import from_mpc

# 1. Read .m
net = from_mpc("path/to/your_case.m")

# 2. Verify the power flow solves
pp.runpp(net)
print(f"PF converged: {len(net.res_bus) > 0}")

# 3. Persist as pandapower JSON
pp.to_json(net, "your_case.json")
```

### Path B — write a CaseLoader plugin

Register your MATPOWER file in the case registry so YAML can reference it as `kind: my_case`:

```python
# pylectra/cases/my_matpower_case.py
from pylectra.interfaces.case_loader import CaseLoader
from pylectra.core.case import NetworkCase
from pylectra.registry import register


@register("case", "ieee300_matpower")
class IEEE300FromMatpower(CaseLoader):
    name = "ieee300_matpower"

    def load(self, identifier):
        from pandapower.converter import from_mpc
        try:
            from pandapower.converter import to_mpc            # pandapower < 3.0
        except ImportError:
            from pandapower.converter.matpower.to_mpc import to_mpc  # pandapower >= 3.0
        net = from_mpc("/path/to/case300.m")
        try:
            raw = to_mpc(net, init="flat")
        except TypeError:
            raw = to_mpc(net)
        mpc = raw.get("mpc", raw)
        return NetworkCase(mpc, net=net)
```

YAML:

```yaml
case_pf: ieee300_matpower      # use the registry name directly
```

### Path C — pass a dict to NetworkCase

If you have raw mpc-style numpy arrays:

```python
from pylectra.core.case import NetworkCase
import numpy as np

case = NetworkCase({
    "baseMVA": 100.0,
    "bus":    np.array([...]),     # shape (n_bus, ≥13)
    "gen":    np.array([...]),     # shape (n_gen, ≥21)
    "branch": np.array([...]),     # shape (n_branch, ≥13)
})

# Pass straight to run()
from pylectra.run import run
out = run({
    "mode": "single",
    "case_pf": case,                # NetworkCase objects are accepted
    "case_dyn": "case39dyn",
    "fault": {"kind": "bus_fault", "params": {"bus": 1, "t_fault": 0.2, "duration": 0.05}},
})
```

## What about `case_dyn`?

MATPOWER only ships static cases — no generator dynamic parameters. Options:

- **Reuse an existing one**: if your topology resembles case39 (10 generators), adapt `case39dyn`.
- **Author your own**: follow `case39dyn`'s format and write a `.py` file.
- **MatDyn `case39dyn.m`-style**: pylectra's legacy loader reads MATLAB MatDyn dynamic files directly.

Quickest stopgap — apply a single set of **defaults to every machine**:

```python
# pylectra/cases/default_dyn.py (sketch)
import numpy as np

def make_default_dyn(n_gen, freq=60.0):
    """Conservative default 4th-order parameters for n_gen machines."""
    Pgen = np.zeros((n_gen, 14))
    for i in range(n_gen):
        Pgen[i, :] = [
            2,      # genmodel = 2 (4th-order)
            3,      # excmodel = 3
            3,      # pssmodel = 3
            1,      # govmodel = 1
            0,      # bus (fill in later)
            0,      # PG
            5.0,    # H
            0,      # D
            0.30,   # xd_tr
            0.55,   # xq_tr
            1.80,   # xd
            1.70,   # xq
            8.00,   # Td0_tr
            0.40,   # Tq0_tr
        ]
    return Pgen
```

> ⚠️ **Use defaults with care** — fine for prototyping but never for serious studies. Use real parameters from manufacturer data or PSS/E records.

## End-to-end workflow

```python
"""Run a case39-style fault on MATPOWER's case300.m."""
import pandapower as pp
from pandapower.converter import from_mpc
try:
    from pandapower.converter import to_mpc                     # pandapower < 3.0
except ImportError:
    from pandapower.converter.matpower.to_mpc import to_mpc     # pandapower >= 3.0
from pylectra.core.case import NetworkCase
from pylectra.run import run

# 1. Convert
net = from_mpc("case300.m")
try:
    raw = to_mpc(net, init="flat")
except TypeError:
    raw = to_mpc(net)
mpc_dict = raw.get("mpc", raw) if isinstance(raw, dict) else raw
case = NetworkCase(mpc_dict, net=net)

# 2. Run (case300 has no case300dyn — write your own or skip integration)
out = run({
    "mode": "single",
    "case_pf": case,
    "case_dyn": "case39dyn",            # mismatched dynamic data, illustrative only
    "skip_integration": True,            # only equilibrium + small-signal
    "small_signal": {"kind": "modal"},
    "verbose": 1,
})

print(f"PF converged: {out.result.pf_success}")
```

## Troubleshooting

### `from_mpc` "could not parse"

- File encoding: MATPOWER `.m` files are ASCII; non-ASCII comments break the parser. Re-encode as UTF-8 and remove non-ASCII chars (or convert to plain ASCII comments).
- Old MATPOWER version: cases predating v6 may lack required fields. pandapower recommends v7+.

### `pp.runpp(net)` doesn't converge but the original MATLAB did

- Zero-impedance branches: pandapower rejects them by default; try `pp.runpp(net, distributed_slack=True)`.
- Slack assignment differs: MATPOWER uses the bus with `bus_type=3`; pandapower's `ext_grid` is auto-attached to the first such bus during `from_mpc` and may differ from the original MATLAB choice.

### After the convert pylectra can't find the case

`from_mpc` alone isn't enough — **either persist with `pp.to_json` or wire it through a CaseLoader plugin**; pylectra doesn't scan disk for `.m` files.

## Next steps

- [YAML schema](../reference/yaml-schema.md) — every supported `case_pf` / `case_dyn` form.
- [Architecture overview](../concepts/architecture.md) — how `NetworkCase` flows through the engine.
