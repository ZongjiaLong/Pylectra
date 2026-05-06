# Complete YAML schema

_Reference_

Type, default, and value range for every field.

## Top-level fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `mode` | str | required | `single` / `batch` / `cct` |
| `case_pf` | str / dict / NetworkCase | required | Power-flow case (name, mpc dict, or NetworkCase) |
| `case_dyn` | str / dict | required | Dynamic-parameters file name (e.g. `case39dyn`) |
| `power_flow` | dict | `{kind: newton}` | See below |
| `solver` | dict | `{kind: modified_euler}` | See below |
| `fault` | dict / null | null | See below |
| `verbose` | int | `1` | 0=silent / 1=progress / 2=verbose |
| `plot` | bool | `false` | Open a matplotlib window after run |
| `skip_integration` | bool | `false` | Equilibrium-only (small-signal use case) |
| `dynamics` | dict | null | Multi-machine model assignment (overrides `case_dyn`) |
| `small_signal` | dict | null | See below; works in single / batch |
| `scenarios` | dict | null (required for batch) | See below |
| `filters` | list[dict] | null (used by batch / cct) | See below |
| `output` | dict | null (required for batch) | See below |
| `cct` | dict | null (required for cct) | See below |

## `power_flow`

```yaml
power_flow:
  kind: newton            # newton | pandapower
  options:
    tolerance_mva: 1.0e-8
    max_iteration: 20
    algorithm: nr         # pandapower only: nr | bfsw | gs | fdbx | fdxb
```

## `solver`

```yaml
solver:
  kind: modified_euler    # see plugins-catalog
  options:
    rtol: 1.0e-6          # adaptive solvers only
    atol: 1.0e-8
    max_step: 0.01
    first_step: null

    # torch backend extras
    chunk_seconds: null   # null or positive number; see GPU tutorial
    torch_dtype: float64  # float64 | float32
    device: auto          # auto | cuda | mps | cpu
    dense_n: 200          # output points per leg
```

## `fault`

```yaml
fault:
  kind: bus_fault         # bus_fault | line_trip | load_step | composite
  params:                 # fields depend on kind
    bus: 16
    t_fault: 0.2
    duration: 0.05
```

Per-kind fields: see [Plugins catalog](plugins-catalog.md#faults).

## `dynamics`

```yaml
dynamics:
  defaults:
    generator: {kind: two_axis,        params_file: null}
    exciter:   {kind: simple_avr}
    governor:  {kind: ieee_g}
    pss:       {kind: none}
  overrides:                           # per-generator overrides
    - id: 30
      generator: {kind: classical}
      pss: {kind: none}
```

## `scenarios` (required for batch)

```yaml
scenarios:
  count: 200              # total samples
  seed: 42                # master seed (sub-seed_i = seed + i)
  generators:             # applied in declaration order
    - kind: load_perturb
      params: {sigma_pct: 5.0, clip_pct: 20.0}
    - kind: line_outage
      params: {n_outages: 1, prob: 0.5}
```

## `filters` (used by batch / cct)

```yaml
filters:
  - kind: pf_converged
  - kind: voltage_range
    params: {vmin: 0.85, vmax: 1.15, tail_fraction: 0.5}
  - kind: angle_stability
    params: {max_dev_deg: 180.0}
  - kind: simulation_completed
  - kind: small_signal_stable
    params: {margin_max: 0.0}
```

## `output` (required for batch)

```yaml
output:
  directory: ./samples
  format: hdf5            # hdf5 | npz
  metadata: parquet       # parquet | csv
  keep_failed: false
  parallel:
    n_jobs: -1            # int / -1 / "auto"
    backend: loky         # loky | multiprocessing | threading
    batch_size: 4
```

## `cct` (required for cct)

```yaml
cct:
  bus: 16
  t_fault: 0.2
  low: 0.01
  high: 0.30
  tol: 0.005
  max_iter: 15
  stability_filter:
    kind: angle_stability
    params: {max_dev_deg: 180.0}
```

## `small_signal`

```yaml
small_signal:
  kind: finite_difference   # finite_difference | modal
  options:
    epsilon: 1.0e-7
    method: central         # central | forward
    drop_reference_mode: true
    stability_tolerance: 1.0e-4
    return_jacobian: false
    return_eigenvectors: false
```

## YAML type gotchas

| Written | Parsed as |
|---|---|
| `0.05` | float |
| `1.0e-6` | float (decimal point required!) |
| `1e-6` | **string** — not float (YAML 1.1 quirk) |
| `null` | None |
| `~` | None (same) |
| `yes` / `on` / `true` | bool True |
| `no` / `off` / `false` | bool False |
| `1.0` | float 1.0 |
| `"1.0"` | str "1.0" |

## Override from Python

`run()` deep-merges keyword arguments:

```python
from pylectra.run import run
out = run("examples/single_case39.yaml",
          solver={"kind": "scipy_dop853"},                    # replaces full solver block
          fault={"kind": "bus_fault",
                 "params": {"bus": 4, "t_fault": 0.2,
                            "duration": 0.10}})
```

## Next steps

- [Plugins catalog](plugins-catalog.md) — every legal value for `kind`.
- [CLI reference](cli.md) — `python -m pylectra ...` commands.
