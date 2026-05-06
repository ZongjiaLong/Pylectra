# 单次确定性仿真

_中级_

**前置阅读：** [你的第一次仿真](../getting-started/04-first-simulation.md)

入门篇跑通了 case39。本篇深入：每个可调字段、求解器选型、事件配置、错误排查。

## 完整 single 模式 YAML

```yaml
mode: single

# ────── 算例 ──────
case_pf:  case39
case_dyn: case39dyn

# ────── 潮流 ──────
power_flow:
  kind: newton                   # newton | pandapower
  options:
    tolerance_mva: 1.0e-8
    max_iteration: 20

# ────── ODE 求解器 ──────
solver:
  kind: scipy_dop853             # 推荐做严格数值实验
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
    max_step: 0.01
    first_step: null             # null = 让求解器自己估

# ────── 故障 ──────
fault:
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05

# ────── 输出与日志 ──────
verbose: 1                       # 0=静默, 1=一行进度, 2=详细
plot: false                      # 仿真完是否弹窗
```

## 选求解器 {#solver-choice}

### 一图速决

```
精确度要求高？  ─── yes ──► scipy_dop853
       │
       no
       │
非常追求和原 MATLAB 输出一致？  ─── yes ──► modified_euler
       │
       no
       │
系统刚性（特征值差几个数量级）？  ─── yes ──► scipy_lsoda 或 scipy_bdf
       │
       no
       │
       └──► scipy_rk45（最通用的折中）
```

### 实测对比

跑同一个 case39 + bus 16 fault，10 秒仿真：

| 求解器 | 步数 | 墙钟 (s) | 5 s 转子角误差 (相对 dop853) |
|---|---|---|---|
| `modified_euler` | 10 024 | 9.4 | 1e-2 |
| `scipy_rk45` | 1 100 | 4.8 | 1e-5 |
| `scipy_dop853` | 600 | 5.1 | 0（参考） |
| `scipy_lsoda` | 850 | 4.5 | 1e-5 |
| `torch_dopri5` | 600 | 2.6 (CPU) | 1e-4 |

**默认推荐：scipy_dop853** —— 高精度自适应，步数最少。

### 求解器选项

```yaml
solver:
  kind: scipy_dop853
  options:
    rtol: 1.0e-6                # 相对误差容忍（默认 1e-3）
    atol: 1.0e-8                # 绝对误差容忍（默认 1e-6）
    max_step: 0.01              # 最大步长 [s]，事件附近建议设小
    first_step: 0.001           # 首步初值估计
```

> 容忍度往严收紧后步数会上升、墙钟变长，但数值结果更稳。
> **batch 模式做大规模数据集**时，建议 `rtol=1e-4 atol=1e-6` 折中。

## 故障类型详解

### `bus_fault` — 母线三相接地短路

```yaml
fault:
  kind: bus_fault
  params:
    bus: 16            # 1-base 母线编号
    t_fault: 0.2       # 故障施加时刻 [s]
    duration: 0.05     # 故障持续时间 [s]，过后自动切除
```

实现：故障期间母线对地阻抗设为接近 0，`t_fault + duration` 时刻恢复正常。

### `line_trip` — 线路跳闸

```yaml
fault:
  kind: line_trip
  params:
    branch: 21         # 1-base 支路编号（即 case_pf 的 branch 矩阵第 21 行）
    t_trip: 0.3
    reclose_after: 0.5   # 可选；不写则永久跳开
```

### `load_step` — 负荷阶跃

```yaml
fault:
  kind: load_step
  params:
    bus: 4
    t_step: 1.0
    delta_pd: 100.0    # 新增有功 [MW]
    delta_qd: 30.0     # 新增无功 [MVAr]
    duration: 2.0      # 可选；不写则阶跃永久保持
```

### `composite` — 复合事件

模拟"先短路、再线跳"的连锁场景：

```yaml
fault:
  kind: composite
  params:
    events:
      - kind: bus_fault
        params: {bus: 16, t_fault: 0.2, duration: 0.05}
      - kind: line_trip
        params: {branch: 21, t_trip: 0.30}
      - kind: load_step
        params: {bus: 4, t_step: 1.0, delta_pd: 100.0}
```

事件按时间自动排序、依次触发。

## 程序化覆盖单字段

不想为每个变体复制一份 YAML？用 `run()` 的关键字覆盖：

```python
from pylectra.run import run

# 扫故障母线
results = {}
for bus in [4, 16, 23, 30]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": 0.05}})
    results[bus] = out.result.max_angle_deviation_deg
    print(f"bus {bus}: 最大角偏差 {results[bus]:.2f}°")
```

`run()` 把关键字深合并进 YAML，**不会污染原文件**。

## 改变发电机模型

case39 默认用 `two_axis`（4 阶）模型。要全部换成 `classical`（2 阶 swing）：

```yaml
dynamics:
  defaults:
    generator: {kind: classical}
    exciter:   {kind: constant}
    governor:  {kind: constant_power}
    pss:       {kind: none}
```

> 此字段是 0.1.0 的扩展接口，当前 example YAML 没用——legacy 引擎仍按 `case_dyn` 文件里的"模型类型"列分配。Phase 8 的下一阶段会把 `dynamics` 字段提升为主路径。

## 错误排查

### "power flow did not converge"

潮流没收敛。可能原因：

- 算例本身病态（试 `power_flow.kind: pandapower`，更鲁棒）
- 容忍度太严（默认 1e-8，可放宽到 1e-6）
- 负荷扰动后无解（如 batch 模式，负荷被加大到失稳）

### "Native engine supports PSS type 3 only"

YAML 选了 scipy 求解器但 case_dyn 里有 type ≠ 3 的 PSS。两条出路：

- 把 PSS 关掉（`case_dyn` 里 PSS type 列改成 3）
- 改用 legacy 求解器（`solver: {kind: modified_euler}`）

### 转子角发散到无穷

故障太严苛、系统不稳定。试：

- 缩短 `duration`
- 换故障母线
- 把 `solver.options.max_step` 调小（避免数值发散）

## 检查事件是否真的发生

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

# 故障期间电压应该掉到接近 0
import numpy as np
fault_idx = np.where((res.Time >= 0.20) & (res.Time <= 0.25))[0]
print(f"故障期间 bus 16 |V| = {np.abs(res.Voltages[fault_idx, 15]).max():.3f}")
# 期望 ≈ 0.0
```

## 接下来读什么

- [批量数据集生成](02-batch-generation.md) — 把单次仿真扩展到 N 个扰动场景
- [YAML schema 完整字段表](../reference/yaml-schema.md) — 每个字段的默认值和取值范围
- [可视化教程](04-visualization.md) — 把单次结果画成 Nature 投稿质量的图
