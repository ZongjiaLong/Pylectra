# Add a new plot type

_Advanced_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md), [Visualization tutorial](../tutorials/04-visualization.md)

## Goal

Write a plot plugin reachable through `render(name, data, ...)` and the `pylectra plot --type my_plot` CLI.

## The interface

```python
from pylectra.interfaces.plot import PlotPlugin

class PlotPlugin(ABC):
    name: str
    input_kind: str   # "single" | "batch" | "case" | "sweep"

    @abstractmethod
    def render(self, data, ax=None, **kwargs):
        """Plot and return a matplotlib Figure / Axes."""
```

`input_kind` declares what `data` is:

| input_kind | data type |
|---|---|
| `single` | `SimulationResult` object / `.h5` path |
| `batch`  | `metadata.parquet` path / DataFrame |
| `case`   | case name string / `NetworkCase` |
| `sweep`  | `list[SimulationResult]` or dict (user-defined) |

## Working example: polar eigenvalue plot

```python
# pylectra/plotting/eigenvalue_polar.py
"""Plot small-signal eigenvalues in polar coords (frequency on radius, damping on angle)."""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt

from pylectra.interfaces.plot import PlotPlugin
from pylectra.registry import register


@register("plot", "eigenvalue_polar")
class EigenvaluePolarPlot(PlotPlugin):
    name = "eigenvalue_polar"
    input_kind = "single"           # expects SimulationResult with small_signal

    def render(self, data, ax=None, *, damping_threshold: float = 0.05, **kwargs):
        ss = getattr(data, "small_signal", None)
        if ss is None:
            raise ValueError("This plot needs a small_signal result. Add small_signal: {kind: finite_difference} to your YAML.")

        eig = ss.eigenvalues
        # Only oscillatory modes
        osc = eig[np.abs(eig.imag) > 0.01]
        freq = np.abs(osc.imag) / (2 * np.pi)
        damp = -osc.real / np.sqrt(osc.real**2 + osc.imag**2)

        if ax is None:
            fig, ax = plt.subplots(subplot_kw=dict(projection="polar"),
                                   figsize=(5, 5))
        else:
            fig = ax.figure

        # Color by whether damping clears the threshold
        colors = np.where(damp >= damping_threshold, "tab:green", "tab:red")
        ax.scatter(damp * np.pi / 2, freq, c=colors, s=50, alpha=0.8)

        ax.set_thetalim(0, np.pi / 2)
        ax.set_xticks([0, np.pi / 8, np.pi / 4, 3 * np.pi / 8, np.pi / 2])
        ax.set_xticklabels(["0%", "12.5%", "25%", "37.5%", "50%"])
        ax.set_title(kwargs.get("title", "Eigenvalue polar (damping × frequency)"))
        return fig
```

YAML stays the same; call from Python:

```python
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39_smallsignal.yaml")
fig = render("eigenvalue_polar", out.result, damping_threshold=0.05)
fig.savefig("polar.pdf")
```

CLI:

```bash
python -m pylectra plot examples/single_case39_smallsignal.yaml \
    --type eigenvalue_polar --output polar.pdf
```

## Example 2: sweep visualization

```python
# pylectra/plotting/cct_sweep.py
"""Bar chart of CCT vs. faulted bus."""
import matplotlib.pyplot as plt
from pylectra.interfaces.plot import PlotPlugin
from pylectra.registry import register


@register("plot", "cct_sweep_bars")
class CCTSweepBars(PlotPlugin):
    name = "cct_sweep_bars"
    input_kind = "sweep"            # expects dict[bus_id, cct_seconds]

    def render(self, data, ax=None, **kwargs):
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 4))
        else:
            fig = ax.figure

        keys = list(data.keys())
        vals = [data[k] * 1000 for k in keys]   # → ms

        ax.bar([str(k) for k in keys], vals, color="tab:blue")
        ax.set_xlabel(kwargs.get("xlabel", "faulted bus"))
        ax.set_ylabel("CCT [ms]")
        ax.axhline(100, color="red", linestyle="--", alpha=0.5,
                   label="protection clearing time")
        ax.legend()
        return fig
```

```python
from pylectra.run import run
from pylectra.plotting import render

# CCT sweep
ccts = {b: run("examples/cct_case39.yaml",
               cct={"bus": b, "t_fault": 0.2, "low": 0.01, "high": 0.40,
                    "tol": 0.005, "max_iter": 15,
                    "stability_filter": {"kind": "angle_stability",
                                         "params": {"max_dev_deg": 180.0}}},
               verbose=0).result.cct
        for b in [4, 14, 16, 21, 23]}

fig = render("cct_sweep_bars", ccts)
fig.savefig("cct_bars.pdf")
```

## Use Nature styling

```python
from pylectra.plotting.style import set_nature_style, journal_figsize

class MyPlot(PlotPlugin):
    def render(self, data, ax=None, **kwargs):
        set_nature_style()              # apply Nature rcParams
        if ax is None:
            fig, ax = plt.subplots(figsize=journal_figsize("single"))
        # ... your plotting code
        return fig
```

## Check what's already there

```python
# 10 built-in plot plugins
import pylectra
from pylectra.registry import list_plugins
print(list_plugins("plot"))
# {'plot': ['acceptance', 'efds', 'heatmap', 'histogram', 'overview',
#           'rotor_angles', 'speeds', 'topology', 'violin', 'voltages']}
```

Always check whether an existing plugin already does what you need. Each built-in is one class in [`pylectra/plotting/*.py`](https://github.com/pylectra/pylectra/tree/main/pylectra/plotting).

## Pass extra kwargs from the CLI

`-O KEY=VALUE` (values are JSON):

```bash
python -m pylectra plot examples/single_case39_smallsignal.yaml \
    --type eigenvalue_polar --output polar.pdf \
    -O damping_threshold=0.05 \
    -O 'title="My case39 spectrum"'
```

## Test

```python
# tests/plotting/test_my_plot.py
import matplotlib
matplotlib.use("Agg")
from pylectra.run import run
from pylectra.plotting import render

def test_eigenvalue_polar_renders():
    out = run("examples/single_case39_smallsignal.yaml", plot=False)
    fig = render("eigenvalue_polar", out.result)
    assert len(fig.axes) >= 1            # at least one Axes drew something
```

## Troubleshooting

### CLI says `unknown plot kind`

The plugin wasn't auto-discovered. Confirm: file is under `pylectra/plotting/`, decorator is correct, category string is `"plot"`.

### Garbled CJK characters in the figure

matplotlib's default font lacks CJK glyphs. Use:

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

or set this *after* `set_nature_style()`.

## Next steps

- [Plugins catalog](../reference/plugins-catalog.md) — built-in 10 plots and their kwargs.
- [pylectra.plotting module](../reference/api/plotting.md) — `render` / `save_figure` / `journal_figsize` API.
