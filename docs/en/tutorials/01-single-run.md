# Single deterministic simulation

_Intermediate_

**Prerequisites:** [Your first simulation](../getting-started/04-first-simulation.md)

The Getting Started page got case39 running. This tutorial goes deeper: every adjustable field, solver selection, event configuration, troubleshooting.

## Full single-mode YAML

```yaml
mode: single

# ────── Case ──────
case_pf:  case39
case_dyn: case39dyn

# ────── Power flow ──────
power_flow:
  kind: newton                   # newton | pandapower
  options:
    tolerance_mva: 1.0e-8
    max_iteration: 20

# ────── ODE solver ──────
solver:
  kind: scipy_dop853             # recommended for serious numerics
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
    max_step: 0.01
    first_step: null             # null = let the solver guess

# ────── Fault ──────
fault:
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05

# ────── Output / logging ──────
verbose: 1                       # 0=silent, 1=progress lines, 2=verbose
plot: false                      # open a matplotlib window after run
```

## Choosing a solver

### Decision tree

```
Need high precision?  ─── yes ──► scipy_dop853
       │
       no
       │
Need bit-comparable to original MATLAB?  ─── yes ──► modified_euler
       │
       no
       │
Stiff system (eigenvalues across orders of magnitude)?  ─── yes ──► scipy_lsoda or scipy_bdf
       │
       no
       │
       └──► scipy_rk45 (best general-purpose default)
```

### Empirical comparison

Same case39 + bus 16 fault, 10 s sim:

| Solver | Steps | Wall (s) | 5 s rotor angle error vs dop853 |
|---|---|---|---|
| `modified_euler` | 10 024 | 9.4 | 1e-2 |
| `scipy_rk45` | 1 100 | 4.8 | 1e-5 |
| `scipy_dop853` | 600 | 5.1 | 0 (reference) |
| `scipy_lsoda` | 850 | 4.5 | 1e-5 |
| `torch_dopri5` | 600 | 2.6 (CPU) | 1e-4 |

**Default recommendation: `scipy_dop853`** — high accuracy, fewest steps.

### Solver options

```yaml
solver:
  kind: scipy_dop853
  options:
    rtol: 1.0e-6                # relative tolerance (default 1e-3)
    atol: 1.0e-8                # absolute tolerance (default 1e-6)
    max_step: 0.01              # max step [s]; tighten near events
    first_step: 0.001           # initial step guess
```

> Tighter tolerances → more steps, longer wall time, more numerical stability.
> For **batch dataset generation**, `rtol=1e-4 atol=1e-6` is a sensible compromise.

## Fault types in detail

### `bus_fault` — three-phase bus short circuit

```yaml
fault:
  kind: bus_fault
  params:
    bus: 16            # 1-based bus number
    t_fault: 0.2       # fault apply time [s]
    duration: 0.05     # fault duration [s]; cleared automatically after
```

Implementation: bus shunt is set to a near-short during the fault, restored at `t_fault + duration`.

### `line_trip` — line outage

```yaml
fault:
  kind: line_trip
  params:
    branch: 21         # 1-based branch index (row of the case's branch matrix)
    t_trip: 0.3
    reclose_after: 0.5   # optional; omit for permanent outage
```

### `load_step` — load step change

```yaml
fault:
  kind: load_step
  params:
    bus: 4
    t_step: 1.0
    delta_pd: 100.0    # added active power [MW]
    delta_qd: 30.0     # added reactive power [MVAr]
    duration: 2.0      # optional; omit for permanent step
```

### `composite` — chained events

Simulate cascading faults:

```yaml
fault:
  kind: composite
  params:
    events:
      - kind: bus_fault
        params: {bus: 16, t_fault: 0.2, duration: 0.05}
      - kind: line_trip
        params: {branch: 21, t_trip: 0.30}
      - kind: load_step
        params: {bus: 4, t_step: 1.0, delta_pd: 100.0}
```

Sub-events are sorted by time and triggered in order.

## Programmatic field overrides

Don't duplicate YAML for each variant — use keyword overrides on `run()`:

```python
from pylectra.run import run

# Sweep the faulted bus
results = {}
for bus in [4, 16, 23, 30]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": 0.05}})
    results[bus] = out.result.max_angle_deviation_deg
    print(f"bus {bus}: max angle dev {results[bus]:.2f}°")
```

`run()` deep-merges keywords into the YAML — the source file is never touched.

## Changing generator models

case39 defaults to the `two_axis` (4th-order) model. To switch all machines to `classical` (2nd-order swing):

```yaml
dynamics:
  defaults:
    generator: {kind: classical}
    exciter:   {kind: constant}
    governor:  {kind: constant_power}
    pss:       {kind: none}
```

> This field is a 0.1.0 extension point; current example YAMLs don't use it — the legacy engine still dispatches by the model-type column inside `case_dyn`. The next phase of Phase 8 promotes `dynamics` to the primary path.

## Troubleshooting

### "power flow did not converge"

Possible causes:

- The case is genuinely ill-conditioned (try `power_flow.kind: pandapower` — it's more robust).
- Tolerance too tight (default 1e-8 → loosen to 1e-6).
- A perturbation pushed the load past the solvable region (typical in batch mode).

### "Native engine supports PSS type 3 only"

You picked a scipy solver but `case_dyn` contains a non-3 PSS type. Two fixes:

- Disable PSS (set the PSS type column to 3 in `case_dyn`).
- Use a legacy solver (`solver: {kind: modified_euler}`).

### Rotor angle blows up

The fault is too severe. Try:

- Shortening `duration`.
- Picking a different bus.
- Tighter `solver.options.max_step` (rules out numerical instability).

## Verify events actually fired

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

# During the fault, bus 16 voltage should collapse to near zero
import numpy as np
fault_idx = np.where((res.Time >= 0.20) & (res.Time <= 0.25))[0]
print(f"|V| at bus 16 during fault: {np.abs(res.Voltages[fault_idx, 15]).max():.3f}")
# Expected ≈ 0.0
```

## Next steps

- [Batch dataset generation](02-batch-generation.md) — extend single runs to N perturbed scenarios.
- [Complete YAML schema](../reference/yaml-schema.md) — defaults and ranges for every field.
- [Visualization tutorial](04-visualization.md) — turn single-run results into publication-quality plots.
