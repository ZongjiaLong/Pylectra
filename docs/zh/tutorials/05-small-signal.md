# 小信号稳定性分析

_进阶_

**前置阅读：** [单次确定性仿真](01-single-run.md)

## 大扰动 vs 小信号

| 维度 | 大扰动稳定性（CCT） | 小信号稳定性 |
|---|---|---|
| 物理意义 | 故障切除后能否回到平衡点 | 平衡点附近微小扰动是否衰减 |
| 数学手段 | 完整非线性 ODE 积分 | Jacobian 特征值 |
| 出来的指标 | CCT [s] | 阻尼比 ζ、振荡频率 f、稳定裕度 σ |
| 关心的工程问题 | 大故障后能保持同步 | 区域间 / 局部低频振荡 |

两者**互补**——研究新方案时通常都要看。

## 一句话原理

把系统在平衡点 y₀ 处线性化：

$$
\dot{y} = f(y) \quad\Longrightarrow\quad \dot{\Delta y} = J \cdot \Delta y, \quad J = \frac{\partial f}{\partial y}\bigg|_{y_0}
$$

J 的**特征值** λ = σ ± jω 决定了：

- **σ < 0**：扰动指数衰减（稳定）
- **σ > 0**：扰动指数发散（不稳定）
- **ζ = −σ / √(σ² + ω²)**：阻尼比（振荡衰减得多快）；电力工程师习惯看 ζ，**< 5% 通常视为风险**
- **f = |ω| / (2π)**：振荡频率 [Hz]

## YAML 模板

```yaml
mode: single
case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: scipy_dop853}

fault: null                              # 不需要故障
skip_integration: true                   # 跳过时域积分，只算平衡点 + 特征值

small_signal:
  kind: finite_difference                # finite_difference | modal
  options:
    epsilon: 1.0e-7                      # 数值微分扰动幅度
    method: central                      # central | forward
    drop_reference_mode: true            # 忽略参考角的 0 模态
    return_eigenvectors: false
    return_jacobian: false
```

`skip_integration: true` 让 pylectra **只算平衡点**（潮流 + 多机初值化 + 小信号），不跑时域——快得多。

## 跑

```python
from pylectra.run import run

out = run("examples/single_case39_smallsignal.yaml")
ss = out.result.small_signal
print(f"is_stable        = {ss.is_stable}")
print(f"stability_margin = {ss.stability_margin:.4f} (max Re(λ))")
print(f"# eigenvalues    = {ss.eigenvalues.shape[0]}")
```

## 解读结果

### 阻尼比表

```python
import numpy as np
import pandas as pd

df = pd.DataFrame({
    "real":     ss.eigenvalues.real,
    "imag":     ss.eigenvalues.imag,
    "freq_hz":  ss.frequencies_hz,
    "damping":  ss.damping_ratios,
})

# 按阻尼比从小到大排（最不稳的 mode 排前面）
df["abs_imag"] = df["imag"].abs()
oscillatory = df[df["abs_imag"] > 0.01].copy()  # 只看振荡 mode
oscillatory = oscillatory.sort_values("damping").head(10)
print(oscillatory.to_string())
```

输出通常长这样：

```
     real      imag   freq_hz  damping
0  -0.21    7.15      1.14     0.029   ← 阻尼最差
1  -0.42    6.93      1.10     0.061
2  -0.78   10.33      1.64     0.075
...
```

第 0 行 ζ ≈ 3% < 5% 阈值，**说明系统对 1.14 Hz 的低频振荡阻尼不足**——典型的区域间振荡问题，研究里通常考虑加 PSS 或重新调励磁参数。

