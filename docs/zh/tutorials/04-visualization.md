# 可视化

_中级_

**前置阅读：** [单次确定性仿真](01-single-run.md)、[批量数据集生成](02-batch-generation.md)

pylectra 内置 10 种发表级可视化插件，全部走同一个 `render(name, data, ...)` 接口。本页把每种图都过一遍。

## 三种入口

### 1. CLI（最快出图）

```bash
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf
```

CLI 会跑一次仿真然后画图。`--output` 决定文件名 + 格式（按扩展名识别 PDF/PNG/SVG）。

### 2. Python 函数

```python
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
fig = render("rotor_angles", out.result, gen_indices=[0, 1, 2, 3])
fig.savefig("rotor.pdf")
```

`render(name, data, **kwargs)` 在注册表里查 `name` 调对应类。

### 3. 直接调函数（细粒度）

```python
from pylectra.plotting import plot_rotor_angles
fig = plot_rotor_angles(out.result, relative=True, palette="default")
```

每种插件背后是一个普通函数。

## 单次仿真结果（input_kind="single"）

输入：`SimulationResult` 对象，或一个 `.h5` 文件路径。

### `rotor_angles`

每台机的转子角随时间。

```python
render("rotor_angles", out.result,
       relative=True,                  # 减去 COI（系统中心）
       gen_indices=[0, 1, 2, 3],       # 只画前 4 台
       palette="default",
       title="case39 rotor angles")
```

**专业建议**：`relative=True` 后曲线更紧凑，最大角偏差一目了然；`relative=False` 时绝对角随时间漂移看起来"飞天"。

### `speeds`

每台机转子转速 [p.u.]。

```python
render("speeds", out.result, gen_indices="all")
```

故障期间速度短暂偏离 1.0，然后收敛。

### `voltages`

母线电压幅值随时间。

```python
render("voltages", out.result, bus_indices=[15, 16, 17])
```

故障母线（如 16）电压瞬间跌到接近 0，故障切除后恢复。

### `efds`

发电机场电压（励磁输出）。

```python
render("efds", out.result, gen_indices="all")
```

观察 AVR 调节响应。

### `overview`

**2×2 总览面板**：转子角 + 转速 + 电压 + 转矩 一图打全。

```python
render("overview", out.result)
```

适合论文里"系统响应概览"那个总图。

## 网络拓扑（input_kind="case"）

### `topology`

```python
render("topology", "case39",
       color_by="vm_pu",               # 按电压幅值上色
       title="IEEE 39-bus")
```

输入可以是 case 名（字符串）或一个 `NetworkCase` 对象。

参数：

| 参数 | 含义 |
|---|---|
| `color_by` | `"vm_pu"`（电压幅值）/ `"type"`（PQ/PV/REF）/ 自定义数组 |
| `cmap` | matplotlib colormap 名字 |
| `bus_size` | 节点圆圈大小（默认 90） |
| `show_labels` | 是否显示母线编号 |
| `seed` | spring layout 的随机种子（保证可复现） |

## 批量结果（input_kind="batch"）

输入：`output.directory` 路径，或者 `metadata.parquet` 直接路径，或 pandas DataFrame。

### `acceptance`

接受 vs 拒绝堆叠条 + 拒绝原因细分。

```python
render("acceptance", "./out_batch")
```

### `histogram`

某个指标的分布。

```python
render("histogram", "./out_batch",
       column="filter_angle_stability_metric",
       bins=40)
```

### `violin`

按某分组变量画小提琴图。

```python
render("violin", "./out_batch",
       column="simulation_time",
       by="rejected_by")              # 按拒绝原因分组
```

### `heatmap`

二维聚合（一行一列各一个变量，颜色是另一个）。

```python
render("heatmap", "./out_batch",
       column="filter_angle_stability_metric",
       rows="meta:fault_bus",
       cols="meta:load_perturb_sigma_pct",
       aggfunc="mean",
       cmap="magma")
```

例：故障母线 vs 负荷扰动幅度，颜色显示平均最大角偏差。

## 给图换风格

### Nature 排版（默认）

pylectra 自动套上 Nature 风格 rcParams：Arial 字体、无上/右坐标轴、矢量 PDF 字体内嵌。
直接 `fig.savefig("out.pdf")` 就投稿可用。

### 双栏宽度

```python
from pylectra.plotting import journal_figsize
fig = render("rotor_angles", out.result, figsize=journal_figsize("double"))
```

`single`（89 mm）/ `double`（183 mm）/ `page`（247 mm）三档。

### 多格式输出

```python
from pylectra.plotting import save_figure
save_figure(fig, "rotor", formats=["pdf", "svg", "png"])
# 生成 rotor.pdf, rotor.svg, rotor.png
```

CLI：

```bash
python -m pylectra plot examples/single_case39.yaml \
    --type overview --output overview --format pdf,svg,png
```

## CLI 高级用法

### 传额外参数

```bash
# -O KEY=VALUE 覆盖 plot 函数关键字（值用 JSON）
python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf \
    -O relative=true \
    -O 'gen_indices=[0,1,2]' \
    -O 'title="My Plot"'
```

字符串值要套 JSON 字符串（外层引号 + 内层 `"..."`）。

### 直接画 .h5 文件

```bash
python -m pylectra plot ./out_batch/sample_000003.h5 \
    --type rotor_angles --output sample3.pdf
```

不会再跑仿真，直接读取已存盘的轨迹画。

## 在 Jupyter Notebook 里

```python
%matplotlib inline                     # 让图显示在 cell 下方
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
render("overview", out.result)         # 自动 display
```

如果想保存而不显示：

```python
import matplotlib
matplotlib.use("Agg")                  # 非交互后端
fig = render("overview", out.result)
fig.savefig("overview.pdf")
import matplotlib.pyplot as plt
plt.close(fig)                         # 释放内存
```

## 写自己的图

10 种内置不够？写一个自己的——见 [如何添加新可视化插件](../how-to/add-new-plot.md)。
模板：继承 `PlotPlugin`、加 `@register("plot", "my_plot")`、实现 `render()`。10 行代码。

## 接下来读什么

- [添加新可视化插件](../how-to/add-new-plot.md) — 自定义图类型
- [插件清单](../reference/plugins-catalog.md) — 所有可视化插件 + 默认参数
- [pylectra.plotting 模块](../reference/api/plotting.md) — 函数级 API
