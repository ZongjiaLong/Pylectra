# GPU acceleration with torch

_Advanced_

**Prerequisites:** [Single deterministic simulation](01-single-run.md)

pylectra's ODE engine has an optional PyTorch backend with `torchdiffeq` solvers — large speed-ups on machines with NVIDIA GPUs. This page covers when to switch, how, and how to manage memory.

## When is torch worth it?

| Scenario | scipy | torch CPU | torch CUDA |
|---|---|---|---|
| case39 single sim | ~5 s | ~3 s | ~1 s |
| case118 single sim | ~30 s | ~20 s | ~3 s |
| case2000+ single sim | ~10 min | ~6 min | ~30 s |
| 1000-sample batch (case39) | ~1 h | ~40 min | ~10 min (and lower power) |

> Numbers from measured case39 + extrapolation. Bigger cases and bigger batches benefit most from CUDA.

If your work is just a handful of case39 runs, **stay on scipy** — torch's CUDA-context startup (~1 s) eats the win.

## Install torch

CPU only:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install torchdiffeq
```

NVIDIA GPU + CUDA 12.x (typical):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install torchdiffeq
```

> **Don't know your CUDA version?** Run `nvidia-smi`; the top-right shows "CUDA Version". 12.1 → cu121, 11.8 → cu118.

Verify:

```python
import torch
print("torch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("device count:",  torch.cuda.device_count())
```

If `CUDA available: False` despite having a GPU, pip installed the CPU build. Reinstall via the CUDA channel:

```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## YAML solver swap

```yaml
solver:
  kind: torch_dopri5            # or torch_dopri8 / torch_rk4 / torch_euler
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
    chunk_seconds: 0.5          # OOM relief (see below)
    torch_dtype: float64        # cuda default float64; mps requires float32
    device: auto                # auto → cuda → mps → cpu
```

Four torch solvers:

| Name | Method | Adaptive | When |
|---|---|---|---|
| `torch_dopri5` | Dormand-Prince 5(4) | yes | **Default**; matches scipy_rk45 in accuracy |
| `torch_dopri8` | Dormand-Prince 8(7) | yes | High accuracy; counterpart of scipy_dop853 |
| `torch_rk4` | classical RK4 | no | Fixed step; simplest |
| `torch_euler` | Euler | no | Rarely useful; reference only |

## Automatic device selection

```yaml
solver:
  options:
    device: auto       # default
```

`auto` tries:

```
1. CUDA available → cuda (full GPU speed)
2. Apple M1/M2/M3 + float32 → mps
3. Otherwise → cpu
```

Force a specific device:

```yaml
device: cuda           # error if no GPU
device: cpu            # CPU even when GPU is present
```

## Out-of-memory: chunking

`torchdiffeq.odeint` can OOM on long sims because it retains internal RK k1..k6 buffers across the whole call (size ∝ T·n).
**Fix:** `chunk_seconds` slices each leg into windows; `tensor.detach()` between windows.

```yaml
solver:
  kind: torch_dopri5
  options:
    chunk_seconds: 0.5         # one window per 0.5 s
```

| `chunk_seconds` | Memory | Speed |
|---|---|---|
| `null` (default) | O(leg × state dim) | fastest |
| `1.0` | half | ~5 % slower |
| `0.5` | quarter | ~10 % slower |
| `0.1` | 1/40 | ~30 % slower |

**OOM rescue checklist**:

1. Try `chunk_seconds: 0.5`.
2. Still OOM → `0.2`.
3. Still OOM → also lower `dense_n` (output points per leg) and `rtol`.
4. Still OOM → fall back to CPU (`device: cpu`).

Mathematical equivalence is enforced by `tests/integration/test_torch_backend.py::test_chunking_is_numerically_equivalent`: chunked vs. non-chunked agree at `rtol=1e-4`.

## Choosing dtype

```yaml
solver:
  options:
    torch_dtype: float64     # default, high accuracy
    # torch_dtype: float32   # 1.5–2× faster, half the memory, ~5 fewer digits
```

Rotor-angle dynamics range over 10⁻³–10⁰ — float32 is usually enough. **Use float64 for numerical comparisons or paper-grade results.**

> Apple MPS supports float32 only. With `device: auto`, pylectra raises a clear error and asks you to switch to cpu or change the dtype.

## Running batches on GPU

batch + torch + joblib — but **don't** spawn `n_jobs = number-of-GPUs × many`: each worker creates a CUDA context (~1 GB VRAM) and you'll OOM fast.

```yaml
output:
  parallel:
    n_jobs: 1                  # one worker; GPU saturates already
    backend: loky
```

For multi-GPU machines:

```python
# Pick a GPU per worker; needs custom dispatching
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # or "1"
```

More elaborate multi-GPU schemes are out of pylectra's core scope — wrap your own driver script.

## Verify the GPU is actually working

```bash
# In a separate terminal during the run
nvidia-smi
```

Look for a `python` process, VRAM usage, and GPU-Util > 0 % — that's the real thing.

Or in code:

```python
import torch
print("device used:", out.result.metadata.get("torch_device"))
```

## scipy vs. torch numerical differences

They are **not** bit-identical, because:

- Different algorithms (dop853 is 8th-order; dopri5 is 5th-order).
- Different initial step controllers.
- Different float64 accumulation orders.

Both are valid solutions of the same ODE. pylectra enforces `< 1 % L2 error`:

```
torch_dopri5 vs scipy_dop853 on case39 + bus 16 fault:
  Angles  L2 = 0.3%
  Speeds  L2 = 0.1%
  Voltages L2 = 3 % (larger near fault discontinuities)
```

For paper-grade results, scipy's output is the safer reference; switch to torch when scaling up datasets.

## FAQ

### Q: torch is installed and I have a GPU, but pylectra reports `device=cpu`

Possible causes:

- `pip install torch` defaulted to the CPU build. `pip uninstall torch` and reinstall via the CUDA channel.
- conda's torch doesn't match the system CUDA toolkit. (conda's torch ships its own CUDA runtime; pip's requires system CUDA.)
- You set `device: cpu` explicitly somewhere.

### Q: torch starts slowly

The very first `import torch` on a GPU machine pays the CUDA-context cost (~1–2 s). Subsequent calls are fast. If every run is slow, the GPU may be in power-save under `nvidia-persistenced` — try `nvidia-smi -pm 1`.

### Q: `torchdiffeq` won't install

```bash
pip install torchdiffeq
```

### Q: torch on CPU is faster than scipy?

Yes. `torchdiffeq` uses PyTorch's BLAS backend (OpenBLAS / MKL) and a fully-vectorised tensor RHS — both faster than scipy's Python interpretation overhead. **You get the win even without a GPU.**

## Next steps

- [Tune memory for long simulations](../how-to/tune-memory.md) — beyond chunk_seconds.
- [pylectra.run.run() API](../reference/api/run.md) — full solver-option reference.
