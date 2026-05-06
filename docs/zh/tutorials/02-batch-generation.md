# 批量数据集生成

_中级_

**前置阅读：** [单次确定性仿真](01-single-run.md)、[5 分钟读懂 YAML](../concepts/what-is-yaml.md)

batch 模式是 pylectra 最核心的功能：从一个基准算例出发，**自动生成 N 个扰动场景**，每个跑一次仿真，**通过过滤器**的留作样本。常用于训练机器学习模型、稳定性统计研究、概率潮流。

## 一个完整 batch YAML

```yaml
mode: batch

# ────── 基准算例 ──────
case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: modified_euler}

# ────── 故障（每个场景都跑同一个故障）──────
fault:
  kind: bus_fault
  params: {bus: 16, t_fault: 0.2, duration: 0.05}

# ────── 场景生成 ──────
scenarios:
  count: 200                          # 生成 200 个样本
  seed: 42                            # 主种子（可复现）
  generators:
    - kind: load_perturb
      params:
        sigma_pct: 5.0                # 每个负荷加 5% 高斯扰动
        clip_pct: 20.0                # 截断到 ±20%
    - kind: line_outage
      params:
        n_outages: 1                  # 每个样本随机切 1 条线
        prob: 0.5                     # 50% 的样本被加这个事件

# ────── 过滤器链 ──────
filters:
  - kind: pf_converged                # 潮流没收敛 → 拒绝
  - kind: voltage_range
    params: {vmin: 0.85, vmax: 1.15, tail_fraction: 0.5}
  - kind: angle_stability
    params: {max_dev_deg: 180.0}
  - kind: simulation_completed

# ────── 输出 ──────
output:
  directory: ./out_batch
  format: hdf5                        # hdf5 | npz
  metadata: parquet                   # parquet | csv
  keep_failed: false                  # 拒绝的样本是否也写盘
  parallel:
    n_jobs: -1                        # -1 = 全部 CPU 核
    backend: loky                     # loky | multiprocessing | threading

verbose: 1
```

## 核心概念

### 场景生成器（Scenario Generators）

每生成一个样本前，pylectra 把基准算例**复制一份**，按 `scenarios.generators` 里的顺序**逐个施加扰动**。

内置 3 种：

| 名字 | 做什么 | 关键参数 |
|---|---|---|
| `load_perturb` | 给每个母线 PD/QD 加高斯扰动 | `sigma_pct`、`clip_pct` |
| `line_outage` | 随机切几条线 | `n_outages`、`prob` |
| `noop` | 什么都不做（控制组） | 无 |

写自己的扰动器 → 看 [如何添加新场景生成器](../how-to/add-new-scenario.md)。

### 过滤器链（Filter Chain）

仿真完成后按 `filters` 里的顺序逐个判断；**任何一个拒绝**该样本就被打 `passed=False`。

内置 5 种：

| 名字 | 拒绝条件 |
|---|---|
| `pf_converged` | 初始潮流不收敛 |
| `voltage_range` | 任何一个母线电压跑出 [vmin, vmax] |
| `angle_stability` | 任何机角度偏离系统中心 (COI) 超过 `max_dev_deg` |
| `simulation_completed` | 仿真没跑到 `stoptime`（求解器中途放弃） |
| `small_signal_stable` | 小信号特征值有正实部 |

`voltage_range` 的 `tail_fraction: 0.5` 表示**只检查后 50% 时段的电压**——避开故障期间的天然低压区，专看故障切除后的恢复情况。

## 跑起来

```bash
python -m pylectra run examples/batch_case39.yaml
```

输出大概这样：

```
[batch] 1/200 ACCEPT
[batch] 2/200 REJECT (voltage_range: bus 12 dipped to 0.81 pu)
[batch] 3/200 ACCEPT
...
[batch] done: 152/200 accepted (38 rejected, 10 PF-failed) in 184.2s, n_jobs=8.
        metadata: ./out_batch/metadata.parquet
```

## 拿结果

### Parquet 元数据：每个样本的指标

