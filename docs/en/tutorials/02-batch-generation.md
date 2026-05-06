# Batch dataset generation

_Intermediate_

**Prerequisites:** [Single deterministic simulation](01-single-run.md), [5-minute YAML guide](../concepts/what-is-yaml.md)

Batch mode is the most powerful feature of pylectra: starting from a baseline case, **automatically generate N perturbed scenarios**, run a simulation for each, and **keep the ones that pass a filter chain**. Common uses: training ML models, statistical stability studies, probabilistic power flow.

## A complete batch YAML

```yaml
mode: batch

# ────── Baseline ──────
case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: modified_euler}

# ────── Fault (the same fault is applied to every scenario) ──────
fault:
  kind: bus_fault
  params: {bus: 16, t_fault: 0.2, duration: 0.05}

# ────── Scenario generation ──────
scenarios:
  count: 200                          # generate 200 samples
  seed: 42                            # master seed (reproducible)
  generators:
    - kind: load_perturb
      params:
        sigma_pct: 5.0                # 5 % Gaussian noise on each load
        clip_pct: 20.0                # clipped at ±20 %
    - kind: line_outage
      params:
        n_outages: 1                  # randomly trip 1 line per sample
        prob: 0.5                     # only on 50 % of samples

# ────── Filter chain ──────
filters:
  - kind: pf_converged                # reject if PF didn't converge
  - kind: voltage_range
    params: {vmin: 0.85, vmax: 1.15, tail_fraction: 0.5}
  - kind: angle_stability
    params: {max_dev_deg: 180.0}
  - kind: simulation_completed

# ────── Output ──────
output:
  directory: ./out_batch
  format: hdf5                        # hdf5 | npz
  metadata: parquet                   # parquet | csv
  keep_failed: false                  # also write rejected samples?
  parallel:
    n_jobs: -1                        # -1 = all CPU cores
    backend: loky                     # loky | multiprocessing | threading

verbose: 1
```

## Core concepts

### Scenario generators

Before producing each sample, pylectra **clones the baseline case** and applies the perturbations in `scenarios.generators` **in order**.

Three built-ins:

| Name | What it does | Key params |
|---|---|---|
| `load_perturb` | Adds Gaussian noise to each bus's PD/QD | `sigma_pct`, `clip_pct` |
| `line_outage` | Randomly trips a few lines | `n_outages`, `prob` |
| `noop` | Does nothing (control group) | — |

To write your own → see [How to add a scenario generator](../how-to/add-new-scenario.md).

### Filter chain

After the simulation, pylectra evaluates each filter in order; **any rejection** marks the sample `passed=False`.

Five built-ins:

| Name | Reject when |
|---|---|
| `pf_converged` | Initial power flow didn't converge |
| `voltage_range` | Any bus voltage left `[vmin, vmax]` |
| `angle_stability` | Any generator angle deviated from the COI by more than `max_dev_deg` |
| `simulation_completed` | The simulation didn't reach `stoptime` (solver gave up) |
| `small_signal_stable` | Small-signal eigenvalues have positive real parts |

`voltage_range`'s `tail_fraction: 0.5` means **only check the last 50 % of the trajectory** — skipping the natural voltage dip during the fault and focussing on post-clearing recovery.

## Run it

```bash
python -m pylectra run examples/batch_case39.yaml
```

Sample output:

```
[batch] 1/200 ACCEPT
[batch] 2/200 REJECT (voltage_range: bus 12 dipped to 0.81 pu)
[batch] 3/200 ACCEPT
...
[batch] done: 152/200 accepted (38 rejected, 10 PF-failed) in 184.2s, n_jobs=8.
        metadata: ./out_batch/metadata.parquet
```

## Inspect the results

### Parquet metadata — per-sample metrics

