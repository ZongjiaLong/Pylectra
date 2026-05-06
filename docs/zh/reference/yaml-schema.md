# YAML 配置完整字段表

_参考资料_

每个字段的类型、默认值、取值范围。

## 顶层字段

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `mode` | str | 必填 | `single` / `batch` / `cct` |
| `case_pf` | str / dict / NetworkCase | 必填 | 潮流算例（名字、mpc dict 或 NetworkCase 对象） |
| `case_dyn` | str / dict | 必填 | 动力学参数文件名（如 `case39dyn`） |
| `power_flow` | dict | `{kind: newton}` | 见下 |
| `solver` | dict | `{kind: modified_euler}` | 见下 |
| `fault` | dict / null | null | 见下 |
| `verbose` | int | `1` | 0=静默 / 1=进度 / 2=详细 |
| `plot` | bool | `false` | 仿真完是否弹 matplotlib 窗口 |
| `skip_integration` | bool | `false` | 只算平衡点（small_signal 模式下用） |
| `dynamics` | dict | null | 多机模型分配（默认从 case_dyn 文件读，可覆盖） |
| `small_signal` | dict | null | 见下；单次 / batch 模式都可加 |
| `scenarios` | dict | null（batch 必填） | 见下 |
| `filters` | list[dict] | null（batch / cct 用） | 见下 |
| `output` | dict | null（batch 必填） | 见下 |
| `cct` | dict | null（cct 必填） | 见下 |

## `power_flow`

```yaml
power_flow:
  kind: newton            # newton | pandapower
  options:
    tolerance_mva: 1.0e-8
    max_iteration: 20
    algorithm: nr         # 仅 pandapower：nr | bfsw | gs | fdbx | fdxb
```

## `solver`

```yaml
solver:
  kind: modified_euler    # 见 plugins-catalog
  options:
    rtol: 1.0e-6          # 自适应求解器才有效
    atol: 1.0e-8
    max_step: 0.01
    first_step: null

    # torch 后端额外字段
    chunk_seconds: null   # null 或正数；详见 GPU 加速教程
    torch_dtype: float64  # float64 | float32
    device: auto          # auto | cuda | mps | cpu
    dense_n: 200          # 每 leg 输出点数
```

## `fault`

```yaml
fault:
  kind: bus_fault         # bus_fault | line_trip | load_step | composite
  params:                 # 字段取决于 kind
    bus: 16
    t_fault: 0.2
    duration: 0.05
```

各类型 params 完整字段见 [插件清单](plugins-catalog.md#faults)。

## `dynamics`

```yaml
dynamics:
  defaults:
    generator: {kind: two_axis,        params_file: null}
    exciter:   {kind: simple_avr}
    governor:  {kind: ieee_g}
    pss:       {kind: none}
  overrides:                           # 可按发电机 id 覆盖
    - id: 30
      generator: {kind: classical}
      pss: {kind: none}
```

## `scenarios`（batch 模式必填）

```yaml
scenarios:
  count: 200              # 总样本数
  seed: 42                # 主种子（每样本子种子 = seed + i）
  generators:             # 按声明顺序逐个施加
    - kind: load_perturb
      params: {sigma_pct: 5.0, clip_pct: 20.0}
    - kind: line_outage
      params: {n_outages: 1, prob: 0.5}
```

## `filters`（batch / cct 用）

```yaml
filters:
  - kind: pf_converged
  - kind: voltage_range
    params: {vmin: 0.85, vmax: 1.15, tail_fraction: 0.5}
  - kind: angle_stability
    params: {max_dev_deg: 180.0}
  - kind: simulation_completed
  - kind: small_signal_stable
    params: {margin_max: 0.0}
```

## `output`（batch 模式必填）

```yaml
output:
  directory: ./samples
  format: hdf5            # hdf5 | npz
  metadata: parquet       # parquet | csv
  keep_failed: false
  parallel:
    n_jobs: -1            # int / -1 / "auto"
    backend: loky         # loky | multiprocessing | threading
    batch_size: 4
```

## `cct`（cct 模式必填）

```yaml
cct:
  bus: 16
  t_fault: 0.2
  low: 0.01
  high: 0.30
  tol: 0.005
  max_iter: 15
  stability_filter:
    kind: angle_stability
    params: {max_dev_deg: 180.0}
```

## `small_signal`

```yaml
small_signal:
  kind: finite_difference   # finite_difference | modal
  options:
    epsilon: 1.0e-7
    method: central         # central | forward
    drop_reference_mode: true
    stability_tolerance: 1.0e-4
    return_jacobian: false
    return_eigenvectors: false
```

## YAML 类型特别提醒

| 写法 | 解析为 |
|---|---|
| `0.05` | float |
| `1.0e-6` | float（必须带小数点！） |
| `1e-6` | **string** —— 不是 float（YAML 1.1 坑） |
| `null` | None |
| `~` | None（同上） |
| `yes` / `on` / `true` | bool True |
| `no` / `off` / `false` | bool False |
| `1.0` | float 1.0 |
| `"1.0"` | str "1.0" |

## 用 Python override

`run()` 接受关键字深合并：

```python
from pylectra.run import run
out = run("examples/single_case39.yaml",
          solver={"kind": "scipy_dop853"},                    # 覆盖整个 solver
          fault={"kind": "bus_fault",
                 "params": {"bus": 4, "t_fault": 0.2,
                            "duration": 0.10}})
```

## 接下来读什么

- [插件清单](plugins-catalog.md) — 每个 `kind` 取值的完整列表
- [CLI 参考](cli.md) — `python -m pylectra ...` 命令
