# Pylectra 总体架构

_中级_

**前置阅读：** [什么是插件](what-is-plugin.md)

## 一图概览

```
                    YAML 配置 / Python dict
                            │
                            ▼
                  ┌───────────────────┐
                  │  pylectra.config  │  ← 解析、校验
                  │  ExperimentConfig │
                  └─────────┬─────────┘
                            │
              mode = single / batch / cct
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │             pylectra.runners           │
        │   SingleRunner   BatchRunner   CCTRunner│
        └─────┬─────────────────┬────────────────┘
              │                 │
              │  joblib 并行     │
              │                 │
              ▼                 ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  pylectra.engine │  │  pylectra.io     │
    │  (ODE 求解 + 事件)│  │  HDF5 / Parquet  │
    └─────────┬────────┘  └──────────────────┘
              │
              │  通过 ABC 调用
              ▼
    ┌─────────────────────────────────────────┐
    │            pylectra.registry             │
    │   {category → {name → plugin class}}     │
    │                                          │
    │   generator   exciter   governor   pss   │
    │   ode_solver  power_flow  fault    case  │
    │   scenario    filter   small_signal plot │
    └─────────────────────────────────────────┘
                  ▲
                  │ @register
                  │
    ┌─────────────────────────────────────────┐
    │         插件实现（pylectra.* 子包）        │
    │  models/  faults/  scenarios/  filters/  │
    │  solvers/ powerflow/ plotting/ cases/    │
    └─────────────────────────────────────────┘
```

## 三层结构

### 第 1 层：配置解析

`pylectra.config.ExperimentConfig`：把 YAML 文件或 Python `dict` 转成强类型对象。
负责：

- YAML schema 校验（缺字段报错、类型检查）
- 路径解析（相对路径 → 绝对路径）
- 默认值填充

只有 schema 在这里固化；具体插件仍按"名字"延后到运行时由 registry 解析。

### 第 2 层：运行器（runners）

```python
from pylectra.runners import SingleRunner, BatchRunner, CCTRunner
```

三种运行模式各自一个类，对外暴露同一个方法 `.run()`：

| Runner | 用途 | 输出 |
|---|---|---|
| `SingleRunner` | 一次确定性仿真 | `SingleRunOutput`（含 `SimulationResult`） |
| `BatchRunner` | 多场景批量数据集生成 | HDF5 文件 + Parquet 元数据 |
| `CCTRunner` | 二分搜索临界切除时间 | `CCTResult` |

`pylectra.run.run(config)` 是顶层入口，根据 `mode` 字段分发到对应 runner。

### 第 3 层：引擎（engine）+ 注册表

#### 引擎

```
pylectra/engine/
├── equilibrium.py    # 潮流 + 多机初值
├── rhs.py            # 拼装 dy/dt = f(t, y)（含网络方程）
├── loop.py           # scipy ODE 主循环（事件分段）
├── torch_engine.py   # torch ODE 主循环（GPU 可选）
└── state.py          # pack/unpack 状态向量
```

引擎本身**不是插件**——它是基础设施。但每一步它都通过 ABC 调用注册表里的插件：

- 潮流 → `power_flow` 插件（`pandapower` / `newton`）
- 发电机导数 → `generator` 插件（`two_axis`、`classical`）
- 励磁机导数 → `exciter` 插件
- ODE 步进 → `ode_solver` 插件
- 故障 on/off → `fault` 插件（注入事件序列）

#### 注册表

```python
pylectra.registry._REGISTRY = {
    "generator": {"two_axis": <class>, "classical": <class>},
    "exciter":   {"simple_avr": <class>, ...},
    ...
}
```

12 个白名单类别，运行时**纯字典查表**。新增分类受限制（避免无序扩展），但同一分类下加新插件**完全开放**。

## 数据在系统里怎么流动

以一次单仿真为例（`mode: single`）：

1. `run("xxx.yaml")` → `ExperimentConfig.from_yaml(...)`
2. 根据 `mode` 实例化 `SingleRunner(cfg)`
3. `SingleRunner.run()`：
   1. 通过 `cfg.case_pf` 字符串去 `case` 注册表里取加载器，得到 `NetworkCase`
   2. 通过 `cfg.power_flow.kind` 取潮流插件，跑 PF → 得到稳态解
   3. 通过 `cfg.dynamics.*` 多机模型取相应 generator/exciter/governor/pss 插件 → 调 `.init()` 算多机初值
   4. 把所有插件的 `.derivative()` 串起来 → 得到一个 `rhs(t, y)` 函数
   5. 通过 `cfg.fault.kind` 取故障插件 → 拿到事件时间表
   6. 通过 `cfg.solver.kind` 取 ODE solver 插件 → 把 `rhs` + 事件喂给它
   7. solver 推进时间，每个 leg（fault on/off 之间）调一次 ODE 求解
   8. 把轨迹打包成 `SimulationResult` 返回

## 三种运行模式的关系

```
SingleRunner  ──────────────► 一次 trajectory
                                    │
                                    ▼
BatchRunner  ──► 循环 N 次 ──► 多次 trajectory ──► HDF5/Parquet
   │             │
   │             └─► scenario 扰动 case → SingleRunner
   │
   └─► joblib 并行 N 个 worker，每个 worker 跑独立的 SingleRunner

CCTRunner  ──► 二分循环 ──► 反复调 SingleRunner（不同 fault duration） ──► CCT
```

`BatchRunner` 和 `CCTRunner` 都把 `SingleRunner` 当成原子操作——这就是为什么 `SingleRunner` 必须**确定性**且**可 pickle**（joblib 并行要求）。

## `pylectra/_legacy/`

这是个**私有内部子包**，存放从原 MatDyn MATLAB 直译过来的 PowerFlow / Models / Auxiliary / Solvers 老代码。
当前的 ODE 主循环还依赖它。它对**最终用户透明**——你不会在公开 API 里见到 `pylectra._legacy`。

未来的版本会用 pandapower + scipy 完全原生重写，届时 `_legacy/` 会被删除。这是公开的技术债，写在 [CHANGELOG.md](https://github.com/pylectra/pylectra/blob/main/CHANGELOG.md) 的"Known limitations"里。

## 可视化系统

```
pylectra/plotting/
├── plugins.py      # @register("plot", ...) 把每种图注册进来
├── time_series.py  # rotor_angles / speeds / efds / voltages / overview
├── topology.py     # 网络拓扑图
├── batch_stats.py  # histogram / violin / heatmap / acceptance
├── style.py        # Nature 风格 rcParams
└── io.py           # 矢量 PDF / 高分辨 PNG 保存
```

`pylectra.plotting.render(name, data, ...)` 在 registry 里查名字、调对应类的 `.render()`。CLI `pylectra plot ...` 走同一条路径。

## 接下来读什么

- [如何添加新发电机模型](../how-to/add-new-generator.md) — 实操体会插件化
- [pylectra.registry 模块](../reference/api/registry.md) — 注册表的 API 细节
