# 用多核加速批量仿真

_中级_

**前置阅读：** [批量数据集生成](../tutorials/02-batch-generation.md)

## 一行 YAML 配置

```yaml
output:
  parallel:
    n_jobs: -1                # -1 = 全部 CPU 核
    backend: loky             # loky | multiprocessing | threading
    batch_size: 4             # 每 batch 任务数（loky 默认 auto）
```

## n_jobs 怎么选

| 值 | 含义 |
|---|---|
| `1` | 串行（开发调试时用） |
| `-1` | 全部逻辑 CPU |
| `auto` | pylectra 推荐值：`min(cpu_count - 1, 16)` |
| `4` | 显式指定 4 个 worker |

**经验**：

- 16 核以下机器，`-1` 通常最快
- 16 核以上，`auto`（上限 16）避免边际收益递减
- 4 GB / 8 GB 小内存机器：每个 worker 占 ~500 MB；16 核同时跑会爆内存。**显式设 `n_jobs: 4` 或 `8`** 

```python
from pylectra.hardware import recommend_n_jobs, summary
print(summary())              # 看自己机器的硬件
print(recommend_n_jobs())     # 看推荐值
```

## backend 选哪个

### `loky`（默认推荐）

joblib 的进程池实现，**Windows / macOS / Linux 都能用**。每个 worker 独立 Python 进程，绕开 GIL，CPU-bound 任务（pylectra 是这类）最快。

### `multiprocessing`

Python 标准库 multiprocessing。功能与 loky 类似，但 fork 实现细节有差异。一般**别用**——`loky` 修了很多 fork 在 Windows / macOS 下的坑。

### `threading`

线程池。受 GIL 限制，**对 pylectra 这种 CPU-bound 任务没有加速**——即使设 `n_jobs=8` 也只用 1 个 CPU。
**例外**：如果你的 worker 调用了**释放 GIL 的 C 扩展**（numpy 大矩阵 BLAS、scipy 求解器、torch），threading 反而能并行。pylectra 的 ODE 主路径主要是 Python，**不要用 threading**。

## Windows 非 ASCII 用户名问题

Windows 中文用户名（如 `龙宗加`）+ joblib `loky` 后端 = `UnicodeEncodeError`。
`multiprocessing.resource_tracker` 用 ASCII 编码 IPC 消息，遇到 `C:\Users\龙宗加\AppData\Local\Temp\...` 会炸。

**解决**：改 `JOBLIB_TEMP_FOLDER` 到一个全 ASCII 路径：

```bash
# Windows cmd
set JOBLIB_TEMP_FOLDER=D:\joblib_tmp
python -m pylectra run examples/batch_case39.yaml

# Windows PowerShell
$env:JOBLIB_TEMP_FOLDER = "D:\joblib_tmp"

# Linux / macOS（一般不会遇到这问题）
export JOBLIB_TEMP_FOLDER=/tmp/joblib_tmp
```

或在 Python 里：

```python
import os
os.environ["JOBLIB_TEMP_FOLDER"] = r"D:\joblib_tmp"
from pylectra.run import run
run("examples/batch_case39.yaml")
```

## batch_size 调优

`batch_size` 决定每次发给 worker 的**任务块**大小。

- 默认 / `"auto"`：joblib 自适应（通常合理）
- 太小（如 `1`）：调度开销大、worker 闲置
- 太大（如 `100`）：负载不均（最慢的那个 worker 拖整体）

如果你跑很大批量（10 000+ 样本），手动设 `batch_size: 8` 或 `16` 通常比 auto 快 5–10%。

## n_jobs vs 内存

每个 worker：

- 独立 Python 解释器（~50 MB）
- 复制 numpy 大数组（如 case 数据 ~1 MB）
- joblib 内部 buffers（~10 MB）
- 仿真本身的状态（case 越大占越多，case39 ~30 MB）

**case39，n_jobs=8 → 总占 ~250 MB**。
**case2000+，n_jobs=8 → 可能爆 8 GB**。

OOM 救急：

```yaml
output:
  parallel:
    n_jobs: 4         # 砍一半
    backend: loky
    batch_size: 1     # 减少在途数据
```

## 验证并行真在加速

跑 5 样本：

```bash
# 串行
time python -m pylectra run examples/batch_case39.yaml \
  -O 'output={"parallel": {"n_jobs": 1}}'

# 并行
time python -m pylectra run examples/batch_case39.yaml \
  -O 'output={"parallel": {"n_jobs": -1}}'
```

8 核机器上典型差距：串行 ~50 s vs 并行 ~10 s（约 5× 加速；理想 8× 因 joblib 启动 + 写盘 IO）。

## 在共享集群上

学校 / 公司 HPC 集群上，**每个 worker 不一定独占一个物理核**——其他用户也在抢。

- **SLURM / PBS** 任务申请 `--cpus-per-task=8` 后，joblib `n_jobs=-1` 看到的是 8 个（不是节点全部）
- 集群禁止 fork 时改 `backend: threading` —— **放弃并行加速**，但能避免被 admin 杀掉
- `dask` 比 joblib 更适合分布式集群——pylectra 不内建支持，但因为 `SingleRunner` 是 picklable，**外面套一层 dask** 不难

## 跑大批量 + 持久化重要 worker 信息

```python
import joblib
joblib.parallel_config(backend="loky",
                       n_jobs=8,
                       temp_folder="/scratch/joblib")
# 之后所有 batch 调用继承这个配置
```

## 常见疑问

### Q：为什么 4 核机 n_jobs=4 只比 n_jobs=2 快 30%？

**单个仿真本身已经吃了 60% CPU**（numpy / scipy 内部 BLAS 多线程）。
关掉 BLAS 的内部多线程能让并行更线性：

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

### Q：进程一直在 "Joblib starting" 卡住

第一次启动 loky worker 会 import 整个 pylectra（含所有插件 + numpy / scipy）——10–30 秒正常。
**只有第一次慢**，后续任务复用同一组 worker。

如果 5 分钟还卡住，可能是某个插件 import 时报错——加 `-O 'verbose=2'` 看详细日志。

### Q：能跨机器分布吗？

joblib 不行——本机限定。要跨机器：

- **dask.distributed**：把 SingleRunner 任务塞进 dask client.submit
- **Ray**：类似 dask
- **Slurm 数组任务**：每个 array task 跑一个独立 batch，最后合并 metadata

## 接下来读什么

- [为长仿真调内存](tune-memory.md) — chunk_seconds + 共享 BLAS 等
- [batch 教程](../tutorials/02-batch-generation.md) — 复习配置
