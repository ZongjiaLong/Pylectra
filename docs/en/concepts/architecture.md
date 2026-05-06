# Pylectra architecture overview

_Intermediate_

**Prerequisites:** [What is a plugin](what-is-plugin.md)

## At a glance

```
                    YAML config / Python dict
                            │
                            ▼
                  ┌───────────────────┐
                  │  pylectra.config  │  ← parse, validate
                  │  ExperimentConfig │
                  └─────────┬─────────┘
                            │
              mode = single / batch / cct
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │           pylectra.runners             │
        │  SingleRunner   BatchRunner   CCTRunner│
        └─────┬─────────────────┬────────────────┘
              │                 │
              │  joblib parallel│
              │                 │
              ▼                 ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  pylectra.engine │  │   pylectra.io    │
    │  (ODE + events)  │  │  HDF5 / Parquet  │
    └─────────┬────────┘  └──────────────────┘
              │
              │  ABC dispatch
              ▼
    ┌─────────────────────────────────────────┐
    │           pylectra.registry              │
    │  {category → {name → plugin class}}      │
    │                                          │
    │  generator   exciter   governor   pss    │
    │  ode_solver  power_flow  fault    case   │
    │  scenario    filter   small_signal plot  │
    └─────────────────────────────────────────┘
                  ▲
                  │ @register
                  │
    ┌─────────────────────────────────────────┐
    │      Plugin implementations (sub-pkgs)   │
    │  models/  faults/  scenarios/  filters/  │
    │  solvers/ powerflow/ plotting/ cases/    │
    └─────────────────────────────────────────┘
```

## Three layers

### Layer 1 — Config parsing

`pylectra.config.ExperimentConfig`: turns a YAML file or a Python `dict` into a strongly-typed object.
Responsibilities:

- YAML schema validation (missing fields, type checks).
- Path resolution (relative → absolute).
- Default-value filling.

The schema is fixed here; specific plugins are still resolved by name at runtime via the registry.

### Layer 2 — Runners

```python
from pylectra.runners import SingleRunner, BatchRunner, CCTRunner
```

One class per run mode; all expose the same `.run()` method:

| Runner | Purpose | Output |
|---|---|---|
| `SingleRunner` | One deterministic simulation | `SingleRunOutput` (contains a `SimulationResult`) |
| `BatchRunner` | Multi-scenario dataset generation | HDF5 files + Parquet metadata |
| `CCTRunner` | Bisection for critical clearing time | `CCTResult` |

`pylectra.run.run(config)` is the top-level entry point — it dispatches to the right runner based on `mode`.

### Layer 3 — Engine + Registry

#### Engine

```
pylectra/engine/
├── equilibrium.py    # Power flow + multi-machine init
├── rhs.py            # Assembles dy/dt = f(t, y) including network solve
├── loop.py           # scipy ODE main loop with event splitting
├── torch_engine.py   # torch ODE main loop (optional GPU)
└── state.py          # pack/unpack state vectors
```

The engine **is not a plugin** — it's infrastructure. But each step calls plugins through ABCs:

- Power flow → `power_flow` plugin (`pandapower` / `newton`)
- Generator derivatives → `generator` plugin (`two_axis`, `classical`)
- Exciter derivatives → `exciter` plugin
- ODE stepping → `ode_solver` plugin
- Fault on/off → `fault` plugin (event injection)

#### Registry

```python
pylectra.registry._REGISTRY = {
    "generator": {"two_axis": <class>, "classical": <class>},
    "exciter":   {"simple_avr": <class>, ...},
    ...
}
```

Twelve whitelisted categories; lookup is a plain dict at runtime. New categories are intentionally restricted; adding new plugins **inside** an existing category is fully open.

## Data flow for a single simulation (`mode: single`)

1. `run("xxx.yaml")` → `ExperimentConfig.from_yaml(...)`.
2. Mode dispatch instantiates `SingleRunner(cfg)`.
3. `SingleRunner.run()`:
   1. Look up `cfg.case_pf` in the `case` registry → `NetworkCase`.
   2. Look up `cfg.power_flow.kind` → run PF → equilibrium voltages.
   3. For each machine, fetch the right generator / exciter / governor / pss plugin and call `.init()` → multi-machine initial state.
   4. Stitch every plugin's `.derivative()` into a single `rhs(t, y)` callable.
   5. Look up `cfg.fault.kind` → event schedule.
   6. Look up `cfg.solver.kind` → feed `rhs` + events into the ODE solver.
   7. The solver advances time; one ODE call per "leg" (between fault on/off events).
   8. Wrap the trajectory into a `SimulationResult` and return.

## How the three modes relate

```
SingleRunner  ──────────────► one trajectory
                                    │
                                    ▼
BatchRunner  ──► loop N times ──► many trajectories ──► HDF5 / Parquet
   │             │
   │             └─► scenarios perturb the case → SingleRunner
   │
   └─► joblib parallelises N workers, each running an independent SingleRunner

CCTRunner  ──► bisection loop ──► many SingleRunner calls (varying fault duration) ──► CCT value
```

`BatchRunner` and `CCTRunner` both treat `SingleRunner` as an atomic operation — which is why `SingleRunner` must be **deterministic** and **pickle-safe** (joblib parallelism requires it).

## `pylectra/_legacy/`

A **private internal sub-package** holding the MATLAB-port code (PowerFlow / Models / Auxiliary / Solvers) translated from the original MatDyn. The current ODE main loop still depends on it. It is **transparent to end users** — you'll never see `pylectra._legacy` in the public API.

A future release will rewrite the loop natively on pandapower + scipy and `_legacy/` will be removed. This is the project's openly tracked technical debt — see "Known limitations" in [CHANGELOG.md](https://github.com/ZongjiaLong/Pylectra/blob/main/CHANGELOG.md).

## Plotting subsystem

```
pylectra/plotting/
├── plugins.py      # @register("plot", ...) for every built-in plot
├── time_series.py  # rotor_angles / speeds / efds / voltages / overview
├── topology.py     # network topology
├── batch_stats.py  # histogram / violin / heatmap / acceptance
├── style.py        # Nature-style rcParams
└── io.py           # vector PDF / high-DPI PNG export
```

`pylectra.plotting.render(name, data, ...)` looks up `name` in the registry and calls the matching class's `.render()`. The `pylectra plot ...` CLI uses the same path.

## Next steps

- [How to add a new generator model](../how-to/add-new-generator.md) — practice plugin authoring.
- [pylectra.registry module](../reference/api/registry.md) — registry API details.
