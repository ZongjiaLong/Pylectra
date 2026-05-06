# 内置插件清单

_参考资料_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)

按类别列出每个内置插件、其 `params` / `options` 字段、源码位置。

## 算例（`case`）

通过 `pandapower.networks` 加载。

| name | 母线数 | 来源 |
|---|---|---|
| `case9` | 9 | WSCC 9-bus |
| `case14` | 14 | IEEE 14-bus |
| `case30` | 30 | IEEE 30-bus |
| `case39` | 39 | IEEE 39-bus（New England） |
| `case57` | 57 | IEEE 57-bus |
| `case118` | 118 | IEEE 118-bus |

源码：`pylectra/cases/pp_builtin.py`

```yaml
case_pf: case39
```

## 潮流（`power_flow`）

| name | 描述 | options |
|---|---|---|
| `newton` | Newton-Raphson（默认） | `tolerance_mva`, `max_iteration` |
| `pandapower` | pandapower runpp | `algorithm` (nr/bfsw/gs/fdbx/fdxb), `tolerance_mva`, `max_iteration` |

## ODE 求解器（`ode_solver`）

### 遗留固定步长

| name | 算法 | 步长来源 |
|---|---|---|
| `modified_euler` | 修正 Euler | `case_dyn.stepsize` |
| `runge_kutta` | RK4 | 同上 |
| `rkf` | RK Fehlberg 4(5) | 同上 |
| `rkhh` | RK Higham–Hall 4(5) | 同上 |

### scipy 自适应

`pylectra/solvers/scipy_solvers.py`

| name | 算法 | 适用 |
|---|---|---|
| `scipy_rk23` | RK 2(3) | 低精度快速 |
| `scipy_rk45` | RK 4(5) Dormand–Prince | **通用默认** |
| `scipy_dop853` | RK 8(7) Dormand–Prince | **高精度** |
| `scipy_lsoda` | LSODA（自动刚性） | 病态系统 |
| `scipy_bdf` | BDF | 强刚性 |
| `scipy_radau` | Radau IIA 5 | 强刚性 + 高精度 |

通用 options：`rtol`, `atol`, `max_step`, `first_step`。

### torch（`pylectra/solvers/torch_solvers.py`）

| name | 算法 | 自适应 |
|---|---|---|
| `torch_dopri5` | RK 5(4) | 是 |
| `torch_dopri8` | RK 8(7) | 是 |
| `torch_rk4` | RK4 | 否 |
| `torch_euler` | Euler | 否 |

torch 额外 options：`chunk_seconds`, `torch_dtype`, `device`, `dense_n`。详见 [GPU 加速教程](../tutorials/06-gpu-acceleration.md)。

## 故障（`fault`） {#faults}

### `bus_fault` — 母线三相短路

```yaml
fault:
  kind: bus_fault
  params:
    bus: 16             # 1-base
    t_fault: 0.2        # [s]
    duration: 0.05      # [s]
```

### `line_trip` — 线路跳闸

```yaml
params:
  branch: 21            # 1-base 支路 row
  t_trip: 0.3
  reclose_after: null   # null = 永久；正数 = 跳后这么久重合
```

### `load_step` — 负荷阶跃

```yaml
params:
  bus: 4
  t_step: 1.0
  delta_pd: 100.0       # [MW]
  delta_qd: 30.0        # [MVAr]
  duration: null        # null = 永久
```

### `composite` — 复合事件

```yaml
params:
  events:
    - {kind: bus_fault,  params: {...}}
    - {kind: line_trip,  params: {...}}
    - {kind: load_step,  params: {...}}
```

源码：`pylectra/faults/`

## 发电机（`generator`）

| name | 阶数 | 状态 |
|---|---|---|
| `classical` | 2 | δ, ω, |E'|, 0 |
| `two_axis` | 4 | δ, ω, Eq', Ed' |

`Pgen` 列约定见各文件 docstring。源码：`pylectra/models/generators/`

## 励磁机（`exciter`）

| name | 描述 |
|---|---|
| `simple_avr` | 一阶 AVR + 余弦电压反馈 |
| `constant` | 常 Efd（无励磁） |

## 调速器（`governor`）

| name | 描述 | 状态 |
|---|---|---|
| `constant_power` | dPm/dt=0 | 1（仅 Pm） |
| `ieee_g` | 4 状态 IEEE 调速器 | Pm, P, x, z |

## PSS（`pss`）

| name | 描述 |
|---|---|
| `none` | 无 PSS |

## 场景生成器（`scenario`）

| name | params |
|---|---|
| `load_perturb` | `sigma_pct`（默认 5），`clip_pct`（默认 20） |
| `line_outage` | `n_outages`（默认 1），`prob`（默认 0.5） |
| `noop` | 无 |

## 过滤器（`filter`）

| name | params |
|---|---|
| `pf_converged` | 无 |
| `voltage_range` | `vmin` (0.85), `vmax` (1.15), `tail_fraction` (1.0) |
| `angle_stability` | `max_dev_deg` (180) |
| `simulation_completed` | `tol` (1e-6) |
| `small_signal_stable` | `margin_max` (0.0) |

## 小信号分析器（`small_signal`）

| name | 描述 |
|---|---|
| `finite_difference` | 数值微分 Jacobian |
| `modal` | 同上 + 阻尼比排序 + 默认存特征向量 |

公共 options：`epsilon`, `method`, `drop_reference_mode`, `return_eigenvectors`, `return_jacobian`。

## 可视化（`plot`） {#plots}

| name | input_kind | 关键参数 |
|---|---|---|
| `rotor_angles` | single | `relative`, `gen_indices`, `palette` |
| `speeds` | single | `gen_indices` |
| `voltages` | single | `bus_indices` |
| `efds` | single | `gen_indices` |
| `overview` | single | — |
| `topology` | case | `color_by`, `cmap`, `bus_size`, `seed` |
| `acceptance` | batch | — |
| `histogram` | batch | `column`, `bins` |
| `violin` | batch | `column`, `by` |
| `heatmap` | batch | `column`, `rows`, `cols`, `aggfunc`, `cmap` |

源码：`pylectra/plotting/`

## 列出运行时已注册插件

```bash
python -m pylectra info
```

或 Python：

```python
import pylectra
from pylectra import registry
for cat in ["generator", "exciter", "governor", "pss", "ode_solver",
            "power_flow", "fault", "case", "scenario", "filter",
            "small_signal", "plot"]:
    print(cat, registry.list_plugins(cat)[cat])
```

## 接下来读什么

- [pylectra.registry API](api/registry.md) — 注册表 API
- [pylectra.interfaces ABC](api/interfaces.md) — 各类别的契约
