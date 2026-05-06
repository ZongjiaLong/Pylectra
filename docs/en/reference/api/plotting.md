# `pylectra.plotting`

_Reference_

**Prerequisites:** [Visualization tutorial](../../tutorials/04-visualization.md)

Plot plugins + style + figure I/O.

## Top-level entry points

### `render(name, data, **kwargs)` → `Figure | Axes`

```python
from pylectra.plotting import render
fig = render("rotor_angles", out.result, gen_indices=[0, 1, 2])
```

Registry-driven dispatch; `name` is any registered plot. See the [plugins catalog](../plugins-catalog.md#plots-plot).

### `render_plot(kind, source, output, *, formats=None, plot_kwargs=None)`

**CLI-style helper** — runs the simulation (if `source` is a YAML), or reads an existing H5 / batch dir, then writes the figure to `output`.

```python
from pylectra.plotting import render_plot
render_plot("rotor_angles", "examples/single_case39.yaml", "rotor.pdf",
            formats=["pdf", "svg"])
```

### `list_plot_kinds() -> list[str]`

```python
from pylectra.plotting import list_plot_kinds
print(list_plot_kinds())
# ['acceptance', 'efds', 'heatmap', 'histogram', 'overview',
#  'rotor_angles', 'speeds', 'topology', 'violin', 'voltages']
```

## Single-result plot functions

Each plugin wraps a regular function — call it directly for finer control:

```python
from pylectra.plotting import (
    plot_rotor_angles,
    plot_speeds,
    plot_voltage_magnitudes,
    plot_efds,
    plot_overview,
)

fig = plot_rotor_angles(out.result,
                        relative=True,
                        gen_indices=[0, 1, 2],
                        palette="default",
                        title="case39",
                        figsize=(8, 4))
```

## Network topology

```python
from pylectra.plotting import plot_network

fig = plot_network("case39",
                   color_by="vm_pu",
                   cmap="viridis",
                   bus_size=90,
                   show_labels=False,
                   seed=0)
```

## Batch-result plot functions

```python
from pylectra.plotting import (
    load_metadata,
    plot_acceptance_summary,
    plot_metric_histogram,
    plot_metric_violin,
    plot_metric_heatmap,
)

meta = load_metadata("./out_batch")          # reads metadata.parquet
plot_metric_histogram(meta, column="filter_angle_stability_metric", bins=40)
plot_metric_violin(meta, column="simulation_time", by="rejected_by")
plot_metric_heatmap(meta,
                    column="filter_angle_stability_metric",
                    rows="meta:fault_bus",
                    cols="meta:load_perturb_sigma_pct",
                    aggfunc="mean",
                    cmap="magma")
```

## Styling / rcParams

### `set_nature_style()`

Applies Nature-style rcParams: Arial, no top/right spines, embedded fonts in vector PDFs, `axes.linewidth=2.5`, `font.size=16`.

```python
from pylectra.plotting import set_nature_style
set_nature_style()
# All subsequent matplotlib figures inherit these settings
```

> Called automatically when `pylectra.plotting` is imported.

### `nature_palette(name="default") -> list[str]`

Returns a hex-colour list. Options: `"default"` / `"nmi_pastel"`.

### `despine(ax)`

Removes the top and right spines on `ax`. `set_nature_style` enables this for new axes by default.

## Figure sizes

### `journal_figsize(layout="single") -> tuple[float, float]`

Returns `(width_in, height_in)` matching Nature submission rules:

| layout | mm wide | inches |
|---|---|---|
| `single` | 89 | (3.50, 2.50) |
| `double` | 183 | (7.20, 4.50) |
| `page` | 247 | (9.72, 6.00) |

```python
from pylectra.plotting import journal_figsize
fig, ax = plt.subplots(figsize=journal_figsize("double"))
```

## Saving

### `save_figure(fig, basename, *, formats=("pdf",), close=True, dpi=600) -> list[Path]`

```python
from pylectra.plotting import save_figure
paths = save_figure(fig, "rotor", formats=["pdf", "svg", "png"])
# [Path("rotor.pdf"), Path("rotor.svg"), Path("rotor.png")]
```

`close=True` (default) releases the figure to free memory.

## Palette constants

```python
from pylectra.plotting import (
    PALETTE,                      # default 10-colour palette
    PALETTE_NMI_PASTEL,
    DEFAULT_COLORS,
    DEFAULT_COLORS_NMI_PASTEL,
)
```

Each is a `list[str]` of hex codes.

## Next steps

- [Visualization tutorial](../../tutorials/04-visualization.md) — complete usage guide.
- [Add a new plot](../../how-to/add-new-plot.md) — write a custom `PlotPlugin`.
- [Plugins catalog](../plugins-catalog.md#plots-plot) — built-in 10.
