# `pylectra.small_signal` 模块

_参考资料_

**前置阅读：** [小信号稳定性分析](../../tutorials/05-small-signal.md)

线性化与特征值分析的全部 API。

## 类层次

```
SmallSignalAnalyzer (ABC)
└── FiniteDifferenceAnalyzer        # @register("small_signal", "finite_difference")
    └── ModalAnalyzer               # @register("small_signal", "modal")
```

## `FiniteDifferenceAnalyzer`

```python
class FiniteDifferenceAnalyzer:
    def __init__(self,
                 epsilon: float = 1e-6,
                 method: str = "central",            # "central" | "forward"
                 drop_reference_mode: bool = True,
                 stability_tolerance: float = 1e-4,
                 return_jacobian: bool = False,
                 return_eigenvectors: bool = False)
```

**参数**

| 参数 | 默认 | 说明 |
|---|---|---|
| `epsilon` | `1e-6` | 数值微分扰动幅度 |
| `method` | `"central"` | central（O(ε²)，2n 次评估）/ forward（O(ε)，n+1 次） |
| `drop_reference_mode` | `True` | 忽略接近 0 的参考角模态 |
| `stability_tolerance` | `1e-4` | Re(λ) ≤ tol 即视为稳定 |
| `return_jacobian` | `False` | 是否在结果里保留 Jacobian 矩阵 |
| `return_eigenvectors` | `False` | 是否计算右特征向量 |

## `ModalAnalyzer`

继承 `FiniteDifferenceAnalyzer`，默认开 `return_eigenvectors=True` + `return_jacobian=True`，按阻尼比从小到大排序。

```python
from pylectra.registry import get
analyzer = get("small_signal", "modal")()
```

## `analyze(rhs, y0, layout, *, t0=0.0)`

```python
def analyze(self, rhs, y0: np.ndarray, layout, *, t0: float = 0.0) -> SmallSignalResult
```

**参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `rhs` | callable | `f(t, y) -> dy/dt` 的 ODE 右端 |
| `y0` | `np.ndarray` | 平衡点状态向量（要求 `f(t0, y0) ≈ 0`） |
| `layout` | `StateLayout` | 状态布局对象（含 `ngen`、`n_states`） |
| `t0` | float | Jacobian 评估时刻（自治系统给 0 即可） |

## `SmallSignalResult` 字段

```python
@dataclass
class SmallSignalResult:
    eigenvalues: np.ndarray              # (n,) complex
    eigenvectors: np.ndarray | None      # (n, n) complex
    jacobian: np.ndarray | None          # (n, n) float
    is_stable: bool
    stability_margin: float              # max Re(λ)（去掉参考模态后）
    damping_ratios: np.ndarray           # (n,) float，NaN 表示纯实模态或 0 模态
    frequencies_hz: np.ndarray           # (n,) float = |Im(λ)| / 2π
    metadata: dict                       # method, epsilon, wall_time_sec, n_states 等
```

## 用法

### 跑一次小信号

```python
from pylectra.run import run

out = run({
    "mode": "single",
    "case_pf": "case39",
    "case_dyn": "case39dyn",
    "skip_integration": True,
    "small_signal": {"kind": "modal"},
})
ss = out.result.small_signal
print(ss.is_stable, ss.stability_margin)
```

### 计算参与因子

```python
import numpy as np
phi = ss.eigenvectors                        # 右特征向量（按列）
psi = np.linalg.inv(phi)                     # 左特征向量（按行）
P = phi * psi.T                              # element-wise → (n_states, n_modes)
P_norm = np.abs(P) / np.abs(P).sum(axis=0, keepdims=True)
```

### 找最不稳定的模态

```python
import numpy as np
osc = ss.eigenvalues[np.abs(ss.eigenvalues.imag) > 0.01]
worst_idx = np.argmin(ss.damping_ratios[np.abs(ss.eigenvalues.imag) > 0.01])
print(f"最差阻尼模态: λ = {osc[worst_idx]:.4f}, ζ = {ss.damping_ratios[worst_idx]:.4f}")
```

## `small_signal_stable` 过滤器

batch 模式里把"小信号稳定"作为接受条件：

```yaml
mode: batch
small_signal: {kind: finite_difference}     # 仿真时同时算
filters:
  - kind: pf_converged
  - kind: small_signal_stable
    params: {margin_max: -0.05}             # 最大特征值实部 ≤ -0.05
```

## 性能

| 算例 | 状态维度 (9 × n_gen) | central FD 时长 |
|---|---|---|
| case9 | 27 | ~50 ms |
| case39 | 90 | ~200 ms |
| case118 | 486 | ~1.5 s |

`forward` 方法约一半时长，但精度从 O(ε²) 降到 O(ε)。**默认 central 不会错**。

## 接下来读什么

- [小信号稳定性教程](../../tutorials/05-small-signal.md) — 完整用例
- [pylectra.interfaces SmallSignalAnalyzer](interfaces.md#smallsignalanalyzer) — ABC
