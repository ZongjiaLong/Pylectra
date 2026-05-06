# What is a virtual environment?

_Beginner_

**Prerequisites:** [What is a Python package](what-is-python-package.md)

## Why you need one

Suppose you have one Python on your machine and every `pip install` lands in it. Eventually:

- Project A needs `pandas==1.5`.
- Project B needs `pandas==2.2` (the API changed; 1.5 code won't run).
- A system utility script needs `pandas==1.3`.

One Python cannot hold all three at once — this is **dependency conflict**.
The fix: **give each project its own isolated "virtual environment"**, each with its own package list.

> Analogy: a per-project MATLAB working directory + `userpath` that pins different toolbox versions.

## Two mainstream options

### Option A: conda (recommended for power-systems engineers)

[Anaconda](https://www.anaconda.com/download) / [Miniconda](https://docs.conda.io/projects/miniconda/) is the most popular distribution in scientific computing. **Bundles Python + virtualenv management + a compiler toolchain.** One install is enough.

We recommend **Miniconda** (lightweight, ~100 MB):

```bash
# Create a fresh environment named pylectra-env with Python 3.11
conda create -n pylectra-env python=3.11

# Activate it
conda activate pylectra-env

# Install pylectra inside the environment (this pip only touches it)
pip install pylectra

# Leave when done
conda deactivate
```

After activation the shell prompt becomes `(pylectra-env) C:\Users\...>`, marking you as inside an isolated environment — every `pip` / `python` invocation now affects only this one.

### Option B: venv (built into Python, no extra install)

```bash
# Create an environment called .venv in the current directory
python -m venv .venv

# Activate
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux

# Install packages
pip install pylectra

# Exit
deactivate
```

`venv` produces a plain folder (the `.venv` name is convention; the leading dot makes it hidden). To delete the environment, just delete the folder.

## Which one when?

| Situation | Recommendation |
|---|---|
| Multiple Python versions (3.10 / 3.11 / 3.12) | conda |
| Installing `pandapower`, `scipy`, anything with C/Fortran extensions but no compiler on hand | conda |
| Corporate machine without admin rights | conda (Miniconda user install) |
| Python already installed; just want lightweight isolation | venv |

The rest of this documentation uses conda in examples because it's the most common in power-systems circles.

## A common mistake

**Running `pip install` without activating an environment** — the package lands in the "system Python" or the previously-activated env, and the next time you activate the right one `import` raises `ModuleNotFoundError`.

How to verify:

```bash
# Where is the current python?
where python                     # Windows
which python                     # macOS / Linux

# Where will pip install to?
pip -V
```

If the output contains your env's name (e.g. `pylectra-env`), you're correct.

## FAQ

### Q: Will environments fill up my disk?

Each is **a few hundred MB** to 1 GB (with numpy/scipy/matplotlib). One or two are fine; for dozens, share a "general science env" and only spin up dedicated ones when conflicts force it.

### Q: My environment broke. How do I fix it?

Don't fix it — `conda env remove -n pylectra-env` (or `rm -rf .venv`) and recreate. Rebuilding is faster than debugging.

### Q: Mixing conda and pip — safe?

Generally yes, but a rule of thumb: **install binary-heavy science packages with conda** (`numpy`, `scipy`, `pandapower` are all on conda), **install pure-Python packages with pip** (`pylectra`). Run `conda install ...` first, then `pip install ...`.

### Q: Can I use Jupyter Notebook with this?

Yes. After `conda activate pylectra-env`, run `pip install jupyterlab`, then `jupyter lab`. Notebooks pick up whichever Python is currently active.

## Next steps

- [Install Pylectra](../getting-started/03-install-pylectra.md) — apply what you just learned and install pylectra inside an isolated environment.
