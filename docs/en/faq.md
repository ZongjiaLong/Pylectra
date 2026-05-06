# Frequently asked questions

_Reference_

Grouped by topic. Can't find your question? File one at [GitHub Issues](https://github.com/ZongjiaLong/Pylectra/issues).

## Installation

### Q: `pip install pylectra` hangs / times out

PyPI is slow from some regions. Switch to a mirror:

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip install pylectra
```

See [Install Python — mirror configuration](getting-started/01-install-python.md#mirrors).

### Q: "Building wheel for h5py" stalls

`h5py` needs the HDF5 C library. **Use conda**:

```bash
conda install -c conda-forge h5py
pip install pylectra
```

### Q: `pandapower` won't install

```bash
conda install -c conda-forge pandapower
```

If that still fails, ensure your Python is ≥ 3.10.

### Q: Where should I install on Windows?

**Prefer `D:\Miniconda3` or similar** — avoid `C:\Program Files`. Spaces in the path break a few Python packages.

### Q: Clean uninstall?

```bash
conda activate pylectra-env
pip uninstall pylectra
conda deactivate
conda env remove -n pylectra-env       # remove the whole environment
```

## First-time runs

### Q: `ModuleNotFoundError: No module named 'pylectra'`

99 % of the time: pylectra is installed in a different Python.

```bash
which python                           # macOS / Linux
where python                           # Windows
pip -V                                 # where pip installs to
```

If the output mentions `pylectra-env`, the env is correct. Otherwise `conda activate pylectra-env`.

### Q: `KeyError: 'kind' = 'xxx'`

The plugin name in YAML isn't registered. Two possibilities:

1. Typo → `python -m pylectra info` lists every legal name.
2. You wrote a custom plugin but it wasn't loaded → confirm it's under `pylectra/<category>/` and the filename doesn't start with `_`.

### Q: `power flow did not converge`

Try, in order:

- Switch solver: `power_flow: {kind: pandapower}`.
- Loosen tolerance: `tolerance_mva: 1.0e-6`.
- Sanity-check the case (extreme loads / disconnected topology).

### Q: Rotor angles shoot to infinity

The fault is too severe / the system is unstable. Try:

- Shorten `fault.params.duration`.
- Switch to `solver: {kind: scipy_dop853, options: {rtol: 1e-8}}` to rule out numerical instability.
- Confirm `out.result.pf_success` is True.

### Q: No plot window appears

- Is `plot: true` in the YAML?
- Did you pass `--no-plot`?
- macOS may need `pip install pyqt5`, or just skip the window:
  ```bash
  python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf
  ```

## Batch mode

### Q: `UnicodeEncodeError: 'ascii' codec can't encode characters` (Windows)

Known issue: non-ASCII Windows usernames (e.g. `龙宗加`) + joblib `loky` backend. Set the env var:

```bash
# Windows cmd
set JOBLIB_TEMP_FOLDER=D:\joblib_tmp
python -m pylectra run examples/batch_case39.yaml

# PowerShell
$env:JOBLIB_TEMP_FOLDER = "D:\joblib_tmp"
```

See [parallel batch how-to](how-to/parallel-batch.md).

### Q: Acceptance rate is too low

The perturbations are too aggressive or the filters too strict.

- Reduce `scenarios.generators[*].params.sigma_pct`.
- Loosen `voltage_range.vmin / vmax`.
- Raise `angle_stability.max_dev_deg`.

### Q: Batch out-of-memory

In order:

1. `n_jobs` too high → halve it (`n_jobs: 4`, not `-1`).
2. `keep_failed: false` set?
3. Case too big? See [tune memory how-to](how-to/tune-memory.md).
4. Last resort: chunked runs (100 samples at a time).

### Q: Batch finished but metadata.parquet is empty

- No samples passed the filters → with `keep_failed: false`, nothing is written.
- Workaround: enable `keep_failed: true` to at least see all samples and their rejection reasons.

## Performance

### Q: pylectra is slower than MATLAB

