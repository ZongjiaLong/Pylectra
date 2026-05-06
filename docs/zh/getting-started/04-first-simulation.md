# 你的第一次仿真

_初学者_

**前置阅读：** [安装 Pylectra](03-install-pylectra.md)、[5 分钟读懂 YAML](../concepts/what-is-yaml.md)

本页带你跑通一次完整的 IEEE 39 节点系统、母线 16 三相短路故障仿真，并逐字段解读 YAML 配置。

## 跑起来

进入 pylectra 源码根目录（路径 2/3 用户），命令行里：

```bash
conda activate pylectra-env       # 激活环境（如果还没激活）
python -m pylectra run examples/single_case39.yaml
```

看到大约这样的输出：

```
> Loading dynamic simulation data...
> Power flow converged
> Constructing augmented admittance matrix...
> Calculating initial state...
> System in steady-state
> Running dynamic simulation...
> Simulation completed in  9.42 seconds
```

仿真结束。如果开启了画图（YAML 里 `plot: true`），还会弹出一个 matplotlib 窗口，画出 10 台发电机的转子角随时间的曲线——故障期间剧烈摇摆，故障切除后逐渐收敛。

## 拆解 YAML

打开 `examples/single_case39.yaml`，你会看到：

```yaml
mode: single                        # 1

case_pf: case39                     # 2
case_dyn: case39dyn

power_flow:                         # 3
  kind: newton

solver:                             # 4
  kind: modified_euler

fault:                              # 5
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05

verbose: 1                          # 6
plot: true
```

逐字段解释：

### ① `mode: single`

三种模式之一：

- `single` — 一次确定性仿真（本页就是这个）
- `batch` — 批量数据集生成
- `cct` — 临界切除时间扫描

### ② `case_pf` / `case_dyn`

要算的电网算例。

- `case_pf` 是稳态潮流算例（**case39** = IEEE 39-bus 标准测试系统）
- `case_dyn` 是动态参数文件（发电机惯量、励磁、调速器等参数）

pylectra 内置了 case9 / 14 / 30 / 39 / 57 / 118 等几个常见算例。完整清单见 [内置插件](../reference/plugins-catalog.md)。

### ③ `power_flow`

潮流求解器：

- `kind: newton` — 经典 Newton-Raphson（默认）
- `kind: pandapower` — 走 pandapower 后端（更鲁棒，需要 `pip install pandapower`）

### ④ `solver`

ODE 求解器：

| 名字 | 类型 | 适用场景 |
|---|---|---|
| `modified_euler` | 固定步长 | 默认，快、与原 MATLAB 输出可比 |
| `runge_kutta` / `rkf` / `rkhh` | 固定 / 自适应 | 老版本兼容求解器 |
| `scipy_rk45` / `scipy_dop853` | 自适应高精度 | 推荐做严格数值实验 |
| `scipy_lsoda` / `scipy_bdf` | 自适应 + 刚性 | 病态系统 |
| `torch_dopri5` 等 | 可选 GPU | 大网络、大批量 |

完整列表见 [YAML schema](../reference/yaml-schema.md)。

### ⑤ `fault`

要施加的故障。本例：母线 16 在 `t=0.2 s` 发生三相接地短路，持续 `0.05 s`（3 周期，60 Hz）后切除。

常用故障类型：

- `bus_fault` — 母线三相短路
- `line_trip` — 线路跳闸
- `load_step` — 负荷阶跃
- `composite` — 复合事件（嵌套上面几种）

### ⑥ `verbose` / `plot`

- `verbose: 1` 输出进度日志（`0` 静默）
- `plot: true` 仿真完弹绘图窗口

## 用 Python API 跑同样的事

CLI 是给"装好就用"的。如果你想在 Notebook 或脚本里编程式调用：

```python
from pylectra.run import run

# 直接传 YAML 路径
out = run("examples/single_case39.yaml")

# 看输出
print(f"仿真时长: {out.result.simulation_time:.2f} s")
print(f"时间点数: {out.result.Time.shape[0]}")
print(f"发电机数: {out.result.Angles.shape[1]}")
print(f"最大角偏差: {out.result.max_angle_deviation_deg:.2f} 度")
```

也可以**直接传 dict**，等价于在 Python 里写 YAML：

```python
out = run({
    "mode": "single",
    "case_pf": "case39",
    "case_dyn": "case39dyn",
    "power_flow": {"kind": "newton"},
    "solver": {"kind": "modified_euler"},
    "fault": {
        "kind": "bus_fault",
        "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05},
    },
    "plot": False,                      # 不弹窗
})
```

或**只覆盖某个字段**（用于参数扫描）：

```python
# 扫不同的故障持续时间
for d in [0.05, 0.10, 0.15, 0.20]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": d}})
    print(f"duration={d:.2f}s, max angle dev={out.result.max_angle_deviation_deg:.1f}°")
```

## 改改试试

试着改 YAML 里几个字段，重跑看现象怎么变：

| 改什么 | 怎么改 | 期待现象 |
|---|---|---|
| 故障母线 | `bus: 16` → `bus: 4` | 不同母线对系统冲击不一样，转子角摇摆幅度不同 |
| 故障时长 | `duration: 0.05` → `duration: 0.20` | 持续越久越接近临界，可能发散 |
| 求解器 | `kind: modified_euler` → `kind: scipy_dop853` | 同样轨迹，但步数减半，更精确 |
| 关闭画图 | `plot: true` → `plot: false` | 跑完就退，不弹窗 |

## 没看到画图？

- 确认 YAML 里 `plot: true`
- 命令行里加 `--no-plot` 会强制关闭画图，去掉这个参数
- macOS 用户在某些后端下需要 `import matplotlib; matplotlib.use("TkAgg")` 才能弹窗——交给我们的可视化命令帮你处理：
  ```bash
  python -m pylectra plot examples/single_case39.yaml --type rotor_angles --output rotor.pdf
  ```

## 接下来读什么

- [理解输出文件](05-understand-output.md) — pylectra 跑完产生了哪些文件、怎么打开看
- [单次确定性仿真（教程）](../tutorials/01-single-run.md) — 更深入解读每个字段的含义
