# Install Pylectra

_Beginner_

**Prerequisites:** [Install Python](01-install-python.md), [Install Git](02-install-git.md), [What is a virtual environment](../concepts/what-is-virtual-env.md)

## Pick your path

| Your goal | Recommended path |
|---|---|
| Just run pylectra, no source edits | **Path 1: install from PyPI** |
| Track latest code / read internals / patch bugs | **Path 2: editable source install** |
| Avoid git but want source code | **Path 3: download zip** |

All three start from a working Miniconda — see [Install Python](01-install-python.md).

## Path 1 — install from PyPI

```bash
# 1. Create a clean environment
conda create -n pylectra-env python=3.11 -y
conda activate pylectra-env

# 2. Install pylectra (core)
pip install pylectra

# 3. Recommended: also install the pandapower backend
pip install pylectra[pandapower]
```

Verify:

```bash
python -c "import pylectra; print(pylectra.__version__)"
```

You should see a version number, e.g. `0.1.0`.

## Path 2 — editable source install

For users who want to read/modify source or contribute PRs.

```bash
# 1. Clone
git clone https://github.com/pylectra/pylectra.git
cd pylectra

# 2. Create environment
conda create -n pylectra-dev python=3.11 -y
conda activate pylectra-dev

# 3. Install editable
pip install -e .

# 4. Optional extras
pip install -e ".[dev]"          # pytest / ruff
pip install -e ".[docs]"         # mkdocs documentation build
pip install -e ".[torch]"        # torchdiffeq GPU solvers
pip install -e ".[all]"          # everything (~2 GB)
```

`-e .` (editable) magic: edits to source files take effect on the next `import pylectra` — no reinstall needed.

## Path 3 — download zip (no git)

1. Open the [pylectra Releases page](https://github.com/pylectra/pylectra/releases).
2. Pick the latest version, click **Source code (zip)**.
3. Unzip to a path **without spaces or non-ASCII characters**.
4. From a terminal inside that directory:

```bash
cd path-to-unzipped/pylectra-0.1.0
conda create -n pylectra-env python=3.11 -y
conda activate pylectra-env
pip install -e .
```

## Verify the install

Regardless of path, run these two:

```bash
# 1. Package imports
python -c "import pylectra; print('OK', pylectra.__version__)"

# 2. CLI works
python -m pylectra info
```

The second command lists every registered plugin — 12 categories, several dozen names. Seeing this means **pylectra is fully wired up**.

## Install extra scientific packages

Subsequent tutorials use:

```bash
# conda is more reliable for binary-heavy packages
conda install -c conda-forge numpy scipy matplotlib pandas h5py pyarrow

# pandapower backend (already covered in Path 1; install separately for Path 2/3)
conda install -c conda-forge pandapower

# Jupyter Notebook (optional but very handy for interactive analysis)
conda install -c conda-forge jupyterlab
```

## Smoke test

```bash
python -m pylectra run examples/single_case39.yaml
```

> Path 1 users may not have an `examples/` directory locally. Either switch to Path 2/3 to grab the source, or pull the YAMLs individually from the [GitHub examples folder](https://github.com/pylectra/pylectra/tree/main/examples).

Expected: ~30 s of log output ending with:

```
[single] simulation completed in X.XX seconds
```

That's your first successful simulation. Detailed walk-through in [Your first simulation](04-first-simulation.md).

## FAQ

### Q: `conda create` raises an SSL error

Usually a mirror or proxy issue. Try:

```bash
conda config --remove-key channels         # Reset to defaults
conda create -n pylectra-env python=3.11
```

### Q: `pip install pylectra` hangs at "Building wheel for h5py..."

`h5py` needs the HDF5 C library. **Install via conda first**:

```bash
conda install -c conda-forge h5py
pip install pylectra
```

### Q: `pandapower` won't install

```bash
conda install -c conda-forge pandapower
```

The conda channel almost always works.

### Q: How do I upgrade pylectra?

```bash
# Path 1 (PyPI)
pip install --upgrade pylectra

# Path 2 (source)
cd pylectra
git pull
pip install -e .    # only needed if dependencies changed
```

### Q: How do I uninstall completely?

```bash
conda activate pylectra-env
pip uninstall pylectra

conda deactivate
conda env remove -n pylectra-env   # remove the whole environment
```

## Next steps

- [Your first simulation](04-first-simulation.md) — run a case39 fault simulation and understand every YAML field.