```python
import pandas as pd

meta = pd.read_parquet("./out_batch/metadata.parquet")
print(meta.shape)                    # (200, ~20)
print(meta.columns.tolist())

# Acceptance rate
print(f"Acceptance: {meta['passed'].mean():.1%}")

# Top rejection reasons
print(meta[~meta["passed"]]["rejected_by"].value_counts())

# Correlations between perturbation params and stability metrics
import numpy as np
ok = meta[meta["passed"]]
corr = ok[[c for c in ok.columns if c.startswith("meta:") or c.startswith("filter_")]].corr()
print(corr["filter_angle_stability_metric"].sort_values(ascending=False).head(5))
```

### HDF5 time-series — per-sample trajectories

```python
import h5py
import numpy as np

# Max angle deviation from the COI for every accepted sample
ok_ids = meta[meta["passed"]]["sample_id"].tolist()
all_max_devs = []
for sid in ok_ids:
    with h5py.File(f"./out_batch/sample_{sid:06d}.h5", "r") as f:
        ang = f["Angles"][:]                             # (T, n_gen)
        max_dev = np.max(np.abs(ang - ang.mean(axis=1, keepdims=True)))
        all_max_devs.append(max_dev)

import matplotlib.pyplot as plt
plt.hist(all_max_devs, bins=30)
plt.xlabel("max angle deviation [°]")
plt.ylabel("count")
plt.show()
```

## Determinism (reproducibility)

Batch mode is **strictly deterministic**:

- `scenarios.seed` is the master seed.
- The i-th sample uses sub-seed `seed + i`, recreated inside the worker process.
- Therefore `n_jobs=1` and `n_jobs=-1` produce **byte-identical output**.

This property is enforced by `tests/integration/test_batch_parallel_determinism.py` — two independent runs are HDF5 byte-identical.

## Designing perturbation patterns

### Case 1 — single parameter sweep

To study only "load perturbation magnitude vs. stability", drop `line_outage`:

```yaml
scenarios:
  count: 100
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 10.0}        # large noise
```

### Case 2 — N-1 outage dataset

To sweep "is the system stable after each single line trip":

```yaml
scenarios:
  count: 46                            # case39 has 46 lines
  seed: 42
  generators:
    - kind: line_outage
      params: {n_outages: 1, prob: 1.0}   # always trip one line
```

### Case 3 — extreme combinations

Heavy load swings + N-2 outages:

```yaml
scenarios:
  count: 1000
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 15.0, clip_pct: 50.0}
    - kind: line_outage
      params: {n_outages: 2, prob: 0.8}
```

## Runtime tuning

| Goal | Setting |
|---|---|
| Faster | `n_jobs: -1`; `solver.kind: scipy_dop853` (fewer steps) |
| Lower memory | Cap `n_jobs: 4`; disable `keep_failed` |
| Live progress | `verbose: 2` |
| Acceptance too low | Loosen filters or shrink perturbation magnitude |
| Acceptance too high (need harder cases) | Increase perturbation; add stricter filters (e.g. `small_signal_stable`) |

## Incremental generation (resuming after a crash)

Batch always starts from sample 0. If you've already produced 100 and want to add another 100, see the [parameter-sweep how-to](../how-to/parameter-sweep.md).

## Estimating wall time for big runs

Trial run with 10 samples:

```yaml
scenarios:
  count: 10
  seed: 42
  generators:
    - {kind: load_perturb, params: {sigma_pct: 5.0}}
output:
  directory: ./out_test
  parallel: {n_jobs: -1}
```

Record completion time T. **Estimate for N samples**: `T_total ≈ T × (N / 10)` (with sufficient cores). Cold start + I/O dominate small batches, so the ratio improves at scale.

## Next steps

- [Critical-clearing-time analysis](03-cct.md) — same engine, but bisecting "how long can the fault last before instability".
- [Speed up batch with multiple cores](../how-to/parallel-batch.md) — joblib backends, Windows quirks.
- [Add a new scenario generator](../how-to/add-new-scenario.md) — write your own perturbation pattern.
- [Add a new sample filter](../how-to/add-new-filter.md) — custom acceptance logic.
