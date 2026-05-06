# 做参数扫描

_中级_

**前置阅读：** [单次确定性仿真](../tutorials/01-single-run.md)

研究里经常要"扫一个参数看响应"——故障母线、负荷大小、惯量常数等。本页给三种实现路径，从简单到强大。

## 路径 A：Python 循环（最直接）

```python
from pylectra.run import run
import pandas as pd

records = []
for bus in [4, 14, 16, 21, 23, 26, 29]:
    for duration in [0.05, 0.10, 0.15]:
        out = run("examples/single_case39.yaml",
                  fault={"kind": "bus_fault",
                         "params": {"bus": bus,
                                    "t_fault": 0.2,
                                    "duration": duration}},
                  verbose=0,
                  plot=False)
        records.append({
            "bus": bus,
            "duration": duration,
            "max_dev": out.result.max_angle_deviation_deg,
            "pf_ok":   out.result.pf_success,
        })

df = pd.DataFrame(records)
print(df)
```

**优点**：一目了然、灵活，可以现场加 print / 画图。
**缺点**：单进程串行，21 次仿真 × 每次 5 s = 105 s。

## 路径 B：joblib 并行

```python
from joblib import Parallel, delayed
from pylectra.run import run

def _run_one(bus, duration):
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              verbose=0, plot=False)
    return {"bus": bus, "duration": duration,
            "max_dev": out.result.max_angle_deviation_deg}

# 7 母线 × 3 时长 = 21 任务
combos = [(b, d) for b in [4, 14, 16, 21, 23, 26, 29] for d in [0.05, 0.10, 0.15]]
records = Parallel(n_jobs=-1, backend="loky")(
    delayed(_run_one)(b, d) for b, d in combos
)
```

**4 核机器**约 30 s 完成（vs 串行 105 s）。

> Windows 中文用户名机器跑 `loky` 时同 [batch 教程的确定性章节](../tutorials/02-batch-generation.md#determinism) 需要设 `JOBLIB_TEMP_FOLDER`。

## 路径 C：用 batch 模式

如果你的"参数扫描"本质上就是"产生 N 个不同算例"，`mode: batch` 已经把并行/写盘/元数据都做好了。
**关键**：写一个**确定性扰动器**（不用 rng）就把扫描值塞进去。

```python
# pylectra/scenarios/sweep_param.py
from dataclasses import dataclass, field
from typing import List
from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.registry import register

# 全局：sample_id 索引（hack 一下用 closure）
@register("scenario", "param_sweep")
@dataclass
class ParamSweep(ScenarioGenerator):
    """按 sample_id 顺序枚举参数组合。"""
    buses: List[int] = field(default_factory=lambda: [16])
    durations: List[float] = field(default_factory=lambda: [0.05])

    _counter: int = 0     # 不能用：每个 worker 进程独立计数会乱

    def generate(self, base_case, rng):
        # 用 rng 的 state 拿到样本编号—— rng 是 Generator(seed=base+i)
        # 这里更可靠的方式：自己 hash rng.bit_generator.state
        idx = int(rng.integers(0, 10_000_000))    # 不严谨；只是示意
        bus = self.buses[idx % len(self.buses)]
        duration = self.durations[(idx // len(self.buses)) % len(self.durations)]

        case = base_case.copy()
        return Scenario(
            case=case,
            metadata={"sweep_bus": bus, "sweep_duration": duration},
        )
```

> 实际上 batch 模式做"网格扫描"不是其设计目标——batch 是**随机扰动**。
> **要做严格网格扫描**，路径 A/B 更合适。

## 路径 D：`pylectra.run.run_many`

```python
from pylectra.run import run_many

configs = []
for bus in [4, 14, 16]:
    cfg = dict(yaml.safe_load(open("examples/single_case39.yaml")))
    cfg["fault"]["params"]["bus"] = bus
    configs.append(cfg)

results = run_many(configs)            # 串行跑（用并行用路径 B）
for cfg, out in zip(configs, results):
    print(cfg["fault"]["params"]["bus"], out.result.max_angle_deviation_deg)
```

`run_many` 是 `run` 的列表版，**串行**执行。

## 进阶：扫描 + 二维热力图

```python
# 扫故障母线 × 持续时间，画热力图
import numpy as np
import matplotlib.pyplot as plt

buses = [4, 14, 16, 21, 23, 26, 29]
durations = [0.02, 0.05, 0.08, 0.12, 0.16, 0.20]

mat = np.zeros((len(buses), len(durations)))
for i, b in enumerate(buses):
    for j, d in enumerate(durations):
        out = run("examples/single_case39.yaml",
                  fault={"kind": "bus_fault",
                         "params": {"bus": b, "t_fault": 0.2, "duration": d}},
                  verbose=0, plot=False)
        mat[i, j] = out.result.max_angle_deviation_deg

fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(mat, cmap="viridis", aspect="auto")
ax.set_xticks(range(len(durations)))
ax.set_xticklabels([f"{d*1000:.0f}" for d in durations])
ax.set_yticks(range(len(buses)))
ax.set_yticklabels(buses)
ax.set_xlabel("fault duration [ms]")
ax.set_ylabel("faulted bus")
plt.colorbar(im, label="max angle deviation [°]")
plt.show()
```

## 缓存中间结果（避免重复跑）

如果扫描中途中断重跑会很浪费——存到磁盘：

```python
import pickle, os

cache_dir = "./sweep_cache"
os.makedirs(cache_dir, exist_ok=True)

def cached_run(bus, duration):
    cache = f"{cache_dir}/bus{bus}_dur{duration:.3f}.pkl"
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              verbose=0, plot=False)
    with open(cache, "wb") as f:
        pickle.dump(out.result, f)
    return out.result
```

## 该用哪条路径？

| 场景 | 路径 |
|---|---|
| < 50 次仿真，要交互式调 | A（Python 循环） |
| 50–500 次，要并行 | B（joblib） |
| 500+，要持久化 + 元数据 | 用 batch + 自定义 scenario |
| 复现某次扫描结果 | A/B + 缓存 |

## 接下来读什么

- [批量数据集生成](../tutorials/02-batch-generation.md) — 路径 C 的完整玩法
- [并行加速 batch](parallel-batch.md) — joblib 后端选择
