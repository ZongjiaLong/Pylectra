# 添加新的场景生成器

_进阶_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)、[批量数据集生成](../tutorials/02-batch-generation.md)

## 任务

写一个 `scenarios.generators` 链里能用 `kind: my_scenario` 引用的扰动器。

## 接口

```python
from pylectra.interfaces.scenario import ScenarioGenerator, Scenario

class ScenarioGenerator(ABC):
    @abstractmethod
    def generate(self, base_case: NetworkCase, rng: np.random.Generator) -> Scenario:
        """从 base_case 生成扰动后的 Scenario.

        Returns
        -------
        Scenario
            含 case (扰动后的副本) + metadata (这次扰动的参数记录)
        """
```

要点：

- **不要修改 `base_case`**——pylectra 已经 deep-copy 过传给你
- 用 `rng`（不要用 `np.random.*` 全局状态）以保证 batch 确定性
- 返回的 `Scenario.metadata` 会**自动写进 Parquet 元数据**（用 `meta:` 前缀）

## 完整示例：发电机出力扰动

```python
# pylectra/scenarios/gen_dispatch_perturb.py
"""随机改每台发电机的有功出力。"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.registry import register
from pylectra.core.idx import PG          # gen 矩阵第 PG 列（1-base 列 2）


@register("scenario", "gen_dispatch")
@dataclass
class GenDispatchPerturb(ScenarioGenerator):
    sigma_pct: float = 5.0          # 高斯扰动 sigma（百分比）
    clip_pct: float = 20.0          # 截断到 ±clip_pct%

    def generate(self, base_case, rng):
        case = base_case.copy()
        gen = case.gen
        n = gen.shape[0]

        factors = rng.normal(loc=1.0, scale=self.sigma_pct / 100.0, size=n)
        clip_lo = 1.0 - self.clip_pct / 100.0
        clip_hi = 1.0 + self.clip_pct / 100.0
        factors = np.clip(factors, clip_lo, clip_hi)

        gen[:, PG] *= factors

        return Scenario(
            case=case,
            metadata={
                "gen_dispatch_sigma_pct": self.sigma_pct,
                "gen_dispatch_factor_min": float(factors.min()),
                "gen_dispatch_factor_max": float(factors.max()),
            },
        )
```

YAML 里：

```yaml
scenarios:
  count: 100
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 5.0}
    - kind: gen_dispatch                # ← 新插件
      params: {sigma_pct: 8.0, clip_pct: 25.0}
```

每个样本的 metadata 在 Parquet 里出现两列：
`meta:gen_dispatch_factor_min`、`meta:gen_dispatch_factor_max`。

## 多个 generator 的执行顺序

`scenarios.generators` 列表按声明顺序逐个执行：

```
base_case
   │
   ▼
load_perturb         ──► case_v1
   │
   ▼
gen_dispatch         ──► case_v2
   │
   ▼
line_outage          ──► case_v3  ──► 跑仿真
```

**每一步看到的是上一步处理过的 case**——所以顺序很重要。

## 概率性扰动

让你的扰动**只有某概率发生**——抽个 `rng.random()`：

```python
@register("scenario", "occasional_step")
@dataclass
class OccasionalStep(ScenarioGenerator):
    bus: int = 1
    delta_pd: float = 100.0
    prob: float = 0.3                   # 30% 的样本有此扰动

    def generate(self, base_case, rng):
        case = base_case.copy()
        applied = rng.random() < self.prob
        if applied:
            from pylectra.core.idx import PD
            case.bus[self.bus - 1, PD] += self.delta_pd
        return Scenario(
            case=case,
            metadata={"occasional_step_applied": int(applied)},
        )
```

batch 跑完后用 metadata 分组：

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")
print(meta.groupby("meta:occasional_step_applied")["passed"].mean())
# 0    0.81     ← 没加扰动的接受率
# 1    0.62     ← 加了扰动的接受率
```

## 测试

```python
# tests/unit/test_my_scenario.py
import numpy as np
from pylectra.core.case import NetworkCase
from pylectra.registry import get

def test_gen_dispatch_seed_determinism():
    """两次相同 seed 得到完全相同结果。"""
    cls = get("scenario", "gen_dispatch")
    s = cls(sigma_pct=5.0, clip_pct=20.0)

    bus = np.zeros((3, 13))
    gen = np.array([[1, 100.0, 0, 0, 0, 1, 100, 1, 200, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]])
    case = NetworkCase({"baseMVA": 100.0, "bus": bus, "gen": gen,
                        "branch": np.zeros((1, 13))})

    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    out_a = s.generate(case, rng_a)
    out_b = s.generate(case, rng_b)
    np.testing.assert_array_equal(out_a.case.gen[:, 1], out_b.case.gen[:, 1])
```

## 排错

### `metadata` 没出现在 Parquet 里

- 返回的不是 `Scenario` 对象
- `metadata` 字段类型不是 dict
- batch 写盘前会过滤非可序列化值（numpy array → 转成 list 或基础类型）

### 多次跑结果不同

没用 `rng` 而是用了 `np.random.*`。**必须用传入的 `rng`**——否则每个 worker 子进程的全局 RNG 不共享。

## 接下来读什么

- [添加新过滤器](add-new-filter.md) — 同样的模式
- [load_perturb 源码](https://github.com/ZongjiaLong/Pylectra/blob/main/pylectra/scenarios/perturb.py) — 内置参考
