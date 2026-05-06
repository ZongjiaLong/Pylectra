# 加载 MATPOWER `.m` 算例

_中级_

**前置阅读：** [单次确定性仿真](../tutorials/01-single-run.md)

## 任务

把一个 MATPOWER 格式的 `.m` 算例文件喂给 pylectra。

## 三种路径

### 路径 A：先用 pandapower 转 → JSON

最稳妥。pandapower 自带 MATPOWER 解析器，转一次保存为 JSON 后就跟 pylectra 内置 case 一样用。

```python
import pandapower as pp
from pandapower.converter import from_mpc

# 1. 读 .m 文件
net = from_mpc("path/to/your_case.m")

# 2. 验证潮流可解
pp.runpp(net)
print(f"PF converged: {len(net.res_bus) > 0}")

# 3. 保存为 pandapower JSON
pp.to_json(net, "your_case.json")
```

### 路径 B：写一个 CaseLoader 插件

把 MATPOWER 文件加进 case 注册表，YAML 里 `kind: my_case` 直接引用：

```python
# pylectra/cases/my_matpower_case.py
from pylectra.interfaces.case_loader import CaseLoader
from pylectra.core.case import NetworkCase
from pylectra.registry import register


@register("case", "ieee300_matpower")
class IEEE300FromMatpower(CaseLoader):
    name = "ieee300_matpower"

    def load(self, identifier):
        from pandapower.converter import from_mpc, to_mpc
        net = from_mpc("/path/to/case300.m")
        raw = to_mpc(net)
        mpc = raw.get("mpc", raw)
        return NetworkCase(mpc, net=net)
```

YAML：

```yaml
case_pf: ieee300_matpower      # 直接用注册名
```

### 路径 C：直接传 dict 到 NetworkCase

如果你有 mpc 风格的 numpy 数组，构造 `NetworkCase` 即可：

```python
from pylectra.core.case import NetworkCase
import numpy as np

case = NetworkCase({
    "baseMVA": 100.0,
    "bus":    np.array([...]),     # 形状 (n_bus, ≥13)
    "gen":    np.array([...]),     # 形状 (n_gen, ≥21)
    "branch": np.array([...]),     # 形状 (n_branch, ≥13)
})

# 用 Python API 跑
from pylectra.run import run
out = run({
    "mode": "single",
    "case_pf": case,                # 也支持直接传 NetworkCase 对象
    "case_dyn": "case39dyn",
    "fault": {"kind": "bus_fault", "params": {"bus": 1, "t_fault": 0.2, "duration": 0.05}},
})
```

## 动力学参数（case_dyn）怎么办？

MATPOWER 只给静态算例，没有发电机动力学参数。要：

- **复用现成的**：如果你的网络拓扑和 case39 类似（10 机），可以从 `case39dyn` 里改
- **手动写**：参考 `case39dyn` 的格式自己造一个 `.py` 文件
- **MATLAB MatDyn 数据**：MatDyn 提供的 `case39dyn.m` 之类的文件，pylectra 的 legacy 加载器能直接读

最简单方案——把每台发电机都用一组**默认参数**：

```python
# pylectra/cases/default_dyn.py 中（示意）
import numpy as np

def make_default_dyn(n_gen, freq=60.0):
    """给 n_gen 台机生成一组保守的默认 4 阶模型参数。"""
    Pgen = np.zeros((n_gen, 14))
    for i in range(n_gen):
        Pgen[i, :] = [
            2,      # genmodel = 2 (4 阶)
            3,      # excmodel = 3
            3,      # pssmodel = 3
            1,      # govmodel = 1
            0,      # bus（filled 后）
            0,      # PG
            5.0,    # H
            0,      # D
            0.30,   # xd_tr
            0.55,   # xq_tr
            1.80,   # xd
            1.70,   # xq
            8.00,   # Td0_tr
            0.40,   # Tq0_tr
        ]
    return Pgen
```

> ⚠️ **慎用默认参数**——是占位用，做严格研究务必用真实参数。

## 完整工作流示例

```python
"""把 MATPOWER case300.m 跑一次 case39 风格的 fault."""
import pandapower as pp
from pandapower.converter import from_mpc, to_mpc
from pylectra.core.case import NetworkCase
from pylectra.run import run

# 1. 转格式
net = from_mpc("case300.m")
mpc_dict = to_mpc(net)["mpc"]
case = NetworkCase(mpc_dict, net=net)

# 2. 跑（注意：case300 没有 case300dyn，要么自己写要么先做潮流分析）
out = run({
    "mode": "single",
    "case_pf": case,
    "case_dyn": "case39dyn",            # 错配的动力学数据，仅作示意
    "skip_integration": True,            # 只算稳态 + 小信号
    "small_signal": {"kind": "modal"},
    "verbose": 1,
})

print(f"潮流是否收敛: {out.result.pf_success}")
```

## 排错

### `from_mpc` 报 "could not parse"

- 文件编码问题：MATPOWER `.m` 用 ASCII；中文注释会导致解析失败，先用 UTF-8 编码器把注释删了或转纯 ASCII
- MATPOWER 版本太旧：从 v6 之前的 case 可能字段不全，pandapower 文档建议用 v7+

### `pp.runpp(net)` 不收敛但原 MATLAB 跑过

可能：

- 算例里有 0 阻抗支路 → pandapower 默认拒绝，加 `pp.runpp(net, distributed_slack=True)` 试试
- 平衡机选取不同 → MATPOWER 用 `bus_type=3` 的母线作平衡机；pandapower 默认的 ext_grid 在 `from_mpc` 里被自动建到第一个 type=3 母线上

### 加完了 pylectra 找不到

`from_mpc` 后**必须 `pp.to_json` 或挂到 case loader**，pylectra 不会去扫盘上的 .m 文件。

## 接下来读什么

- [YAML schema](../reference/yaml-schema.md) — `case_pf` / `case_dyn` 字段的所有用法
- [架构总览](../concepts/architecture.md) — 看 NetworkCase 在引擎里怎么流动
