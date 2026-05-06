# 为长仿真调内存

_进阶_

**前置阅读：** [GPU 加速教程](../tutorials/06-gpu-acceleration.md)

跑 100+ 秒仿真、case2000+ 大网络、或者 batch 模式 16 worker 同时跑——内存吃紧是常态。本页给一组**逐级递增的优化清单**。

## 第一档：YAML 调参（无需改代码）

### 关掉非必要的轨迹保存

```yaml
solver:
  options:
    dense_n: 50          # torch 模式每 leg 输出点数（默认 200）→ 减到 50
```

### 关掉 batch 元数据里的额外字段

```yaml
output:
  keep_failed: false     # 不保留拒绝的样本（默认就是 false）
  format: hdf5           # 比 npz 小 2-3 倍
  metadata: parquet      # 比 csv 小 10 倍
```

## 第二档：torch 引擎的 chunk_seconds

如果你已经切到 torch 后端：

```yaml
solver:
  kind: torch_dopri5
  options:
    chunk_seconds: 0.5     # 把每个 leg 切成 0.5 s 窗口
```

效果（case39 + 10 s 仿真）：

| `chunk_seconds` | 峰值显存 | 速度 |
|---|---|---|
| `null`（默认） | 1.0 GB | 100% |
| `1.0` | 0.5 GB | 95% |
| `0.5` | 0.25 GB | 90% |
| `0.1` | 50 MB | 70% |

详细见 [GPU 加速 — 内存爆炸怎么办](../tutorials/06-gpu-acceleration.md#oom)。

## 第三档：减小 batch 并发

每个 joblib worker 复制一份 case 数据 + 求解器状态，并发越多内存越大。

```yaml
output:
  parallel:
    n_jobs: 4              # 16 核机器跑大 case 时砍到 4-8
    batch_size: 1          # 减少在途数据
```

## 第四档：禁 BLAS 多线程嵌套

joblib worker × OpenBLAS 多线程 = O(n²) 资源消耗。用环境变量限制：

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

每个仿真单线程跑，但你 worker 多 → 总 CPU 用满，**总内存却小很多**。

## 第五档：分段写盘

非常长的 batch（10 000+ 样本）一次跑完风险大——拆成 100 样本一档：

```python
from pylectra.run import run
import os

base_seed = 42
chunk_size = 100
total = 10000

for offset in range(0, total, chunk_size):
    out_dir = f"./batch_chunks/chunk_{offset:06d}"
    if os.path.exists(out_dir):
        continue            # 跳过已完成
    run("examples/batch_case39.yaml",
        scenarios={"count": chunk_size, "seed": base_seed + offset},
        output={"directory": out_dir})
```

之后用 pandas 把所有 metadata 拼回去：

```python
import pandas as pd, glob
metas = pd.concat([pd.read_parquet(f) for f in glob.glob("./batch_chunks/*/metadata.parquet")])
metas["sample_id"] = metas.index    # 重新编号避免冲突
```

## 第六档：删除中间状态

如果你的 Python 脚本里**不释放 SimulationResult**，N 个结果叠在内存里：

```python
results = []                         # ✗ 越加越多
for cfg in configs:
    out = run(cfg, plot=False)
    results.append(out.result.max_angle_deviation_deg)   # 只留标量

# 或者
del out                              # 显式 del
import gc
gc.collect()                         # 强制回收
```

## 第七档：换更小算例

case2000+ 的内存瓶颈通常是**完整时序**——每个 sample H5 几百 MB。如果你只关心标量指标（最大角偏差、CCT），完全可以**只存 metadata**：

```yaml
output:
  format: hdf5
  keep_failed: false
  # 自定义只存 metadata（要小改 BatchRunner，未来版本会原生支持）
```

当前版本暂不支持"丢弃 H5 只留 parquet"——临时方案：跑完后 `rm samples/*.h5`。

## 第八档：换 case 表示

如果你做大量小信号扫描（`skip_integration: true`），其实**只需要 case + 模型参数 + 平衡点**——不需要时序。每个样本的 metadata + eigenvalues 几 KB 而已。

```yaml
mode: batch
skip_integration: true
small_signal: {kind: finite_difference}
output:
  format: npz             # 比 hdf5 简单
  metadata: parquet
```

## 内存监控

```bash
# Linux / macOS
htop                       # 实时；F10 退出

# Windows
tasklist | findstr python

# 程序里实时打印
import psutil, os
proc = psutil.Process(os.getpid())
print(f"RSS = {proc.memory_info().rss / 1024**3:.2f} GB")
```

## 排错

### "MemoryError" / Killed by OS

排查顺序：

1. 看 `n_jobs` 是不是过大 → 砍半
2. case 多大 → `pylectra info` 看 `total memory` vs case 大小
3. dense_n 是否过大（torch 后端） → 调到 50
4. 是否在脚本里堆积了 results 列表
5. 终极：分段跑 + 间隙 `del` + `gc.collect()`

### swap 暴增

OS 用上了硬盘虚拟内存——速度会暴跌。**立刻**砍 n_jobs，否则 batch 时间从 10 分钟变 10 小时不夸张。

## 接下来读什么

- [GPU 加速教程](../tutorials/06-gpu-acceleration.md) — chunk_seconds 完整文档
- [并行 batch 优化](parallel-batch.md) — n_jobs / BLAS 线程
- [常见问题 FAQ](../faq.md) — 内存相关问题汇总
