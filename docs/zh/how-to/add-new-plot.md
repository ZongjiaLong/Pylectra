# 添加新的可视化插件

_进阶_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)、[可视化教程](../tutorials/04-visualization.md)

## 任务

写一个 `render(name, data, ...)` 能调用、CLI `pylectra plot --type my_plot` 能引用的可视化插件。

## 接口

```python
from pylectra.interfaces.plot import PlotPlugin

class PlotPlugin(ABC):
    name: str
    input_kind: str   # "single" | "batch" | "case" | "sweep"

    @abstractmethod
    def render(self, data, ax=None, **kwargs):
        """画图并返回 matplotlib Figure / Axes."""
```

`input_kind` 决定 `data` 是什么：

| input_kind | data 是什么 |
|---|---|
| `single` | `SimulationResult` 对象 / `.h5` 路径 |
| `batch`  | metadata.parquet 路径 / DataFrame |
| `case`   | case 名字字符串 / `NetworkCase` |
| `sweep`  | `list[SimulationResult]` 或 dict（用户自己定义） |

## 完整示例：极坐标特征值图

```python
# pylectra/plotting/eigenvalue_polar.py
"""把小信号特征值画到极坐标（频率作半径，阻尼作角度）。"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt

from pylectra.interfaces.plot import PlotPlugin
from pylectra.registry import register


@register("plot", "eigenvalue_polar")
class EigenvaluePolarPlot(PlotPlugin):
    name = "eigenvalue_polar"
    input_kind = "single"           # 期待 SimulationResult，附带 small_signal

    def render(self, data, ax=None, *, damping_threshold: float = 0.05, **kwargs):
        # data 是 SimulationResult 或读过的 dict
        ss = getattr(data, "small_signal", None)
        if ss is None:
            raise ValueError("plot 需要 small_signal 结果。请在 YAML 里加 small_signal: {kind: finite_difference}")

        eig = ss.eigenvalues
        # 只画振荡 mode（虚部 > 0.01）
        osc = eig[np.abs(eig.imag) > 0.01]
        freq = np.abs(osc.imag) / (2 * np.pi)
        damp = -osc.real / np.sqrt(osc.real**2 + osc.imag**2)

        if ax is None:
            fig, ax = plt.subplots(subplot_kw=dict(projection="polar"),
                                   figsize=(5, 5))
        else:
            fig = ax.figure

        # 颜色按是否达到阻尼阈值
        colors = np.where(damp >= damping_threshold, "tab:green", "tab:red")
        ax.scatter(damp * np.pi / 2, freq, c=colors, s=50, alpha=0.8)

        ax.set_thetalim(0, np.pi / 2)
        ax.set_xticks([0, np.pi / 8, np.pi / 4, 3 * np.pi / 8, np.pi / 2])
        ax.set_xticklabels(["0%", "12.5%", "25%", "37.5%", "50%"])
        ax.set_title(kwargs.get("title", "Eigenvalue polar (damping × frequency)"))
        return fig
```

YAML 配置不变；用 Python 调：

```python
from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39_smallsignal.yaml")
fig = render("eigenvalue_polar", out.result, damping_threshold=0.05)
fig.savefig("polar.pdf")
```

CLI 也能用：

```bash
python -m pylectra plot examples/single_case39_smallsignal.yaml \
    --type eigenvalue_polar --output polar.pdf
```

## 例 2：扫描结果可视化

```python
# pylectra/plotting/cct_sweep.py
"""扫描多个母线的 CCT 结果，画柱状对比。"""
import matplotlib.pyplot as plt
from pylectra.interfaces.plot import PlotPlugin
from pylectra.registry import register


@register("plot", "cct_sweep_bars")
class CCTSweepBars(PlotPlugin):
    name = "cct_sweep_bars"
    input_kind = "sweep"            # 期待 dict[bus_id, cct_seconds]

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
                   label="保护动作时间")
        ax.legend()
        return fig
```

```python
from pylectra.run import run
from pylectra.plotting import render

# 跑 CCT 扫描
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

## 用 Nature 风格

```python
from pylectra.plotting.style import set_nature_style, journal_figsize

class MyPlot(PlotPlugin):
    def render(self, data, ax=None, **kwargs):
        set_nature_style()              # 套上 Nature rcParams
        if ax is None:
            fig, ax = plt.subplots(figsize=journal_figsize("single"))
        # ... 你的画图代码
        return fig
```

## 与现有插件对比

```python
# 已有 10 个内置可视化插件
import pylectra
from pylectra.registry import list_plugins
print(list_plugins("plot"))
# {'plot': ['acceptance', 'efds', 'heatmap', 'histogram', 'overview',
#           'rotor_angles', 'speeds', 'topology', 'violin', 'voltages']}
```

写新插件前**先看现成的能不能用**。每个内置都是 [`pylectra/plotting/*.py`](https://github.com/ZongjiaLong/Pylectra/tree/main/pylectra/plotting) 下的一个类。

## 在 CLI 里传额外参数

CLI 用 `-O KEY=VALUE`（值是 JSON）：

```bash
python -m pylectra plot examples/single_case39_smallsignal.yaml \
    --type eigenvalue_polar --output polar.pdf \
    -O damping_threshold=0.05 \
    -O 'title="My case39 spectrum"'
```

## 测试

```python
# tests/plotting/test_my_plot.py
import matplotlib
matplotlib.use("Agg")
from pylectra.run import run
from pylectra.plotting import render

def test_eigenvalue_polar_renders():
    out = run("examples/single_case39_smallsignal.yaml", plot=False)
    fig = render("eigenvalue_polar", out.result)
    assert len(fig.axes) >= 1            # 至少有一个 Axes
```

## 排错

### CLI 报 `unknown plot kind`

YAML 没认到。检查文件在 `pylectra/plotting/` 下、装饰器对、类别 `"plot"` 拼对。

### 中文坐标轴乱码

matplotlib 默认字体不带中文。改用：

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

或者在 set_nature_style() 之后单独设这两行。

## 接下来读什么

- [插件清单](../reference/plugins-catalog.md) — 内置 10 个的参数表
- [pylectra.plotting 模块](../reference/api/plotting.md) — `render` / `save_figure` / `journal_figsize` 等 API
