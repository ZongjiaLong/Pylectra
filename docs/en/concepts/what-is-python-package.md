# What is a Python package?

_Beginner_

> Written for power-systems engineers coming from MATLAB / C / Fortran. If you already know `import numpy as np`, skip to [Next steps](#next-steps).

## One-line definition

A **package** is a **pre-written collection of Python code, hosted online, installable with one command**.

The "toolbox" concept that power-systems engineers use every day is called a *package* in Python:

| MATLAB concept | Python equivalent |
|---|---|
| Toolbox (e.g. Power System Toolbox) | Package (e.g. `pylectra`, `pandapower`) |
| `addpath('mytoolbox/')` | `import mytoolbox` (after installing) |
| Function `myfunc.m` | Function `myfunc()` in a `.py` file |
| `which myfunc` | `print(myfunc.__module__)` |

## How to "install" a package

Python's official package manager is **pip**. Installing one looks like:

```bash
pip install pylectra
```

This single command does three things:

1. Downloads the package from [PyPI](https://pypi.org) (Python's official package index, similar to MATLAB's File Exchange).
2. Resolves declared dependencies (e.g. `pylectra` depends on `numpy`, `scipy`, `pandas`) and recursively installs them.
3. Drops the package into your current Python's **site-packages** directory so any script that runs `import pylectra` finds it.

## What is `import`?

```python
import numpy as np              # Load all of numpy, alias it as np
from pylectra.run import run    # Pull just the `run` function out of pylectra.run
```

Python's `import` is similar to MATLAB's `addpath` + load, but more granular:

- `import X` — load the whole package; access members via `X.foo()`.
- `from X import foo` — pull just `foo`; use it directly as `foo()`.
- `import X as Y` — assign a shorter alias (community convention: `numpy → np`, `pandas → pd`).

If you see this error:

```
ModuleNotFoundError: No module named 'pylectra'
```

it means "the package I asked for is not installed in the current Python environment". 99 % of the time the cause is:

- You haven't run `pip install pylectra` yet, or
- `pip` installed into a *different* Python (each Python version has its own site-packages).

The second case is exactly what the next page,
[What is a virtual environment](what-is-virtual-env.md), explains.

## What does a package look like on disk?

Open the install location of `pylectra` and you'll see:

```
pylectra/
├── __init__.py          # Entry point; import pylectra runs this file
├── run.py               # A submodule (defines the run() function)
├── registry.py
├── models/
│   ├── __init__.py      # Sub-packages need an __init__.py too
│   └── generators/
│       ├── __init__.py
│       └── two_axis.py  # A generator dynamic model
└── ...
```

**Every `__init__.py` tells Python "this folder is a (sub-)package and is importable."**
It typically also runs some startup logic:

```python
# pylectra/__init__.py
from . import _legacy           # Initialise vendored legacy first
from . import registry          # Then load the plugin registry
from .run import run            # Expose run at the top level
__version__ = "0.1.0"
```

So `from pylectra import run` works directly.

## Standard library vs third-party

Python ships with a **standard library** that needs no `pip install`:

```python
import os         # filesystem
import math       # basic math
import json       # JSON I/O
import pathlib    # paths (the modern, recommended API)
```

Anything else is **third-party**: `numpy`, `scipy`, `pandas`, `matplotlib`, `pylectra` are all third-party.

## FAQ

### Q: Are Python packages much larger than MATLAB toolboxes?

No. Most packages are a few MB to a few tens of MB. The big exceptions are GPU-accelerated libraries like `torch` (~200 MB CPU, ~2 GB CUDA). The first install of `pylectra` typically takes 1–3 minutes because pip pulls in every dependency in one go.

### Q: How do I see what I have installed?

```bash
pip list                        # All packages in the current Python environment
pip show pylectra               # Version, install path, declared dependencies
```

### Q: How do I uninstall?

```bash
pip uninstall pylectra
```

## Next steps

- [What is a virtual environment](what-is-virtual-env.md) — don't pile every package into your system Python; isolate per project.
