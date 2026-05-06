# Speed up batch with multiple cores

_Intermediate_

**Prerequisites:** [Batch dataset generation](../tutorials/02-batch-generation.md)

## One YAML block

```yaml
output:
  parallel:
    n_jobs: -1                # -1 = all CPU cores
    backend: loky             # loky | multiprocessing | threading
    batch_size: 4             # tasks per dispatch (loky default = auto)
```

## Choosing `n_jobs`

| Value | Meaning |
|---|---|
| `1` | Serial (development / debugging) |
| `-1` | Every logical CPU |
| `auto` | pylectra heuristic: `min(cpu_count - 1, 16)` |
| `4` | Explicit 4 workers |

**Rules of thumb**:

- ≤ 16 cores: `-1` is usually fastest.
- > 16 cores: `auto` (capped at 16) avoids diminishing returns.
- 4 / 8 GB machines: each worker takes ~500 MB; 16 workers will OOM. **Cap at `n_jobs: 4` or `8`.**

```python
from pylectra.hardware import recommend_n_jobs, summary
print(summary())              # full hardware summary
print(recommend_n_jobs())     # pylectra's recommendation
```

## Choosing the backend

### `loky` (recommended default)

joblib's process pool. **Works on Windows / macOS / Linux**. Each worker is its own Python process — bypasses the GIL and is fastest for CPU-bound tasks (pylectra is one).

### `multiprocessing`

Python's stdlib multiprocessing. Similar in spirit but with more fork-related quirks. **Avoid** — `loky` patches a long list of fork issues on Windows / macOS.

### `threading`

Thread pool. Limited by the GIL — **no speed-up for pylectra's mostly-Python ODE driver**, even at `n_jobs=8`.
**Exception**: if your code calls **GIL-releasing C extensions** (numpy BLAS on big matrices, scipy solvers, torch), threading does parallelise. Pylectra's main loop is mostly Python, so **don't use threading**.

## The Windows non-ASCII username pitfall

A Windows username with non-ASCII chars (e.g. `龙宗加`) + joblib `loky` = `UnicodeEncodeError`.
`multiprocessing.resource_tracker` encodes IPC messages as ASCII; paths like `C:\Users\龙宗加\AppData\Local\Temp\...` blow up.

**Fix**: redirect `JOBLIB_TEMP_FOLDER` to an ASCII-only path:

```bash
# Windows cmd
set JOBLIB_TEMP_FOLDER=D:\joblib_tmp
python -m pylectra run examples/batch_case39.yaml

# Windows PowerShell
$env:JOBLIB_TEMP_FOLDER = "D:\joblib_tmp"

# Linux / macOS (rarely an issue here)
export JOBLIB_TEMP_FOLDER=/tmp/joblib_tmp
```

Or in Python:

```python
import os
os.environ["JOBLIB_TEMP_FOLDER"] = r"D:\joblib_tmp"
from pylectra.run import run
run("examples/batch_case39.yaml")
```

## Tuning `batch_size`

`batch_size` controls how many tasks are dispatched to each worker per chunk.

- `auto` / default: joblib adapts (usually fine).
- Too small (`1`): scheduling overhead, idle workers.
- Too large (`100`): unbalanced load (one slow worker drags the rest).

For very large batches (10 000+), explicit `batch_size: 8` or `16` is often 5–10 % faster than auto.

## Memory vs. n_jobs

Per worker:

- A separate Python interpreter (~50 MB).
- Copy of the numpy case data (~1 MB).
- joblib internal buffers (~10 MB).
- Simulation state (case-size dependent; case39 ~30 MB).

**case39, n_jobs=8 → ~250 MB total.**
**case2000+, n_jobs=8 → easily exceeds 8 GB.**

OOM rescue:

```yaml
output:
  parallel:
    n_jobs: 4         # halve it
    backend: loky
    batch_size: 1     # less in-flight data
```

## Verify the speed-up

5-sample sanity check:

```bash
# Serial
time python -m pylectra run examples/batch_case39.yaml \
  -O 'output={"parallel": {"n_jobs": 1}}'

# Parallel
time python -m pylectra run examples/batch_case39.yaml \
  -O 'output={"parallel": {"n_jobs": -1}}'
```

8-core typical: serial ~50 s, parallel ~10 s — about 5× (ideal 8× minus joblib start-up + I/O overhead).

## On a shared cluster

In academic / corporate HPC, each worker rarely owns a physical core — others are also competing.

- **SLURM / PBS**: after `--cpus-per-task=8`, `n_jobs=-1` sees 8 (not the whole node).
- Cluster forbids `fork`? Switch to `backend: threading` — gives up parallel speed-up but avoids being killed by the scheduler.
- `dask` is the better fit for true distributed clusters; pylectra has no built-in dask support, but `SingleRunner` is picklable so wrapping it externally is straightforward.

## Long-running setups

```python
import joblib
joblib.parallel_config(backend="loky",
                       n_jobs=8,
                       temp_folder="/scratch/joblib")
# All later batch calls inherit this config
```

## FAQ

### Q: Why is 4-core `n_jobs=4` only 30 % faster than `n_jobs=2`?

Each individual sim already eats ~60 % CPU (numpy / scipy BLAS multi-threading). Disable BLAS internal threading for more linear scaling:

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

### Q: Stuck on "Joblib starting"

First-time loky workers import pylectra in full (every plugin + numpy / scipy) — 10–30 s is normal. **Only the first start is slow**; subsequent tasks reuse the same workers.

If still stuck after 5 minutes, an importing plugin probably raised. Add `-O 'verbose=2'` for details.

### Q: Distribute across multiple machines?

joblib is single-host. For multi-machine:

- **dask.distributed**: submit `SingleRunner` tasks via `client.submit`.
- **Ray**: similar.
- **SLURM array jobs**: each array task runs an independent batch; merge metadata afterwards.

## Next steps

- [Tune memory for long simulations](tune-memory.md) — chunk_seconds + BLAS sharing, etc.
- [Batch tutorial](../tutorials/02-batch-generation.md) — config refresher.
