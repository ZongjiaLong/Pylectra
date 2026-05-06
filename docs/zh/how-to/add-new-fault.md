# 添加新的故障类型

_进阶_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)

## 任务

写一个 YAML 里能用 `kind: my_fault` 引用的故障 / 事件插件。

## 故障在 pylectra 里的本质

故障 = **一组定时事件**，每个事件在某时刻**修改算例的某个字段**（母线/支路）。pylectra 把这些事件按时间顺序触发，仿真在故障施加 / 切除点分段积分。

`FaultEvent` ABC 只有一个方法：返回 3 个数组——

```python
def build_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (event, buschange, linechange).

    event:      shape (N, 2)   每行 [time, kind]，kind=1 母线事件 / kind=2 支路事件
    buschange:  shape (N, 4)   每行 [time, bus(1-base), col(1-base), value]
    linechange: shape (N, 4)   每行 [time, branch(1-base), col(1-base), value]
    """
```

## 完整示例：母线短路阻抗可调

```python
# pylectra/faults/bus_fault_impedance.py
"""母线带阻抗的三相短路（不是 bolted 短路）。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import numpy as np

from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "bus_fault_impedance")
@dataclass
class BusFaultWithImpedance(FaultEvent):
    bus: int = 1
    t_fault: float = 0.2
    duration: float = 0.05
    fault_susceptance: float = -100.0    # pu，负值代表故障对地阻抗

    def build_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # event: [time, kind=1 母线事件]
        event = np.array([
            [self.t_fault,                   1],
            [self.t_fault + self.duration,   1],
        ], dtype=float)
        # buschange: [time, bus, col=6 (1-base, BS shunt), value]
        buschange = np.array([
            [self.t_fault,                   self.bus, 6, self.fault_susceptance],
            [self.t_fault + self.duration,   self.bus, 6, 0.0],
        ], dtype=float)
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
```

YAML 里：

```yaml
fault:
  kind: bus_fault_impedance
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.10
    fault_susceptance: -50.0     # 比 -1e10 (bolted) 温和得多
```

## 关键列索引（1-base，MATPOWER 风格）

| 数组 | 列 1 | 列 2 | 列 3 | 列 4 |
|---|---|---|---|---|
| `bus` | 母线号 | 类型 (1=PQ, 2=PV, 3=REF) | **PD（有功负荷）** | **QD（无功负荷）** |
| `bus` | ... 5 = GS | **6 = BS（并联电纳）** | 7 = area | 8 = VM |
| `branch` | F_BUS（首端） | T_BUS（末端） | BR_R | BR_X |
| `branch` | ... 11 = **BR_STATUS（0=断开, 1=投入）** | 12 = ANGMIN | ... | ... |

完整索引在 `pylectra/core/idx.py`。

## 内置 4 种故障对照

| 名字 | 改什么 | 典型用途 |
|---|---|---|
| `bus_fault` | bus col 6 (BS) → 极大负值 | 三相接地短路 |
| `line_trip` | branch col 11 (BR_STATUS) → 0 | 线路跳闸 |
| `load_step` | bus col 3/4 (PD/QD) → 新值 | 负荷阶跃 |
| `composite` | 嵌套子故障 | 复合事件序列 |

## 例 2：发电机退出运行

```python
# pylectra/faults/gen_outage.py
"""发电机退出运行（模拟跳机）。"""
import numpy as np
from dataclasses import dataclass
from pylectra.interfaces.fault import FaultEvent
from pylectra.registry import register


@register("fault", "gen_outage")
@dataclass
class GeneratorOutage(FaultEvent):
    gen_index: int = 1                # 1-base 发电机编号（gen 矩阵的行号）
    t_outage: float = 0.5

    def build_arrays(self):
        # 改 gen 矩阵的 GEN_STATUS 列要走 buschange?
        # 实际上 pylectra 当前事件分发器只支持 bus/branch；要退发电机最稳的办法
        # 是在故障期间把对应母线注入功率清零 —— 用 load_step 模式：
        # 记发电机在 bus B，潮流给的 PG=Pg。事件就是给 bus B 的 PD 加上 Pg：
        # （等效于"少发了 Pg 的电"）
        event     = np.array([[self.t_outage, 1]], dtype=float)
        # 这里只是示意；真实场景需要从 case 里读出 PG 才能填值
        buschange = np.empty((0, 4), dtype=float)
        linechange = np.empty((0, 4), dtype=float)
        return event, buschange, linechange
```

> ⚠️ 这个示例展示了**故障接口的局限**——当前的事件分发器对发电机退出没原生支持。你可以这样做：

> **方案 A（简单）**：用 `load_step` 在发电机母线上加上等量负荷，间接模拟"少发电"
> **方案 B（彻底）**：扩展 `FaultEvent` 接口（你需要改 pylectra 内部，不仅是加插件）

实际工程里 80% 的研究只需要 bus_fault / line_trip / load_step / composite——这 4 个已经能合成绝大多数场景。

## composite 故障：把事件串起来

不需要写新插件——直接在 YAML 里嵌：

```yaml
fault:
  kind: composite
  params:
    events:
      - kind: bus_fault
        params: {bus: 16, t_fault: 0.2, duration: 0.05}    # 短路
      - kind: line_trip
        params: {branch: 21, t_trip: 0.30}                  # 切线
      - kind: load_step
        params: {bus: 4, t_step: 1.0, delta_pd: 100.0}      # 负荷跳跃
```

`composite` 内部把每个子事件的 `build_arrays()` 输出 `vstack` 起来再按时间 sort。

## 测试

```python
# tests/unit/test_my_fault.py
import numpy as np
from pylectra.registry import get

def test_bus_fault_impedance_arrays():
    cls = get("fault", "bus_fault_impedance")
    f = cls(bus=10, t_fault=0.1, duration=0.05, fault_susceptance=-50.0)
    event, bus_arr, line_arr = f.build_arrays()

    assert event.shape == (2, 2)              # 施加 + 切除
    assert bus_arr[0, 0] == 0.10              # 故障开始时刻
    assert bus_arr[0, 3] == -50.0             # 故障阻抗
    assert bus_arr[1, 0] == 0.15              # 切除时刻
    assert bus_arr[1, 3] == 0.0               # 切除恢复
    assert line_arr.size == 0
```

## 排错

### 仿真中 `event` 没触发

事件没在 `t_fault` 那一时刻被引擎读到。常见原因：

- `event` 数组 dtype 不是 `float`（kind 列也要 float！）
- `bus` / `branch` 用了 0-base（pylectra 事件接口要 **1-base**）

### 故障切除后系统不恢复

切除事件值写错了——`bus_fault` 切除时把 BS 改回 **0**（不是恢复成原值）；如果原值非 0，要换成 `composite` 拆分恢复。

## 接下来读什么

- [添加新场景生成器](add-new-scenario.md) — batch 模式的扰动器
- [bus_fault 源码](https://github.com/pylectra/pylectra/blob/main/pylectra/faults/bus_fault.py) — 最简单的内置插件参考