### 复平面散点图

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.scatter(ss.eigenvalues.real, ss.eigenvalues.imag, alpha=0.6)
ax.axvline(0, color="red", linestyle="--", label="稳定边界")
ax.set_xlabel("Re(λ)  [1/s]")
ax.set_ylabel("Im(λ)  [rad/s]")
ax.legend()
plt.show()
```

红线左边 = 稳定，右边 = 不稳定。

## 两种分析器

### `finite_difference`

通过**数值差分**算 Jacobian。

- 每列 J 列要 1～2 次完整 RHS 评估
- 9 × ngen × ngen 维 Jacobian
- 优点：**完全黑盒**，不依赖模型推导
- 缺点：受步长 epsilon 选取影响

```yaml
small_signal:
  kind: finite_difference
  options: {epsilon: 1.0e-7, method: central}
```

### `modal`

继承 `finite_difference` 但默认开启 `return_eigenvectors=True` + 按阻尼比排序。**做模态分析时用这个**。

```yaml
small_signal:
  kind: modal
```

```python
ss = run("...yaml").result.small_signal
ss.eigenvectors      # (n_states, n_states) 复矩阵
# 每列是对应 eigenvalue 的右特征向量
```

## 参与因子

要识别"哪个状态变量对哪个 mode 贡献最大"，需要左右特征向量的 Hadamard 积——这是经典 Verghese-Pérez-Arriaga 公式。

pylectra 当前版本提供 `eigenvectors` 但**不直接算参与因子**。手动算：

```python
import numpy as np
phi = ss.eigenvectors                    # 右特征向量（按列）
psi = np.linalg.inv(phi)                 # 左特征向量（按行）

# 参与因子 P[i, k] = phi[i, k] * psi[k, i]
P = phi * psi.T                          # element-wise
P_abs = np.abs(P)
P_norm = P_abs / P_abs.sum(axis=0, keepdims=True)   # 每个 mode 内归一化

# 找出第 0 个（阻尼最差） mode 的 top 5 状态
top_states = np.argsort(P_norm[:, 0])[::-1][:5]
print("最不稳定的 mode 主要由这些状态参与:", top_states)
```

## 做 batch 小信号扫描

把"小信号是否稳定"作为过滤器：

```yaml
mode: batch
small_signal:
  kind: finite_difference
filters:
  - kind: pf_converged
  - kind: small_signal_stable
    params:
      margin_max: -0.05      # 要求最大特征值实部 ≤ -0.05（最低阻尼率约束）
```

`small_signal_stable` 过滤器把不稳定 / 阻尼太低的样本剔除，剩下的是稳定数据集。

## 性能提示

```
finite_difference 一次算 J 大约要 (9 * ngen) 次 RHS 评估：
- case9    (3 机)  → 27 次  → ~50 ms
- case39   (10 机) → 90 次  → ~200 ms
- case118  (54 机) → 486 次 → ~1.5 s
```

`forward` 方法（`method: forward`）只要一半评估数，但精度只有 O(ε) 而 `central` 是 O(ε²)。**默认用 central 不会错**。

## 常见疑问

### Q：跑出来 `stability_margin > 0`，意味着什么？

平衡点不稳定。但这**不一定是物理不稳定**——可能：

- 潮流没收敛到正确平衡点
- 多机初值化未达稳态（`epsilon` 太松）
- 模型参数有问题

先验证 `out.result.pf_success` 与 `ss.metadata` 里 ε 的取值。

### Q：drop_reference_mode 是什么？

电力系统有一个**自由度**：所有转子角同时旋转 + 一个常数仍然满足方程（参考角自由）。这导致 Jacobian 必然有一个 λ = 0 的"虚假"模态。`drop_reference_mode: true` 时把最接近 0 的那个特征值从稳定性判断里剔除。

### Q：modal 和 finite_difference 数值结果一样吗？

完全一样——modal 只是 finite_difference + 排序 + 默认带 eigenvector。

## 接下来读什么

- [pylectra.small_signal API](../reference/api/small_signal.md) — 字段完整列表
- [自定义过滤器](../how-to/add-new-filter.md) — 写自己的小信号判据
