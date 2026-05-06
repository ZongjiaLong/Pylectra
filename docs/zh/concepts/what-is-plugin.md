# 什么是插件（在 pylectra 中）？

_中级_

**前置阅读：** [什么是 Python 包](what-is-python-package.md)

## 类比：插线板

电力工程师对"插件"应该不陌生。想象一个插线板：

- 插线板本身定义了**插孔的标准接口**（电压、电流、孔型）
- 任何符合这个接口的电器都能插上去工作
- 你不用改插线板，就能加一个新电器

pylectra 就是这样的"插线板"。它定义了若干**插孔类别**：

| 插孔类别 | 用来"插"什么 | 典型示例 |
|---|---|---|
| `generator` | 发电机动力学模型 | `two_axis`（4 阶）、`classical`（2 阶 swing） |
| `exciter` | 励磁系统 | `simple_avr`、`constant` |
| `governor` | 调速器 | `ieee_g`、`constant_power` |
| `pss` | 电力系统稳定器 | `none` |
| `ode_solver` | ODE 求解器 | `scipy_dop853`、`torch_dopri5` |
| `power_flow` | 潮流求解器 | `pandapower`、`newton` |
| `fault` | 故障/事件 | `bus_fault`、`line_trip`、`load_step` |
| `case` | 算例加载器 | `case39`、`case118` |
| `scenario` | 场景扰动生成器 | `load_perturb`、`line_outage` |
| `filter` | 样本过滤器 | `voltage_range`、`angle_stability` |
| `small_signal` | 小信号分析器 | `finite_difference`、`modal` |
| `plot` | 可视化 | `rotor_angles`、`topology`、`heatmap` |

YAML 里写哪个名字，pylectra 就用哪个：

```yaml
solver: {kind: scipy_dop853}    # ← 这就是用 "ode_solver" 类别下名为 "scipy_dop853" 的插件
```

## 核心机制：注册表 + 装饰器

pylectra 内部维护一张**注册表**（registry），就是一张表：

```
"ode_solver" → {
    "scipy_rk45":    <class ScipyRK45>,
    "scipy_dop853":  <class ScipyDOP853>,
    "torch_dopri5":  <class TorchDOPRI5>,
    ...
}
```

新插件被一行 Python 装饰器自动加进去：

```python
from pylectra.interfaces.ode_solver import ODESolver
from pylectra.registry import register

@register("ode_solver", "my_solver")
class MyAwesomeSolver(ODESolver):
    def integrate(self, rhs, t_span, y0, events, options):
        ...
```

`@register("ode_solver", "my_solver")` 这一行做了什么？
等价于：

```python
class MyAwesomeSolver(ODESolver):
    ...

# 把它注册到 registry["ode_solver"]["my_solver"]
registry.register("ode_solver", "my_solver")(MyAwesomeSolver)
```

只要这个 `.py` 文件被 Python 加载过一次，注册就完成了。

## 自动发现

`import pylectra` 时，会自动：

1. 用 `pkgutil.walk_packages` 递归扫描 `pylectra/` 下所有子模块
2. 一一 `import` 它们 → 触发每个文件里的 `@register` 装饰器
3. 注册表填满

所以你**新增一个 `.py` 文件**就够了，**不用改 `__init__.py`**，**不用 patch 框架代码**。

第三方包想发布插件？把自己注册到 `pylectra.plugins` entry point group：

```toml
# pyproject.toml of a 3rd-party package
[project.entry-points."pylectra.plugins"]
my_pack = "my_package.plugins"
```

`pylectra.plugin_loader.discover()` 也会自动扫到。

## 抽象基类（ABC）

每个插件类别有一个对应的**抽象基类**（Abstract Base Class），定义了"必须实现哪些方法"。比如 `ODESolver`：

```python
class ODESolver(ABC):
    engine_kind: str           # "scipy" 或 "torch"

    @abstractmethod
    def integrate(self, rhs, t_span, y0, events, options):
        """必须实现：返回一个 SimulationResult。"""
```

继承它就要实现 `integrate`，否则 Python 在实例化时会报错。这给插件作者一份**契约清单**——只要满足契约，框架就能用上。

类比：实验室里的"标准接口仪器"——只要遵守 GPIB/SCPI 协议，任何品牌的示波器都能接到自动测试系统里。

## 列出所有已注册插件

```bash
python -m pylectra info
```

输出形如：

```
generator    : ['classical', 'two_axis']
exciter      : ['constant', 'simple_avr']
governor     : ['constant_power', 'ieee_g']
ode_solver   : ['scipy_rk45', 'scipy_dop853', 'torch_dopri5', ...]
fault        : ['bus_fault', 'line_trip', 'load_step', 'composite']
...
```

也可以在 Python 里：

```python
import pylectra
from pylectra import registry
print(registry.list_plugins("fault"))
# {'fault': ['bus_fault', 'composite', 'line_trip', 'load_step']}
```

## 为什么这样设计

电力研究的需求高度发散——不同学校有自己的发电机模型、自家定义的故障类型、特定的过滤准则。
传统做法是"fork 整个仿真器、改源码"，结果**升级时和上游就分裂了**。

pylectra 的插件化让：

- 你的扩展是**一个独立 .py 文件**，不动框架
- 升级 pylectra 主版本，你的扩展不动也能跑
- 同一个 YAML 配置可以**同时引用框架内置插件 + 你自己的插件 + 第三方包的插件**

## 接下来读什么

- [如何添加新发电机模型](../how-to/add-new-generator.md) — 实操：从零写一个发电机插件
- [Pylectra 总体架构](architecture.md) — 注册表、引擎、运行器是怎么协作的