```python
import pandas as pd

meta = pd.read_parquet("./out_batch/metadata.parquet")
print(meta.shape)                    # (200, ~20)
print(meta.columns.tolist())

# 通过率
print(f"接受率: {meta['passed'].mean():.1%}")

# 拒绝原因排名
print(meta[~meta["passed"]]["rejected_by"].value_counts())

# 每个扰动配置和指标的相关
import numpy as np
ok = meta[meta["passed"]]
corr = ok[[c for c in ok.columns if c.startswith("meta:") or c.startswith("filter_")]].corr()
print(corr["filter_angle_stability_metric"].sort_values(ascending=False).head(5))
```

### HDF5 时序：每个样本的轨迹

```python
import h5py
import numpy as np

# 读所有通过样本的最大角偏差
ok_ids = meta[meta["passed"]]["sample_id"].tolist()
all_max_devs = []
for sid in ok_ids:
    with h5py.File(f"./out_batch/sample_{sid:06d}.h5", "r") as f:
        ang = f["Angles"][:]                             # (T, n_gen)
        max_dev = np.max(np.abs(ang - ang.mean(axis=1, keepdims=True)))
        all_max_devs.append(max_dev)

import matplotlib.pyplot as plt
plt.hist(all_max_devs, bins=30)
plt.xlabel("max angle deviation [°]")
plt.ylabel("count")
plt.show()
```

## 确定性（可复现性） {#determinism}

batch 是**严格确定性**的：

- `scenarios.seed` 作为主种子
- 第 i 个样本用子种子 `seed + i`（在 worker 子进程内重新构造 RNG）
- 因此 `n_jobs=1` 和 `n_jobs=-1` 对**完全相同的输出**

这条性质由 `tests/integration/test_batch_parallel_determinism.py` 守护——两次独立运行的 HDF5 byte-identical。

## 设计扰动模式

### 案例 1：单一参数扫描

只想扫"负荷扰动幅度对稳定性的影响"——把 `line_outage` 关掉：

```yaml
scenarios:
  count: 100
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 10.0}        # 大扰动
```

### 案例 2：N-1 故障数据集

只想扫"切某条线后系统是否稳定"：

```yaml
scenarios:
  count: 46                            # case39 有 46 条线
  seed: 42
  generators:
    - kind: line_outage
      params: {n_outages: 1, prob: 1.0}   # 每个样本必切 1 条
```

### 案例 3：极端工况组合

负荷大波动 + N-2 故障：

```yaml
scenarios:
  count: 1000
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 15.0, clip_pct: 50.0}
    - kind: line_outage
      params: {n_outages: 2, prob: 0.8}
```

## 运行时调优

| 想要的效果 | 改哪 |
|---|---|
| 跑更快 | `n_jobs: -1`（全核）；`solver.kind: scipy_dop853`（步少） |
| 占内存更小 | `n_jobs: 4`（限制并发）；不打开 `keep_failed` |
| 实时看进度 | `verbose: 2` |
| 通过率太低 | 放宽过滤器或缩小扰动幅度 |
| 通过率太高（要更困难场景） | 加扰动幅度 / 加过滤器（如 `small_signal_stable`） |

## 增量生成（中断后续跑）

batch 默认从头开始。若已经跑了 100 个想再加 100：用 [参数扫描 how-to](../how-to/parameter-sweep.md)。

## 跑大批量怎么估时间

10 个样本试跑：

```yaml
scenarios:
  count: 10
  seed: 42
  generators:
    - {kind: load_perturb, params: {sigma_pct: 5.0}}
output:
  directory: ./out_test
  parallel: {n_jobs: -1}
```

记下完成时间 T。**目标 N 个样本估时**：`T_total ≈ T × (N / 10)`（核数足够时）。注意冷启动 + 写盘开销在小 batch 里占比大。

## 接下来读什么

- [临界切除时间分析](03-cct.md) — 同样的引擎，但用二分搜索"故障多长时系统就不稳了"
- [并行加速 batch](../how-to/parallel-batch.md) — joblib 后端选择、Windows 上的特殊问题
- [添加新场景生成器](../how-to/add-new-scenario.md) — 写自己的扰动模式
- [添加新过滤器](../how-to/add-new-filter.md) — 写自己的样本筛选逻辑
