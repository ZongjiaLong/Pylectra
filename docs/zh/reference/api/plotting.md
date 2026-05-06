# `pylectra.plotting` 模块

_参考资料_

**前置阅读：** [可视化教程](../../tutorials/04-visualization.md)

可视化插件 + 样式 + 文件 IO。

## 顶层入口

### `render(name, data, **kwargs)` → `Figure | Axes`

```python
from pylectra.plotting import render
fig = render("rotor_angles", out.result, gen_indices=[0, 1, 2])
```

按注册名查表分发。`name` 取值见 [插件清单](../plugins-catalog.md#plots)。

### `render_plot(kind, source, output, *, formats=None, plot_kwargs=None)`

**CLI 用** —— 跑仿真（如果 source 是 YAML）/ 读 H5 / 读 batch dir，然后画图，**直接写到 output 文件**。

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

## 单次仿真画图函数

每种插件背后是一个函数；想要更细粒度控制，可以直接调：

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

## 网络拓扑

```python
from pylectra.plotting import plot_network

fig = plot_network("case39",
                   color_by="vm_pu",
                   cmap="viridis",
                   bus_size=90,
                   show_labels=False,
                   seed=0)
```

## 批量结果画图函数

```python
from pylectra.plotting import (
    load_metadata,
    plot_acceptance_summary,
    plot_metric_histogram,
    plot_metric_violin,
    plot_metric_heatmap,
)

meta = load_metadata("./out_batch")          # 读 metadata.parquet
plot_metric_histogram(meta, column="filter_angle_stability_metric", bins=40)
plot_metric_violin(meta, column="simulation_time", by="rejected_by")
plot_metric_heatmap(meta,
                    column="filter_angle_stability_metric",
                    rows="meta:fault_bus",
                    cols="meta:load_perturb_sigma_pct",
                    aggfunc="mean",
                    cmap="magma")
```

## 样式 / rcParams

### `set_nature_style()`

应用 Nature 风格 rcParams：Arial 字体、无上/右坐标轴、矢量 PDF 字体内嵌、`axes.linewidth=2.5`、`font.size=16`。

```python
from pylectra.plotting import set_nature_style
set_nature_style()
# 之后所有 matplotlib 图自动应用
```

> `import pylectra.plotting` 时已自动调用一次。

### `nature_palette(name="default") -> list[str]`

返回 Nature 风格调色板的颜色十六进制列表。可选 `"default"` / `"nmi_pastel"`。

### `despine(ax)`

移除 `ax` 的上 / 右两条 spine。`set_nature_style` 已默认开。

## 图像尺寸

### `journal_figsize(layout="single") -> tuple[float, float]`

按 Nature 排版规范返回 `(width_in, height_in)`：

| layout | mm 宽 | inch |
|---|---|---|
| `single` | 89 | (3.50, 2.50) |
| `double` | 183 | (7.20, 4.50) |
| `page` | 247 | (9.72, 6.00) |

```python
from pylectra.plotting import journal_figsize
fig, ax = plt.subplots(figsize=journal_figsize("double"))
```

## 保存

### `save_figure(fig, basename, *, formats=("pdf",), close=True, dpi=600) -> list[Path]`

```python
from pylectra.plotting import save_figure
paths = save_figure(fig, "rotor", formats=["pdf", "svg", "png"])
# [Path("rotor.pdf"), Path("rotor.svg"), Path("rotor.png")]
```

`close=True` 默认释放 Figure 内存。

## 调色板常量

```python
from pylectra.plotting import (
    PALETTE,                      # Nature 默认调色板（10 色）
    PALETTE_NMI_PASTEL,
    DEFAULT_COLORS,
    DEFAULT_COLORS_NMI_PASTEL,
)
```

每个是 `list[str]`，hex 颜色码。

## 接下来读什么

- [可视化教程](../../tutorials/04-visualization.md) — 完整用法
- [添加新可视化](../../how-to/add-new-plot.md) — 自定义 PlotPlugin
- [插件清单](../plugins-catalog.md#plots) — 内置 10 种
