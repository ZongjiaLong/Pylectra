# Tune memory for long simulations

_Advanced_

**Prerequisites:** [GPU acceleration tutorial](../tutorials/06-gpu-acceleration.md)

100+ second simulations, large case2000+ grids, 16-worker batches — memory pressure is normal. This page is a **graduated checklist** of optimisations.

## Tier 1 — YAML knobs (no code changes)

### Reduce stored trajectory points

```yaml
solver:
  options:
    dense_n: 50          # torch: output points per leg (default 200) → reduce to 50
```

### Trim batch outputs

```yaml
output:
  keep_failed: false     # don't keep rejected samples (default already false)
  format: hdf5           # 2-3× smaller than npz
  metadata: parquet      # 10× smaller than csv
```

## Tier 2 — torch `chunk_seconds`

If you've moved to the torch backend:

```yaml
solver:
  kind: torch_dopri5
  options:
    chunk_seconds: 0.5     # split each leg into 0.5 s windows
```

Effect (case39 + 10 s sim):

| `chunk_seconds` | Peak VRAM | Speed |
|---|---|---|
| `null` (default) | 1.0 GB | 100 % |
| `1.0` | 0.5 GB | 95 % |
| `0.5` | 0.25 GB | 90 % |
| `0.1` | 50 MB | 70 % |

Full coverage: [GPU acceleration — out-of-memory](../tutorials/06-gpu-acceleration.md#out-of-memory-chunking).

## Tier 3 — Cap batch concurrency

Each joblib worker copies the case data + solver state. More workers ⇒ more RAM.

```yaml
output:
  parallel:
    n_jobs: 4              # cut from 16 to 4-8 on big cases
    batch_size: 1          # less in-flight data
```

## Tier 4 — Disable nested BLAS threading

joblib workers × OpenBLAS multi-threading multiplies resource use. Cap with env vars:

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

Each sim is single-threaded but with many workers → CPU is fully used and **total memory is much lower**.

## Tier 5 — Chunked persistence

Very long batches (10 000+) are risky to run as one job — slice into 100-sample chunks:

```python
from pylectra.run import run
import os

base_seed = 42
chunk_size = 100
total = 10000

for offset in range(0, total, chunk_size):
    out_dir = f"./batch_chunks/chunk_{offset:06d}"
    if os.path.exists(out_dir):
        continue            # skip completed
    run("examples/batch_case39.yaml",
        scenarios={"count": chunk_size, "seed": base_seed + offset},
        output={"directory": out_dir})
```

Then merge metadata with pandas:

```python
import pandas as pd, glob
metas = pd.concat([pd.read_parquet(f) for f in glob.glob("./batch_chunks/*/metadata.parquet")])
metas["sample_id"] = metas.index    # re-number to avoid collisions
```

## Tier 6 — Drop intermediate state

If your Python script **doesn't release SimulationResult objects**, N results pile up:

```python
results = []                         # ✗ grows without bound
for cfg in configs:
    out = run(cfg, plot=False)
    results.append(out.result.max_angle_deviation_deg)   # keep only the scalar

# Or
del out                              # explicit del
import gc
gc.collect()                         # force GC
```

## Tier 7 — Use a smaller case

case2000+ is dominated by **the time-series themselves** — each sample HDF5 is hundreds of MB. If you only need scalar metrics (max angle deviation, CCT), **keep just the metadata**:

```yaml
output:
  format: hdf5
  keep_failed: false
  # Custom "metadata-only" mode requires small BatchRunner changes;
  # planned for a future release.
```

Current workaround: run full pipeline, then `rm samples/*.h5` after the fact.

## Tier 8 — Different case representation

For mass small-signal sweeps (`skip_integration: true`), you only need **case + model parameters + equilibrium** — no time-series. Per-sample metadata + eigenvalues is just a few KB.

```yaml
mode: batch
skip_integration: true
small_signal: {kind: finite_difference}
output:
  format: npz             # simpler than hdf5
  metadata: parquet
```

## Monitor memory

```bash
# Linux / macOS
htop                       # live; F10 to quit

# Windows
tasklist | findstr python

# Inline in your script
import psutil, os
proc = psutil.Process(os.getpid())
print(f"RSS = {proc.memory_info().rss / 1024**3:.2f} GB")
```

## Troubleshooting

### "MemoryError" / Killed by OS

Diagnosis order:

1. Is `n_jobs` too large? Halve it.
2. How big is the case? `pylectra info` reports total memory vs. case size.
3. Is `dense_n` too large (torch)? Reduce to 50.
4. Are you accumulating results into a Python list?
5. Last resort: chunk the run + `del` + `gc.collect()`.

### Swap usage spikes

The OS is paging to disk — performance plummets. **Immediately** lower `n_jobs`; otherwise a 10-minute batch turns into 10 hours.

## Next steps

- [GPU acceleration tutorial](../tutorials/06-gpu-acceleration.md) — full `chunk_seconds` reference.
- [Parallel batch tuning](parallel-batch.md) — n_jobs / BLAS threading.
- [FAQ](../faq.md) — memory-related troubleshooting.
