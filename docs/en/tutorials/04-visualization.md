# Visualization

_Intermediate_

**Prerequisites:** [Single deterministic simulation](01-single-run.md), [Batch dataset generation](02-batch-generation.md)

pylectra ships 10 publication-quality plot plugins, all reachable through the unified `render(name, data, ...)` interface. This page tours every one.

## Three entry points

### 1. CLI (fastest path to a figure)

```bash
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf
```

The CLI runs one simulation and emits the plot. `--output` controls filename + format (extension-driven: PDF/PNG/SVG).

### 2. Python function

```python
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
fig = render("rotor_angles", out.result, gen_indices=[0, 1, 2, 3])
fig.savefig("rotor.pdf")
```

`render(name, data, **kwargs)` looks up `name` in the registry and dispatches.

### 3. Direct function call (fine-grained)

```python
from pylectra.plotting import plot_rotor_angles
fig = plot_rotor_angles(out.result, relative=True, palette="default")
```

Each plugin wraps an ordinary function.

## Single-run plots (`input_kind="single"`)

Input: a `SimulationResult` object or a path to an `.h5` file.

### `rotor_angles`

Per-machine rotor angles vs. time.

```python
render("rotor_angles", out.result,
       relative=True,                  # subtract the COI (centre of inertia)
       gen_indices=[0, 1, 2, 3],       # only the first 4 machines
       palette="default",
       title="case39 rotor angles")
```

**Pro tip**: `relative=True` keeps the curves compact and makes the maximum angular swing obvious; `relative=False` lets the absolute angles drift visually "to infinity".

### `speeds`

Per-machine rotor speed [p.u.].

```python
render("speeds", out.result, gen_indices="all")
```

Speeds dip / rise briefly during the fault, then converge.

### `voltages`

Bus voltage magnitudes vs. time.

```python
render("voltages", out.result, bus_indices=[15, 16, 17])
```

Faulted buses (e.g. 16) collapse to near 0 during the fault, recover after clearing.

### `efds`

Generator field voltages (excitation output).

```python
render("efds", out.result, gen_indices="all")
```

Useful for inspecting AVR response.

### `overview`

**2×2 panel**: rotor angles + speeds + voltages + torques.

```python
render("overview", out.result)
```

Perfect "system response overview" figure for a paper.

## Network topology (`input_kind="case"`)

### `topology`

```python
render("topology", "case39",
       color_by="vm_pu",
       title="IEEE 39-bus")
```

Input may be a case name (string) or a `NetworkCase` object.

Parameters:

| Parameter | Meaning |
|---|---|
| `color_by` | `"vm_pu"` (voltage magnitude) / `"type"` (PQ/PV/REF) / custom array |
| `cmap` | matplotlib colormap |
| `bus_size` | node size (default 90) |
| `show_labels` | render bus numbers |
| `seed` | spring layout seed (reproducible layout) |

## Batch result plots (`input_kind="batch"`)

Input: the `output.directory` path, the `metadata.parquet` path directly, or a pandas DataFrame.

### `acceptance`

Acceptance / rejection stacked bar with reason breakdown.

```python
render("acceptance", "./out_batch")
```

### `histogram`

Distribution of a metric.

```python
render("histogram", "./out_batch",
       column="filter_angle_stability_metric",
       bins=40)
```

### `violin`

Per-group violin plot.

```python
render("violin", "./out_batch",
       column="simulation_time",
       by="rejected_by")
```

### `heatmap`

2D aggregation (rows × cols → one column's value).

```python
render("heatmap", "./out_batch",
       column="filter_angle_stability_metric",
       rows="meta:fault_bus",
       cols="meta:load_perturb_sigma_pct",
       aggfunc="mean",
       cmap="magma")
```

Example: faulted bus vs. perturbation magnitude, colour = average max-angle-deviation.

## Style tweaks

### Nature layout (default)

pylectra applies Nature-style rcParams automatically: Arial font, no top/right spines, embedded fonts in vector PDFs. `fig.savefig("out.pdf")` is submission-ready.

### Two-column width

```python
from pylectra.plotting import journal_figsize
fig = render("rotor_angles", out.result, figsize=journal_figsize("double"))
```

Three presets: `single` (89 mm) / `double` (183 mm) / `page` (247 mm).

### Multi-format export

```python
from pylectra.plotting import save_figure
save_figure(fig, "rotor", formats=["pdf", "svg", "png"])
# Produces rotor.pdf, rotor.svg, rotor.png
```

CLI:

```bash
python -m pylectra plot examples/single_case39.yaml \
    --type overview --output overview --format pdf,svg,png
```

## Advanced CLI usage

### Pass extra kwargs

```bash
# -O KEY=VALUE overrides plot-function kwargs (values are JSON-decoded)
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf \
    -O relative=true \
    -O 'gen_indices=[0,1,2]' \
    -O 'title="My Plot"'
```

String values need JSON quoting (outer shell quotes + inner `"..."`).

### Plot a saved `.h5` directly

```bash
python -m pylectra plot ./out_batch/sample_000003.h5 \
    --type rotor_angles --output sample3.pdf
```

No re-simulation — the saved trajectory is used as-is.

## Inside a Jupyter Notebook

```python
%matplotlib inline                     # Display below the cell
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
render("overview", out.result)         # auto-displayed
```

To save without displaying:

```python
import matplotlib
matplotlib.use("Agg")                  # non-interactive backend
fig = render("overview", out.result)
fig.savefig("overview.pdf")
import matplotlib.pyplot as plt
plt.close(fig)                         # release memory
```

## Write your own plot

The 10 built-ins not enough? Write a plugin — see [How to add a new plot type](../how-to/add-new-plot.md).
Template: subclass `PlotPlugin`, decorate with `@register("plot", "my_plot")`, implement `render()`. ~10 lines.

## Next steps

- [Add a new plot type](../how-to/add-new-plot.md) — custom plot.
- [Plugins catalog](../reference/plugins-catalog.md) — every plot plugin + default kwargs.
- [pylectra.plotting module](../reference/api/plotting.md) — function-level API.
