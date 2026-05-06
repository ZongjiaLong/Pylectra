# 临界切除时间（CCT）分析

_中级_

**前置阅读：** [单次确定性仿真](01-single-run.md)

## 什么是 CCT

**CCT（Critical Clearing Time，临界切除时间）** 是电力系统暂态稳定性的经典指标：

> "在故障发生后，多少秒之内必须切除故障，系统才能维持稳定？"

- 故障切得**早** → 干扰短，系统能恢复
- 故障切得**晚** → 转子角偏离过大，系统失步

CCT 就是稳定 / 失稳的分界。算法上是个 **bisection（二分搜索）**：在故障持续时间 `[low, high]` 之间反复试，越来越精确地找到边界。

## YAML 模板

```yaml
mode: cct

case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: modified_euler}

cct:
  bus: 16             # 故障母线
  t_fault: 0.2        # 故障施加时刻（固定）
  low: 0.01           # 二分下界（必须稳定）
  high: 0.30          # 二分上界（必须不稳定）
  tol: 0.005          # 收敛容忍 [s]，到这个精度就停
  max_iter: 15        # 最多二分多少轮
  stability_filter:
    kind: angle_stability      # 用哪个过滤器判稳定
    params:
      max_dev_deg: 180.0

verbose: 1
```

## 跑

```bash
python -m pylectra run examples/cct_case39.yaml
```

输出：

```
[cct] bracket check: low=0.01, high=0.3 (snapped to step 0.001)
[cct] iter  0: duration=0.1500 → unstable
[cct] iter  1: duration=0.0750 → stable
[cct] iter  2: duration=0.1125 → stable
[cct] iter  3: duration=0.1310 → unstable
[cct] iter  4: duration=0.1218 → stable
[cct] iter  5: duration=0.1264 → stable
[cct] iter  6: duration=0.1287 → unstable
[cct] iter  7: duration=0.1276 → unstable
[cct] CCT ≈ 0.1264 s (bracket [0.1264, 0.1276], 8 iters, converged=True)
```

每轮跑一次完整仿真，共 ~10 次。case39 + bus 16 → CCT 约 **127 ms**。

## 边界条件检查

二分前先验证：

- `duration = low` → 必须**稳定**（否则 CCT 在 low 以下，结果无效）
- `duration = high` → 必须**不稳定**（否则 CCT 在 high 以上，bracket 没覆盖）

如果检查失败，pylectra 不二分，直接返回 warning：

```
CCT 在 [0.01, 0.30] 之外，请加宽 bracket。
```

## 选稳定性判据

`cct.stability_filter` 决定"什么算稳定"。两个常用：

### `angle_stability`（默认推荐）

```yaml
stability_filter:
  kind: angle_stability
  params:
    max_dev_deg: 180.0    # 任何机角度偏离系统中心超过 180° 就算失步
```

180° 是国际惯例（first-swing 失步阈值）。研究保守稳定性时可以用 120° 或 90°。

### `voltage_range`（电压稳定性）

```yaml
stability_filter:
  kind: voltage_range
  params:
    vmin: 0.7
    vmax: 1.2
    tail_fraction: 0.3
```

如果故障切除后母线电压恢复不到正常区间，就算"电压不稳定"。

### 复合判据

`stability_filter` 只能写一个。要"同时满足角稳定 + 电压稳定"——写一个**自定义过滤器**（[How-to 添加新过滤器](../how-to/add-new-filter.md)）把多个判据串起来。

## 编程式调用

```python
from pylectra.run import run

out = run("examples/cct_case39.yaml", verbose=0)
print(f"CCT = {out.result.cct * 1000:.1f} ms")
print(f"  bracket: [{out.result.bracket_low:.4f}, {out.result.bracket_high:.4f}]")
print(f"  iters:   {out.result.iterations}")
print(f"  converged: {out.result.converged}")
```

## 用例：扫故障母线，画 CCT-by-bus

```python
from pylectra.run import run
import matplotlib.pyplot as plt

buses = [4, 14, 16, 21, 23, 26, 29]
ccts = []
for b in buses:
    out = run("examples/cct_case39.yaml",
              cct={"bus": b, "t_fault": 0.2, "low": 0.01, "high": 0.40,
                   "tol": 0.005, "max_iter": 15,
                   "stability_filter": {"kind": "angle_stability",
                                        "params": {"max_dev_deg": 180.0}}},
              verbose=0)
    ccts.append(out.result.cct)
    print(f"bus {b}: CCT = {out.result.cct*1000:.1f} ms")

plt.bar([str(b) for b in buses], [c * 1000 for c in ccts])
plt.xlabel("faulted bus")
plt.ylabel("CCT [ms]")
plt.show()
```

> 运行很慢（每个柱子 ~10 次仿真 × 7 = 70 次）。要加速：用 [`scipy_dop853` 求解器](01-single-run.md#solver-choice) 或者用 batch 的 joblib（自己包一层）。

## 常见疑问

### Q：为什么 bracket 要给 `[0.01, 0.30]`？

太窄会触发"边界条件检查失败"；太宽浪费迭代轮数。
经验：

- **case39 / case68 等 IEEE 教学算例**：`[0.01, 0.40]`
- **小型微网**：`[0.001, 0.10]`
- **大型骨干网**：`[0.05, 0.50]`

### Q：`tol: 0.005` 含义？

二分到 `bracket_high - bracket_low ≤ 0.005 s` 就停。**精度 5 ms 通常足够**——CCT 本身物理意义有 ±10 ms 的不确定性（取决于故障类型、保护动作时序）。

### Q：每轮要重跑潮流和初值化吗？

要，因为故障持续时间不同，事件序列不一样。但**算例本身不变**，所以潮流总会收敛到同一个解（节省了发散排查）。

### Q：`modified_euler` 求解器结果会不会受步长 quantisation 影响？

会。`modified_euler` 步长 1 ms 时，事件只能在整数 ms 上触发。pylectra 的 CCT 自动**对齐到 stepsize 整数倍**，所以 `tol < stepsize` 没意义。
**用自适应求解器（`scipy_dop853`）就没这个限制**。

## 在 batch 模式里用 CCT 作过滤器

CCT 本身是个完整的 mode，但你也可以反过来——**在 batch 模式里只接受 CCT > 阈值的工况**。这是个进阶用法：写一个自定义过滤器，内部跑一次 CCT 子流程。详见 [自定义过滤器 how-to](../how-to/add-new-filter.md)。

## 接下来读什么

- [小信号稳定性分析](05-small-signal.md) — CCT 是大扰动稳定性，小信号是局部线性化稳定性，互补研究
- [可视化教程](04-visualization.md) — 把 CCT 扫描结果画成发表级别的图
- [API: pylectra.run.run()](../reference/api/run.md) — 程序化调用的完整签名
