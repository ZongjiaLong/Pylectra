# 理解输出文件

_初学者_

**前置阅读：** [你的第一次仿真](04-first-simulation.md)

pylectra 跑完会产生不同形式的输出，取决于运行模式。

## Single 模式：一次仿真

CLI 里 `python -m pylectra run examples/single_case39.yaml` 默认**不写任何文件**——结果在内存里返回，画图后丢弃。

要持久化？两种方法：

### 方法 1：从 Python 调用，自己保存

```python
from pylectra.run import run
import h5py

out = run("examples/single_case39.yaml", plot=False)
res = out.result

# 写到 HDF5
with h5py.File("my_run.h5", "w") as f:
    f.create_dataset("Time",   data=res.Time)
    f.create_dataset("Angles", data=res.Angles)
    f.create_dataset("Speeds", data=res.Speeds)
    # 复数电压拆成实部 + 虚部
    f.create_dataset("Voltages_real", data=res.Voltages.real)
    f.create_dataset("Voltages_imag", data=res.Voltages.imag)

# 写到 npz（numpy 的简单格式）
import numpy as np
np.savez("my_run.npz", Time=res.Time, Angles=res.Angles, Voltages=res.Voltages)
```

### 方法 2：用画图命令直接出图

```bash
python -m pylectra plot examples/single_case39.yaml --type rotor_angles --output rotor.pdf
python -m pylectra plot examples/single_case39.yaml --type overview --output overview.pdf --format pdf,png
```

CLI 会跑一次仿真然后画图，不需要中间文件。

## SimulationResult 对象的字段

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

print(res.Time.shape)        # (N,)         所有采样时刻 [s]
print(res.Voltages.shape)    # (N, n_bus)   每时刻每母线电压（复数）
print(res.Angles.shape)      # (N, n_gen)   每时刻每发电机的转子角 [度]
print(res.Speeds.shape)      # (N, n_gen)   转子转速 [p.u.]
print(res.Eq_trs.shape)      # (N, n_gen)   d 轴 q 轴瞬态 EMF
print(res.Ed_trs.shape)
print(res.Efds.shape)        # (N, n_gen)   场电压 (Efd)
print(res.Tes.shape)         # (N, n_gen)   电磁转矩
print(res.TM.shape)          # (N, n_gen)   机械转矩
print(res.Stepsize.shape)    # (N,)         每步步长（自适应求解器有意义）

# 标量便利属性
print(res.simulation_time)        # 墙钟时长 [s]
print(res.pf_success)             # 潮流是否收敛
print(res.n_steps)                # 总步数
print(res.max_angle_deviation_deg)  # 偏离 COI 的最大角差 [度]
```

## Batch 模式：批量仿真

YAML 里设置 `mode: batch` + `output:` 块时，pylectra 会：

```
output_directory/
├── metadata.parquet                   # 整批样本的元数据（一行一样本）
├── sample_000000.h5                   # 第 0 个样本的时序
├── sample_000001.h5
├── sample_000002.h5
└── ...
```

YAML 例：

```yaml
mode: batch
case_pf: case39
case_dyn: case39dyn
scenarios:
  count: 100
  seed: 42
  generators:
    - {kind: load_perturb, params: {sigma_pct: 5.0}}
output:
  directory: ./out_batch
  format: hdf5            # hdf5 | npz
  metadata: parquet       # parquet | csv
```

### 打开 HDF5 时序文件

```python
import h5py

with h5py.File("out_batch/sample_000000.h5", "r") as f:
    print(list(f.keys()))                # 看里面有哪些 dataset
    Time   = f["Time"][:]                # numpy 数组
    Angles = f["Angles"][:]
    Speeds = f["Speeds"][:]

print(Time.shape, Angles.shape)
```

> HDF5 是科学计算最常用的二进制格式，比 csv 快 10–100 倍且支持复数、多维数组。h5py 是 Python 操作 HDF5 的标准库。

也可以用图形界面浏览：[HDFView](https://www.hdfgroup.org/downloads/hdfview/)（免费）能像文件管理器一样打开 .h5 文件。

### 打开 Parquet 元数据

```python
import pandas as pd

meta = pd.read_parquet("out_batch/metadata.parquet")
print(meta.columns.tolist())
# ['sample_id', 'passed', 'rejected_by', 'rejected_reason',
#  'simulation_time', 'pf_success', 'n_steps', 'n_bus', 'n_gen',
#  'filter_voltage_range_metric', 'filter_angle_stability_metric',
#  'meta:load_perturb_sigma_pct', 'meta:line_outage_branches',
#  'sample_path']

# 看哪些样本通过了过滤器
ok = meta[meta["passed"]]
print(f"{len(ok)} / {len(meta)} 通过过滤")

# 看角度偏差最大的 10 个
top = meta.nlargest(10, "filter_angle_stability_metric")
print(top[["sample_id", "filter_angle_stability_metric"]])
```

> Parquet 是列式存储格式，比 csv 小 10× 且查询快很多。pandas 1.0+ 内置支持。

### 也可以让 pylectra 给你画统计图

```bash
# 接受/拒绝堆叠条
python -m pylectra plot ./out_batch --type acceptance --output acceptance.pdf

# 某个指标的直方图
python -m pylectra plot ./out_batch --type histogram --output hist.pdf \
    -O column='"filter_angle_stability_metric"'

# 小提琴图
python -m pylectra plot ./out_batch --type violin --output violin.pdf \
    -O column='"filter_voltage_range_metric"'
```

## CCT 模式：临界切除时间

```bash
python -m pylectra run examples/cct_case39.yaml
```

CCT 模式不写文件，直接打印结果：

```
[cct] iter  0: duration=0.1500 → unstable
[cct] iter  1: duration=0.0750 → stable
...
[cct] CCT ≈ 0.1270 s (bracket [0.1270, 0.1300], 7 iters, converged=True)
```

要程序化拿到结果：

```python
from pylectra.run import run
out = run("examples/cct_case39.yaml")
print(out.result.cct, out.result.iterations, out.result.converged)
```

## 把日志写到文件

CLI 输出可以重定向到文件保留：

```bash
python -m pylectra run examples/single_case39.yaml > run.log 2>&1
```

`> run.log` 把标准输出写到文件，`2>&1` 把错误也合并进去。

## 接下来读什么

- [单次确定性仿真（教程）](../tutorials/01-single-run.md) — 系统讲解 single 模式的所有可调字段
- [批量数据集生成（教程）](../tutorials/02-batch-generation.md) — 学怎么用 batch 模式构造研究用数据集
