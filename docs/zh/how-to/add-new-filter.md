# 添加新的样本过滤器

_进阶_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)、[批量数据集生成](../tutorials/02-batch-generation.md)

## 任务

写一个 batch / CCT 模式里能用 `kind: my_filter` 的样本判别器。

## 接口

```python
from pylectra.interfaces.filter import SampleFilter, FilterDecision

class SampleFilter(ABC):
    name: str
    @abstractmethod
    def judge(self, result: SimulationResult, scenario, case) -> FilterDecision:
        """判断这一次仿真结果是否通过.

        Returns
        -------
        FilterDecision(passed: bool, reason: str, metric: float | None)
        """
```

`FilterDecision` 三个字段都会写进 Parquet：

- `passed` → metadata 的 `passed` 列（如果**任何**过滤器拒绝，最终 `passed=False`）
- `reason` → 拒绝时记到 `rejected_reason`、`rejected_by` 列
- `metric` → 一个数值，写到 `filter_<name>_metric` 列

## 完整示例：频率偏差判据

```python
# pylectra/filters/frequency_deviation.py
"""稳定性条件：故障切除后，机组频率偏离 50/60 Hz 不超过指定值。"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from pylectra.interfaces.filter import SampleFilter, FilterDecision
from pylectra.registry import register


@register("filter", "frequency_deviation")
@dataclass
class FrequencyDeviationFilter(SampleFilter):
    name: str = "frequency_deviation"
    max_dev_hz: float = 0.5             # 允许的最大偏差 [Hz]
    after_seconds: float = 0.5          # 跳过故障期间，从故障切除多少秒后开始算

    def judge(self, result, scenario, case):
        if not result.pf_success:
            return FilterDecision(False, "PF failed", metric=float("nan"))

        # Speeds 是 omega/(2π·f₀) p.u.；偏差 (Speeds - 1) × f₀ Hz
        f0 = 60.0          # 假设系统 60 Hz；可读取 case.dyn freq
        delta_f = (result.Speeds - 1.0) * f0    # (T, n_gen)

        # 只看故障切除之后的部分
        t = result.Time
        mask = t > self.after_seconds
        if not mask.any():
            return FilterDecision(False, "trajectory too short")

        max_dev = float(np.max(np.abs(delta_f[mask])))
        passed = max_dev <= self.max_dev_hz
        reason = f"max |Δf| = {max_dev:.3f} Hz" + ("" if passed else f" > {self.max_dev_hz}")
        return FilterDecision(passed=passed, reason=reason, metric=max_dev)
```

YAML 里：

```yaml
filters:
  - kind: pf_converged
  - kind: frequency_deviation
    params:
      max_dev_hz: 0.3
      after_seconds: 0.5
```

跑完批量后：

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")

# 看新过滤器的指标分布
print(meta["filter_frequency_deviation_metric"].describe())

# 仅它拒绝的样本
rejected = meta[~meta["passed"] & (meta["rejected_by"] == "frequency_deviation")]
print(f"由频率偏差判据拒绝: {len(rejected)} 个")
```

## 复合判据

只能写一个 stability_filter 但想"同时满足角稳定 + 频率稳定"——把多个过滤器组合：

```python
@register("filter", "angle_and_freq")
@dataclass
class AngleAndFreqFilter(SampleFilter):
    name: str = "angle_and_freq"
    max_dev_deg: float = 180.0
    max_dev_hz: float = 0.5

    def judge(self, result, scenario, case):
        from pylectra.registry import get
        # 复用现成过滤器
        d_ang = get("filter", "angle_stability")(max_dev_deg=self.max_dev_deg).judge(result, scenario, case)
        d_frq = get("filter", "frequency_deviation")(max_dev_hz=self.max_dev_hz).judge(result, scenario, case)
        if not d_ang.passed:
            return d_ang
        if not d_frq.passed:
            return d_frq
        return FilterDecision(passed=True, reason="ok",
                              metric=max(d_ang.metric or 0, d_frq.metric or 0))
```

## "重型"过滤器：内部跑小信号

要在 batch 里加"接受样本必须小信号也稳"的判据——已经有 `small_signal_stable` 内置过滤器，但**它依赖 result.small_signal**——前提是 batch YAML 里开了 `small_signal: {kind: finite_difference}`。

```yaml
mode: batch
small_signal: {kind: finite_difference}      # 仿真时同时算特征值
filters:
  - kind: pf_converged
  - kind: angle_stability
  - kind: small_signal_stable
    params: {margin_max: -0.05}              # 最大特征值实部 ≤ -0.05
```

## 测试

```python
# tests/unit/test_my_filter.py
import math
from pylectra.registry import get

class _StubResult:
    def __init__(self, ok):
        self.pf_success = ok
        # 简化：自己造一个 result-like 对象

def test_frequency_filter_pf_failed_rejects():
    f = get("filter", "frequency_deviation")()
    d = f.judge(_StubResult(ok=False), None, None)
    assert d.passed is False
    assert "PF failed" in d.reason
    assert math.isnan(d.metric)
```

## 实战提示

| 想法 | 实现策略 |
|---|---|
| 只看仿真后期 | 用 `result.Time` 做 mask（如本例 `after_seconds`） |
| 算每台机的指标取最坏 | `np.max(np.abs(... ), axis=0)` 然后再 `max` |
| 多个量同时检查 | 用 `Filter` 复合，或写一个完整新 filter |
| 想加自定义元数据列 | `metric` 是 1 个 float；多列用 scenario 的 metadata |

## 排错

### `metric` 出现 NaN

一般是潮流没收敛 → result 数组是空的 → `np.max()` 在空数组上抛异常。**记得先判 `result.pf_success`**。

### 指标出现在 Parquet 但都是 NaN

`name` 字段没设对。pylectra 用 `name` 作 Parquet 列名键：`filter_<name>_metric`。

## 接下来读什么

- [添加新可视化](add-new-plot.md) — 给 batch 结果画自己的图
- [batch 教程](../tutorials/02-batch-generation.md) — 复习过滤器链怎么用
