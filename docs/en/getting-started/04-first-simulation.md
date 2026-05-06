# Your first simulation

_Beginner_

**Prerequisites:** [Install Pylectra](03-install-pylectra.md), [5-minute YAML guide](../concepts/what-is-yaml.md)

This page walks through one full simulation of the IEEE 39-bus system with a three-phase fault on bus 16, and dissects every YAML field.

## Run it

From the pylectra source root (Path 2 / 3 users):

```bash
conda activate pylectra-env       # activate if not already
python -m pylectra run examples/single_case39.yaml
```

You should see roughly:

```
> Loading dynamic simulation data...
> Power flow converged
> Constructing augmented admittance matrix...
> Calculating initial state...
> System in steady-state
> Running dynamic simulation...
> Simulation completed in  9.42 seconds
```

If `plot: true` is set, a matplotlib window opens with rotor-angle trajectories of the 10 generators — wild swings during the fault, gradual convergence after clearing.

## Anatomy of the YAML

Open `examples/single_case39.yaml`:

```yaml
mode: single                        # 1

case_pf: case39                     # 2
case_dyn: case39dyn

power_flow:                         # 3
  kind: newton

solver:                             # 4
  kind: modified_euler

fault:                              # 5
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05

verbose: 1                          # 6
plot: true
```

Field-by-field:

### ① `mode: single`

One of three modes:

- `single` — one deterministic simulation (this page).
- `batch` — multi-scenario dataset generation.
- `cct` — critical-clearing-time bisection.

### ② `case_pf` / `case_dyn`

The grid case to simulate.

- `case_pf` is the steady-state power-flow case (**case39** = IEEE 39-bus benchmark).
- `case_dyn` is the dynamic-parameters file (machine inertias, exciter gains, governor settings, etc.).

Built-in cases include case 9 / 14 / 30 / 39 / 57 / 118. See [Built-in plugins](../reference/plugins-catalog.md) for the full list.

### ③ `power_flow`

The power-flow solver:

- `kind: newton` — classical Newton-Raphson (default).
- `kind: pandapower` — pandapower backend (more robust; needs `pip install pandapower`).

### ④ `solver`

The ODE solver:

| Name | Type | When to use |
|---|---|---|
| `modified_euler` | fixed-step | Default; fast, comparable to original MATLAB output |
| `runge_kutta` / `rkf` / `rkhh` | fixed / adaptive | Legacy compatibility |
| `scipy_rk45` / `scipy_dop853` | adaptive, high accuracy | Recommended for serious numerics |
| `scipy_lsoda` / `scipy_bdf` | stiff-aware adaptive | Stiff systems |
| `torch_dopri5` etc. | optional GPU | Large grids, large batches |

Full list: [YAML schema](../reference/yaml-schema.md).

### ⑤ `fault`

The disturbance to apply. This example: a three-phase fault at bus 16 starting at `t = 0.2 s`, cleared after `0.05 s` (3 cycles at 60 Hz).

Common fault types:

- `bus_fault` — three-phase bus short-circuit.
- `line_trip` — line outage.
- `load_step` — load step change.
- `composite` — sequence of any of the above.

### ⑥ `verbose` / `plot`

- `verbose: 1` prints progress (`0` is silent).
- `plot: true` opens a matplotlib window after completion.

## Same thing via the Python API

The CLI is the "install-and-go" path. From a Notebook or script:

```python
from pylectra.run import run

# Pass a YAML path
out = run("examples/single_case39.yaml")

# Inspect the output
print(f"Wall time: {out.result.simulation_time:.2f} s")
print(f"Time points: {out.result.Time.shape[0]}")
print(f"Generators:  {out.result.Angles.shape[1]}")
print(f"Max angle deviation: {out.result.max_angle_deviation_deg:.2f}°")
```

You can also pass a **dict** — equivalent to writing YAML in Python:

```python
out = run({
    "mode": "single",
    "case_pf": "case39",
    "case_dyn": "case39dyn",
    "power_flow": {"kind": "newton"},
    "solver": {"kind": "modified_euler"},
    "fault": {
        "kind": "bus_fault",
        "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05},
    },
    "plot": False,
})
```

Or **override a single field** (handy for parameter sweeps):

```python
# Sweep fault duration
for d in [0.05, 0.10, 0.15, 0.20]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": d}})
    print(f"duration={d:.2f}s, max dev={out.result.max_angle_deviation_deg:.1f}°")
```

## Try variations

Modify a few YAML fields and rerun:

| Change | How | Expected effect |
|---|---|---|
| Faulted bus | `bus: 16` → `bus: 4` | Different bus — different swing amplitudes |
| Fault duration | `duration: 0.05` → `duration: 0.20` | Closer to instability; may diverge |
| Solver | `kind: modified_euler` → `kind: scipy_dop853` | Same trajectory, ~half the steps, higher accuracy |
| Disable plot | `plot: true` → `plot: false` | No window; just exit |

## No plot window?

- Confirm `plot: true` in the YAML.
- Don't pass `--no-plot` on the CLI.
- macOS users sometimes need a specific matplotlib backend. The simpler approach: use the dedicated plotting CLI:
  ```bash
  python -m pylectra plot examples/single_case39.yaml --type rotor_angles --output rotor.pdf
  ```

## Next steps

- [Understanding the output files](05-understand-output.md) — what files pylectra produces and how to open them.
- [Single deterministic simulation (tutorial)](../tutorials/01-single-run.md) — go deeper on each field.
