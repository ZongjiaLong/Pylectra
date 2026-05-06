# Built-in plugins catalog

_Reference_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md)

Per-category list of built-in plugins, their `params` / `options`, and source location.

## Cases (`case`)

Loaded via `pandapower.networks`.

| name | buses | source |
|---|---|---|
| `case9` | 9 | WSCC 9-bus |
| `case14` | 14 | IEEE 14-bus |
| `case30` | 30 | IEEE 30-bus |
| `case39` | 39 | IEEE 39-bus (New England) |
| `case57` | 57 | IEEE 57-bus |
| `case118` | 118 | IEEE 118-bus |

Source: `pylectra/cases/pp_builtin.py`

```yaml
case_pf: case39
```

## Power-flow (`power_flow`)

| name | description | options |
|---|---|---|
| `newton` | Newton-Raphson (default) | `tolerance_mva`, `max_iteration` |
| `pandapower` | pandapower runpp | `algorithm` (nr/bfsw/gs/fdbx/fdxb), `tolerance_mva`, `max_iteration` |

## ODE solvers (`ode_solver`)

### Legacy fixed-step

| name | algorithm | step source |
|---|---|---|
| `modified_euler` | Modified Euler | `case_dyn.stepsize` |
| `runge_kutta` | RK4 | same |
| `rkf` | RK Fehlberg 4(5) | same |
| `rkhh` | RK Higham–Hall 4(5) | same |

### scipy adaptive

`pylectra/solvers/scipy_solvers.py`

| name | algorithm | when to use |
|---|---|---|
| `scipy_rk23` | RK 2(3) | low precision, fast |
| `scipy_rk45` | RK 4(5) Dormand–Prince | **general default** |
| `scipy_dop853` | RK 8(7) Dormand–Prince | **high precision** |
| `scipy_lsoda` | LSODA (auto-stiff) | ill-conditioned systems |
| `scipy_bdf` | BDF | strongly stiff |
| `scipy_radau` | Radau IIA 5 | strongly stiff + high accuracy |

Common options: `rtol`, `atol`, `max_step`, `first_step`.

### torch (`pylectra/solvers/torch_solvers.py`)

| name | algorithm | adaptive |
|---|---|---|
| `torch_dopri5` | RK 5(4) | yes |
| `torch_dopri8` | RK 8(7) | yes |
| `torch_rk4` | RK4 | no |
| `torch_euler` | Euler | no |

Extra options: `chunk_seconds`, `torch_dtype`, `device`, `dense_n`. See [GPU acceleration](../tutorials/06-gpu-acceleration.md).

## Faults (`fault`) {#faults}

### `bus_fault` — three-phase bus short

```yaml
fault:
  kind: bus_fault
  params:
    bus: 16             # 1-based
    t_fault: 0.2        # [s]
    duration: 0.05      # [s]
```

### `line_trip` — line outage

```yaml
params:
  branch: 21            # 1-based branch row
  t_trip: 0.3
  reclose_after: null   # null = permanent; positive = reclose after that many seconds
```

### `load_step` — load step change

```yaml
params:
  bus: 4
  t_step: 1.0
  delta_pd: 100.0       # [MW]
  delta_qd: 30.0        # [MVAr]
  duration: null        # null = permanent
```

### `composite` — chained events

```yaml
params:
  events:
    - {kind: bus_fault,  params: {...}}
    - {kind: line_trip,  params: {...}}
    - {kind: load_step,  params: {...}}
```

Source: `pylectra/faults/`

## Generators (`generator`)

| name | order | states |
|---|---|---|
| `classical` | 2 | δ, ω, |E'|, 0 |
| `two_axis` | 4 | δ, ω, Eq', Ed' |

`Pgen` column conventions in each file's docstring. Source: `pylectra/models/generators/`.

## Exciters (`exciter`)

| name | description |
|---|---|
| `simple_avr` | First-order AVR with cosine voltage feedback |
| `constant` | Constant Efd (no excitation control) |

## Governors (`governor`)

| name | description | states |
|---|---|---|
| `constant_power` | dPm/dt = 0 | 1 (Pm only) |
| `ieee_g` | 4-state IEEE turbine-governor | Pm, P, x, z |

## PSS (`pss`)

| name | description |
|---|---|
| `none` | No PSS |

## Scenarios (`scenario`)

| name | params |
|---|---|
| `load_perturb` | `sigma_pct` (default 5), `clip_pct` (default 20) |
| `line_outage` | `n_outages` (default 1), `prob` (default 0.5) |
| `noop` | — |

## Filters (`filter`)

| name | params |
|---|---|
| `pf_converged` | — |
| `voltage_range` | `vmin` (0.85), `vmax` (1.15), `tail_fraction` (1.0) |
| `angle_stability` | `max_dev_deg` (180) |
| `simulation_completed` | `tol` (1e-6) |
| `small_signal_stable` | `margin_max` (0.0) |

## Small-signal (`small_signal`)

| name | description |
|---|---|
| `finite_difference` | Numerical Jacobian via finite differences |
| `modal` | Same + damping-sorted + eigenvectors by default |

Common options: `epsilon`, `method`, `drop_reference_mode`, `return_eigenvectors`, `return_jacobian`.

## Plots (`plot`)

| name | input_kind | key kwargs |
|---|---|---|
| `rotor_angles` | single | `relative`, `gen_indices`, `palette` |
| `speeds` | single | `gen_indices` |
| `voltages` | single | `bus_indices` |
| `efds` | single | `gen_indices` |
| `overview` | single | — |
| `topology` | case | `color_by`, `cmap`, `bus_size`, `seed` |
| `acceptance` | batch | — |
| `histogram` | batch | `column`, `bins` |
| `violin` | batch | `column`, `by` |
| `heatmap` | batch | `column`, `rows`, `cols`, `aggfunc`, `cmap` |

Source: `pylectra/plotting/`

## List registered plugins at runtime

```bash
python -m pylectra info
```

or in Python:

```python
import pylectra
from pylectra import registry
for cat in ["generator", "exciter", "governor", "pss", "ode_solver",
            "power_flow", "fault", "case", "scenario", "filter",
            "small_signal", "plot"]:
    print(cat, registry.list_plugins(cat)[cat])
```

## Next steps

- [pylectra.registry API](api/registry.md)
- [pylectra.interfaces ABCs](api/interfaces.md)
