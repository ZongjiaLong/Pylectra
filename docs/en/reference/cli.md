# Command-line reference

_Reference_

```
python -m pylectra <command> [args] [options]
```

Or, if `pip install pylectra` registered the entry-point script:

```
pylectra <command> [args] [options]
```

## Commands at a glance

| Command | Purpose |
|---|---|
| `run` | Execute a YAML config (single / batch / cct) |
| `info` | List registered plugins + hardware info |
| `plot` | Render a figure (runs a sim or reads an existing `.h5`) |

## `run`

```
python -m pylectra run <config.yaml> [-O KEY=VALUE]... [--verbose N] [--no-plot]
```

**Arguments**

| Argument | Meaning |
|---|---|
| `<config.yaml>` | Required — path to YAML config |
| `-O KEY=VALUE` | Override a YAML field (value is JSON); repeatable |
| `--verbose 0/1/2` | Override the YAML's `verbose` |
| `--no-plot` | Force `plot=false` |

**Examples**

```bash
# Basic
python -m pylectra run examples/single_case39.yaml

# Override single fields
python -m pylectra run examples/single_case39.yaml \
    -O 'fault.params.duration=0.10' \
    -O 'solver.kind="scipy_dop853"'

# Silent + no plot
python -m pylectra run examples/batch_case39.yaml --verbose 0 --no-plot
```

**Exit codes**

- `0`: success
- `1`: configuration error (YAML syntax / unknown plugin / missing required field)
- `2`: simulation failure (PF didn't converge / solver crashed / etc.)

## `info`

```
python -m pylectra info [--category CAT] [--hardware]
```

**Arguments**

| Argument | Meaning |
|---|---|
| `--category CAT` | List only one category (e.g. `generator`, `fault`) |
| `--hardware` | Include CPU / RAM / GPU info |

**Examples**

```bash
# All plugins
python -m pylectra info

# Just faults
python -m pylectra info --category fault
# fault: ['bus_fault', 'composite', 'line_trip', 'load_step']

# Include hardware
python -m pylectra info --hardware
```

## `plot`

```
python -m pylectra plot <source> --type TYPE --output FILE \
    [--format FORMATS] [-O KEY=VALUE]...
```

**Arguments**

| Argument | Meaning |
|---|---|
| `<source>` | YAML config (auto-run sim) / existing `.h5` / batch output dir |
| `--type TYPE` | Plugin name (see [plugins catalog](plugins-catalog.md#plots-plot)) |
| `--output FILE` | Output filename |
| `--format FORMATS` | Comma-separated, e.g. `pdf,svg,png` |
| `-O KEY=VALUE` | Extra plot-function kwargs (JSON-decoded) |

**Examples**

```bash
# Run case39 and produce a rotor-angle PDF
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf

# Multiple formats
python -m pylectra plot examples/single_case39.yaml \
    --type overview --output overview --format pdf,svg,png

# Read an existing H5 directly (no re-simulation)
python -m pylectra plot ./out_batch/sample_000003.h5 \
    --type rotor_angles --output sample3.pdf

# Topology coloured by voltage
python -m pylectra plot examples/single_case39.yaml \
    --type topology --output topo.pdf \
    -O 'color_by="vm"'

# Batch histogram
python -m pylectra plot ./out_batch \
    --type histogram --output hist.pdf \
    -O 'column="filter_angle_stability_metric"' \
    -O 'bins=40'
```

## Global options

| Option | Meaning |
|---|---|
| `-h` / `--help` | Show help |
| `--version` | Show pylectra version |

## Environment variables

| Variable | Meaning |
|---|---|
| `JOBLIB_TEMP_FOLDER` | Joblib worker temp directory (required for non-ASCII Windows usernames) |
| `OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` | Cap BLAS threads |
| `PYTORCH_CUDA_ALLOC_CONF` | torch CUDA allocator (advanced) |
| `PYLECTRA_LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` (advanced) |

## Redirecting output

```bash
# stdout to a file
python -m pylectra run examples/batch_case39.yaml > run.log

# stdout + stderr merged
python -m pylectra run examples/batch_case39.yaml > run.log 2>&1

# Background (Linux / macOS)
nohup python -m pylectra run examples/batch_case39.yaml > run.log 2>&1 &
```

## Next steps

- [YAML schema](yaml-schema.md) — every configurable field.
- [Plugins catalog](plugins-catalog.md) — every legal `kind`.
