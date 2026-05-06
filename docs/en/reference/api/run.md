# `pylectra.run`

_Reference_

The top-level programmatic entry point. Anything that uses pylectra from Python instead of the CLI starts here.

## `run(config, **overrides)`

```python
def run(config: str | Path | dict | NetworkCase, **overrides) -> RunOutput
```

**Parameters**

| Param | Type | Notes |
|---|---|---|
| `config` | `str` / `Path` / `dict` | YAML path or pre-parsed dict |
| `**overrides` | any | Deep-merged into config (e.g. `solver={"kind": "scipy_dop853"}`) |

**Returns**

| Field | Type | Mode |
|---|---|---|
| `out.result` | `SimulationResult` / `BatchResult` / `CCTResult` | all |
| `out.case` | `NetworkCase` | single / cct |
| `out.scenario` | `Scenario` or None | single (if perturbed) |

**Examples**

```python
from pylectra.run import run

# YAML path
out = run("examples/single_case39.yaml")

# dict
out = run({"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
           "fault": {"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05}}})

# Override one field
out = run("examples/single_case39.yaml",
          solver={"kind": "scipy_dop853", "options": {"rtol": 1e-8}})
```

## `run_many(configs, **shared_overrides)`

```python
def run_many(configs: Iterable[ConfigLike], **shared_overrides) -> list
```

Runs each config serially and returns a list of `RunOutput`.

```python
configs = [
    {"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
     "fault": {"kind": "bus_fault",
               "params": {"bus": b, "t_fault": 0.2, "duration": 0.05}}}
    for b in [4, 16, 23]
]
results = run_many(configs)
for cfg, out in zip(configs, results):
    print(cfg["fault"]["params"]["bus"], out.result.max_angle_deviation_deg)
```

> Need parallel? Wrap with joblib yourself. `run_many` is intentionally serial so it works even when objects aren't picklable.

## `SimulationResult` fields (single mode)

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

# Trajectories
res.Time          # (N,)         [s]
res.Voltages      # (N, n_bus)   complex
res.Angles        # (N, n_gen)   [deg]
res.Speeds        # (N, n_gen)   [p.u.]
res.Eq_trs        # (N, n_gen)
res.Ed_trs        # (N, n_gen)
res.Efds          # (N, n_gen)
res.Tes           # (N, n_gen)   electrical torque
res.TM            # (N, n_gen)   mechanical torque
res.Vss           # (N, n_gen)   PSS output
res.Stepsize      # (N,)
res.Errest        # (N,)         (adaptive solvers only)

# Metadata
res.simulation_time              # wall time [s]
res.pf_success                   # bool
res.metadata                     # dict
res.small_signal                 # SmallSignalResult or None

# Conveniences
res.n_steps
res.n_bus
res.n_gen
res.voltage_magnitude            # |Voltages|
res.max_angle_deviation_deg      # vs. COI
```

## `BatchResult` fields (batch mode)

```python
out = run("examples/batch_case39.yaml")
br = out.result

br.n_total       # samples submitted
br.n_accepted    # passed every filter
br.n_rejected
br.n_pf_failed
br.duration      # total wall time [s]
br.directory     # output directory
br.metadata_path # parquet path
```

Per-sample `SimulationResult` objects are not held in `BatchResult` — read `directory/sample_*.h5` to get them.

## `CCTResult` fields (cct mode)

```python
out = run("examples/cct_case39.yaml")
cct = out.result

cct.cct          # critical clearing time [s]
cct.iterations   # bisection iterations
cct.bracket_low  # final bracket
cct.bracket_high
cct.converged    # bool
cct.note         # description if not converged
```

## Failure modes

When PF doesn't converge or the solver crashes:

- single: `res.pf_success = False`; time-series arrays have shape `(0, ...)`.
- batch: that sample's metadata has `passed=False, rejected_by="pf_converged"`; the rest of the batch continues.
- cct: a failed bracket check sets `cct.converged = False` and writes a `note`.

## Next steps

- [pylectra.registry](registry.md) — registry API.
- [pylectra.interfaces](interfaces.md) — ABCs by category.