Probably the wrong solver. `modified_euler` is kept for byte-comparable MATLAB output — **`scipy_dop853` is the production recommendation**:

```yaml
solver:
  kind: scipy_dop853
  options: {rtol: 1.0e-6}
```

Half the steps and half the wall time, typically.

### Q: Torch on CPU is slower than scipy?

torch's CUDA-context startup + first-time imports are heavy. **torch wins on GPU** or **across many simulations** (worker reuse).

For one-off case39 runs, stick with scipy. case500+ or batches of 1000+ start to favour torch.

### Q: How do I confirm the GPU is actually being used?

```bash
nvidia-smi                             # GPU utilisation
```

Or in Python:

```python
import torch
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
```

### Q: `n_jobs=8` is only 30 % faster than `n_jobs=2`

OpenBLAS / MKL multi-thread inside each worker, causing oversubscription. Pin to a single thread:

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

## CCT mode

### Q: `CCT outside bracket [low, high]; widen the bracket`

The bracket is wrong:

- `low` must be stable (shrink it).
- `high` must be unstable (raise it).

Try `low: 0.001, high: 0.50`.

### Q: CCT converged but disagrees with the literature

Reference values usually pin specific dynamic parameters and a specific solver. pylectra's case39 defaults to `case39dyn` + `modified_euler`, which may differ from your reference.

- Match the solver and tolerance.
- Match the stability criterion (180° / 90°).
- Match the fault type (bolted vs impedance).

## Small-signal

### Q: `stability_margin > 0` but the simulation looks stable

An unstable equilibrium ≠ unstable large-disturbance response. Two reasons:

1. The `case_dyn` parameters are off (small-signal exposed a bug).
2. There's a slowly diverging mode that a 5-10 s sim doesn't reveal.

Run `kind: modal` to find the worst-damped mode's frequency, then run a 30 s sim to verify.

### Q: All damping ratios are NaN

Every eigenvalue is at zero (no oscillation) — the case is degenerate (no load, no fault). Pick a case that actually has dynamics.

## Visualization

### Q: CJK labels show as boxes

matplotlib's default font lacks CJK glyphs. First cell of a Notebook:

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

### Q: PDF export rasterised the fonts

`set_nature_style()` defaults `svg.fonttype = "none"` so PDFs embed live fonts. If output is rasterised, verify:

- `matplotlib >= 3.7`.
- You're using `fig.savefig("x.pdf")` (not `plt.savefig`, which loses figure context).

### Q: CLI `pylectra plot` says `unknown plot kind`

`python -m pylectra info --category plot` lists the legal names. Common typo: `rotor-angles` should be `rotor_angles` (underscore).

## Jupyter

### Q: `import pylectra` fails inside a Notebook

Jupyter is using the wrong Python. Register the env as a kernel:

```bash
conda activate pylectra-env
pip install ipykernel
python -m ipykernel install --user --name pylectra-env --display-name "Python (pylectra-env)"
```

Refresh Jupyter and pick `Python (pylectra-env)` for new notebooks.

## Advanced / development

### Q: How do I contribute?

See [CONTRIBUTING.md](https://github.com/ZongjiaLong/Pylectra/blob/main/CONTRIBUTING.md). In short: fork → write one new plugin file → add a test → PR.

### Q: Will the API break compatibility?

The 0.1.x line keeps the YAML schema and `pylectra.run.run()` signature stable. 0.2.0 plans to **remove `pylectra/_legacy/`** — but only users importing legacy internal modules will notice; the public API is unchanged.

### Q: Offline install?

From a machine with internet:

```bash
pip download pylectra -d ./pylectra-pkgs
```

Tar the directory and copy it to the target host:

```bash
pip install --no-index --find-links ./pylectra-pkgs pylectra
```

## Next steps

- [Tune memory](how-to/tune-memory.md) — memory-related issues.
- [Parallel batch](how-to/parallel-batch.md) — parallel performance.
- [GitHub Issues](https://github.com/ZongjiaLong/Pylectra/issues) — file a new question.
