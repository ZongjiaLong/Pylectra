# 添加新的发电机模型

_进阶_

**前置阅读：** [什么是插件](../concepts/what-is-plugin.md)、[Pylectra 总体架构](../concepts/architecture.md)

## 任务

写一个**自定义发电机动力学模型**，能在 YAML 里以 `kind: my_gen` 引用。

## 4 步走

### 1. 新建文件

```
pylectra/models/generators/my_gen.py
```

文件名随意，但放在 `pylectra/models/generators/` 下，启动时才会被自动发现。

### 2. 继承 ABC + 装饰器

```python
# pylectra/models/generators/my_gen.py
"""三阶发电机模型示例（δ, ω, Eq′）。"""
from __future__ import annotations
import numpy as np
from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register


@register("generator", "my_gen")           # ← YAML 里的名字
class MyGenerator(GeneratorModel):
    type_id = 99                           # 1-99 一般够用，避开 1/2 等内置
    n_states = 4                           # 状态向量长度（按 4 维布局填，未用列填 0）

    # 1) 初始化：从潮流解 + 多机参数计算稳态
    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA):
        ...
        return Efd0, Xgen0     # Efd0 形状 (n,)；Xgen0 形状 (n, 4)

    # 2) 导数：dy/dt = f(y)
    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq):
        F = np.zeros_like(Xgen_rows)
        ...
        return F               # (n, 4)

    # 3) 电流：从状态 + 网络电压算出 (Id, Iq, Pe)
    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows):
        ...
        return Id, Iq, Pe      # 各形状 (n,)
```

### 3. 在 YAML 里使用

```yaml
mode: single
case_pf: case39
case_dyn: case39dyn
dynamics:
  defaults:
    generator: {kind: my_gen}
solver: {kind: scipy_dop853}
fault:
  kind: bus_fault
  params: {bus: 16, t_fault: 0.2, duration: 0.05}
```

### 4. 跑

```bash
python -m pylectra info | grep generator        # 应该看到 my_gen 出现在列表
python -m pylectra run my_config.yaml
```

## 完整可工作示例：3 阶模型

```python
# pylectra/models/generators/three_state.py
"""三阶发电机：删去 d 轴瞬态 EMF（Ed' = 0）。

State: [delta, omega, Eq', 0]
导数:
    dδ/dt   = ω - ω_s
    dω/dt   = (π·f / H) · (Pm - Pe)
    dEq'/dt = (Efd - Eq' + (xd - xd')·Id) / Td0'
"""
import numpy as np
from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register
from pylectra.core.idx import idx_gen
from pylectra.core import freq as _f


@register("generator", "three_state")
class ThreeStateGenerator(GeneratorModel):
    type_id = 99
    n_states = 4

    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA):
        (GEN_BUS, PG, QG, *_) = idx_gen()
        n = Pgen_rows.shape[0]
        Xgen0 = np.zeros((n, 4))
        Efd0 = np.zeros(n)
        if n == 0:
            return Efd0, Xgen0

        xd_tr = Pgen_rows[:, 8]
        xd    = Pgen_rows[:, 10]
        xq    = Pgen_rows[:, 11]

        omega0 = np.full(n, 2.0 * np.pi * float(_f.freq))
        Ia0 = (gen_rows[:, PG] - 1j * gen_rows[:, QG]) / np.conj(U_rows) / baseMVA
        phi0 = np.angle(Ia0)
        Eq0 = U_rows + 1j * xq * Ia0
        delta0 = np.angle(Eq0)
        Id0 = -np.abs(Ia0) * np.sin(delta0 - phi0)

        Efd0[:] = np.abs(Eq0) - (xd - xq) * Id0
        Eq_tr0 = Efd0 + (xd - xd_tr) * Id0

        Xgen0[:, 0] = delta0
        Xgen0[:, 1] = omega0
        Xgen0[:, 2] = Eq_tr0
        # col 3 (Ed') 永远为 0
        return Efd0, Xgen0

    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq):
        omegas = 2.0 * np.pi * float(freq)
        omega = Xgen_rows[:, 1]
        Eq_tr = Xgen_rows[:, 2]

        H      = Pgen_rows[:, 6]
        xd_tr  = Pgen_rows[:, 8]
        xd     = Pgen_rows[:, 10]
        Td0_tr = Pgen_rows[:, 12]

        Id = Vgen_rows[:, 0]
        Pe = Vgen_rows[:, 2]
        Efd = Xexc_rows[:, 0]
        Pm  = Xgov_rows[:, 0]

        F = np.zeros_like(Xgen_rows)
        F[:, 0] = omega - omegas
        F[:, 1] = (np.pi * float(freq) / H) * (Pm - Pe)
        F[:, 2] = (Efd - Eq_tr + (xd - xd_tr) * Id) / Td0_tr
        # col 3 (Ed') 不动
        return F

    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows):
        delta = Xgen_rows[:, 0]
        Eq_tr = Xgen_rows[:, 2]
        xd_tr = Pgen_rows[:, 8]
        xq_tr = Pgen_rows[:, 9]

        theta = np.angle(Ubus_rows)
        absU  = np.abs(Ubus_rows)
        vd = -absU * np.sin(delta - theta)
        vq =  absU * np.cos(delta - theta)

        Id = (vq - Eq_tr) / xd_tr
        Iq = -vd / xq_tr                      # Ed' = 0
        Pe = Eq_tr * Iq + (xd_tr - xq_tr) * Id * Iq
        return Id, Iq, Pe
```

## 写测试（推荐）

```python
# tests/numerical/test_three_state.py
import numpy as np
import pylectra
from pylectra.registry import get

def test_three_state_init_steady():
    """init 应得到 dδ/dt ≈ 0 的稳态。"""
    gen = get("generator", "three_state")()
    # ... 构造 Pgen / U / gen 输入
    Efd0, Xgen0 = gen.init(Pgen, U, gen_rows, baseMVA=100.0)
    F = gen.derivative(Xgen0, Xexc0, Xgov0, Pgen, Vgen0, freq=60.0)
    assert np.max(np.abs(F)) < 1e-6           # 稳态导数接近 0
```

## 排错

### "Plugin name 'my_gen' is already registered"

注册表里已经有同名插件——换个名字。

### YAML 里写 `kind: my_gen` 报 `KeyError`

`import pylectra` 时没扫到你的文件。检查：

- 文件**在 `pylectra/models/generators/` 下**（不是 `pylectra/my_models/`）
- 文件**没有以 `_` 开头**（`pkgutil.walk_packages` 默认跳过）
- 装饰器**类别 `"generator"` 拼写对**

### init 跑出来 `derivative` 不接近 0

稳态没初始化对——通常是没读对 `Pgen_rows` 的列下标。
**对照 `pylectra/models/generators/two_axis.py`** 看每列的物理含义。

## 第三方包发布

如果你的模型放在自己的 pip 包里（不是 fork pylectra）：

```toml
# my_package/pyproject.toml
[project.entry-points."pylectra.plugins"]
my_models = "my_package.generators"
```

`my_package/generators/__init__.py` 里导入所有要注册的子模块——`pylectra.plugin_loader.discover()` 会自动扫到。

## 接下来读什么

- [pylectra.interfaces ABC 完整列表](../reference/api/interfaces.md) — 每个 ABC 的方法签名细节
- [添加新故障类型](add-new-fault.md) — 同样的模式，不同的 ABC
- [插件清单](../reference/plugins-catalog.md) — 内置发电机的对照
