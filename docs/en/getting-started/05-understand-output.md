# Understanding the output files

_Beginner_

**Prerequisites:** [Your first simulation](04-first-simulation.md)

What pylectra produces depends on the run mode.

## Single mode — one simulation

The default `python -m pylectra run examples/single_case39.yaml` **writes nothing to disk** — results stay in memory and are discarded after plotting.

To persist them, two options:

### Option 1 — call from Python and save yourself

```python
from pylectra.run import run
import h5py

out = run("examples/single_case39.yaml", plot=False)
res = out.result

# Save to HDF5
with h5py.File("my_run.h5", "w") as f:
    f.create_dataset("Time",   data=res.Time)
    f.create_dataset("Angles", data=res.Angles)
    f.create_dataset("Speeds", data=res.Speeds)
    # Split complex voltages into real / imag
    f.create_dataset("Voltages_real", data=res.Voltages.real)
    f.create_dataset("Voltages_imag", data=res.Voltages.imag)

# Or to npz (numpy's simple format)
import numpy as np
np.savez("my_run.npz", Time=res.Time, Angles=res.Angles, Voltages=res.Voltages)
```

### Option 2 — go through the plotting CLI

```bash
python -m pylectra plot examples/single_case39.yaml --type rotor_angles --output rotor.pdf
python -m pylectra plot examples/single_case39.yaml --type overview --output overview.pdf --format pdf,png
```

The CLI runs one simulation and emits the plot — no intermediate files needed.

## SimulationResult fields

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

print(res.Time.shape)        # (N,)         all sample times [s]
print(res.Voltages.shape)    # (N, n_bus)   complex bus voltage at each time
print(res.Angles.shape)      # (N, n_gen)   rotor angle [deg]
print(res.Speeds.shape)      # (N, n_gen)   rotor speed [p.u.]
print(res.Eq_trs.shape)      # (N, n_gen)   d/q-axis transient EMFs
print(res.Ed_trs.shape)
print(res.Efds.shape)        # (N, n_gen)   field voltage (Efd)
print(res.Tes.shape)         # (N, n_gen)   electrical torque
print(res.TM.shape)          # (N, n_gen)   mechanical torque
print(res.Stepsize.shape)    # (N,)         per-step size (meaningful for adaptive solvers)

# Scalar conveniences
print(res.simulation_time)            # wall time [s]
print(res.pf_success)                 # power-flow converged?
print(res.n_steps)                    # total step count
print(res.max_angle_deviation_deg)    # max deviation from COI [deg]
```

## Batch mode — many simulations

With `mode: batch` and an `output:` block, pylectra writes:

```
output_directory/
├── metadata.parquet                   # one row per sample (all metadata)
├── sample_000000.h5                   # time-series for sample 0
├── sample_000001.h5
├── sample_000002.h5
└── ...
```

YAML excerpt:

```yaml
mode: batch
case_pf: case39
case_dyn: case39dyn
scenarios:
  count: 100
  seed: 42
  generators:
    - {kind: load_perturb, params: {sigma_pct: 5.0}}
output:
  directory: ./out_batch
  format: hdf5            # hdf5 | npz
  metadata: parquet       # parquet | csv
```

### Open an HDF5 time-series file

```python
import h5py

with h5py.File("out_batch/sample_000000.h5", "r") as f:
    print(list(f.keys()))                # available datasets
    Time   = f["Time"][:]                # numpy array
    Angles = f["Angles"][:]
    Speeds = f["Speeds"][:]

print(Time.shape, Angles.shape)
```

> HDF5 is the de-facto binary format in scientific computing — 10–100× faster than CSV and handles complex / multi-dimensional arrays cleanly. h5py is the standard Python binding.

For a GUI: [HDFView](https://www.hdfgroup.org/downloads/hdfview/) (free) opens `.h5` files like a file manager.

### Open the Parquet metadata

```python
import pandas as pd

meta = pd.read_parquet("out_batch/metadata.parquet")
print(meta.columns.tolist())
# ['sample_id', 'passed', 'rejected_by', 'rejected_reason',
#  'simulation_time', 'pf_success', 'n_steps', 'n_bus', 'n_gen',
#  'filter_voltage_range_metric', 'filter_angle_stability_metric',
#  'meta:load_perturb_sigma_pct', 'meta:line_outage_branches',
#  'sample_path']

# Samples that passed every filter
ok = meta[meta["passed"]]
print(f"{len(ok)} / {len(meta)} accepted")

# Top 10 by angle deviation
top = meta.nlargest(10, "filter_angle_stability_metric")
print(top[["sample_id", "filter_angle_stability_metric"]])
```

> Parquet is a columnar format — typically 10× smaller than CSV with much faster filtered reads. Built into pandas 1.0+.

### Or let pylectra plot the statistics

```bash
# Acceptance / rejection bar
python -m pylectra plot ./out_batch --type acceptance --output acceptance.pdf

# Histogram of one metric
python -m pylectra plot ./out_batch --type histogram --output hist.pdf \
    -O column='"filter_angle_stability_metric"'

# Violin plot
python -m pylectra plot ./out_batch --type violin --output violin.pdf \
    -O column='"filter_voltage_range_metric"'
```

## CCT mode — critical clearing time

```bash
python -m pylectra run examples/cct_case39.yaml
```

CCT mode prints results without writing files:

```
[cct] iter  0: duration=0.1500 → unstable
[cct] iter  1: duration=0.0750 → stable
...
[cct] CCT ≈ 0.1270 s (bracket [0.1270, 0.1300], 7 iters, converged=True)
```

Programmatic access:

```python
from pylectra.run import run
out = run("examples/cct_case39.yaml")
print(out.result.cct, out.result.iterations, out.result.converged)
```

## Capture logs to a file

Redirect stdout/stderr:

```bash
python -m pylectra run examples/single_case39.yaml > run.log 2>&1
```

`> run.log` redirects standard output; `2>&1` merges errors in too.

## Next steps

- [Single deterministic simulation (tutorial)](../tutorials/01-single-run.md) — every adjustable field of single mode in detail.
- [Batch dataset generation (tutorial)](../tutorials/02-batch-generation.md) — build research-grade datasets.
