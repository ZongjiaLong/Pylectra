# 用 torch 做 GPU 加速

_进阶_

**前置阅读：** [单次确定性仿真](01-single-run.md)

pylectra 的 ODE 引擎可选 PyTorch 后端 + `torchdiffeq` 求解器，在有 NVIDIA GPU 的机器上能大幅加速。本页说清：什么时候值得切、怎么切、怎么调内存。

## 什么时候值得切到 torch？

| 情景 | scipy 后端 | torch CPU | torch CUDA |
|---|---|---|---|
| case39 单次仿真 | ~5 s | ~3 s | ~1 s |
| case118 单次仿真 | ~30 s | ~20 s | ~3 s |
| case2000+ 单次仿真 | ~10 min | ~6 min | ~30 s |
| 1000 样本 batch（case39） | ~1 h | ~40 min | ~10 min（且省功耗） |

> 估算来自 case39 实测 + 大网络外推。结论：**case 越大、batch 越多，CUDA 优势越显著**。

如果你的研究只跑几次 case39，**留在 scipy 即可**——torch 后端的启动开销（CUDA context ~1 s）会吃掉短跑的优势。

## 安装 torch

不带 GPU：

```bash
pip install torch torchdiffeq                          # 默认装 CUDA 版（~2 GB）
# 或者只要 CPU 版（~200 MB）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install torchdiffeq
```

带 NVIDIA GPU + CUDA 12.x（典型）：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install torchdiffeq
```

> **不知道 CUDA 版本？** 命令行 `nvidia-smi` 看右上角的 "CUDA Version"。如果显示 12.1 用 cu121 通道，11.8 用 cu118 通道。

验证：

```python
import torch
print("torch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("device count:",  torch.cuda.device_count())
```

如果 `CUDA available: False` 但你确实有 GPU——pip 装到了 CPU 版。卸载重装 CUDA 版：

```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## YAML 切换求解器

```yaml
solver:
  kind: torch_dopri5            # 或 torch_dopri8 / torch_rk4 / torch_euler
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
    chunk_seconds: 0.5          # OOM 缓解（见下文）
    torch_dtype: float64        # cuda 默认 float64；mps 必须 float32
    device: auto                # auto → cuda → mps → cpu
```

四个 torch 求解器：

| 名字 | 算法 | 自适应 | 推荐 |
|---|---|---|---|
| `torch_dopri5` | Dormand-Prince 5(4) | 是 | **默认推荐**，与 scipy_rk45 同精度 |
| `torch_dopri8` | Dormand-Prince 8(7) | 是 | 高精度，与 scipy_dop853 对应 |
| `torch_rk4` | 经典 RK4 | 否 | 固定步长，最简单 |
| `torch_euler` | 欧拉 | 否 | 几乎不用，做对照 |

## device 自动选

```yaml
solver:
  options:
    device: auto       # 默认
```

`auto` 会按优先级查：

```
1. CUDA 可用 → 用 cuda（GPU 全速）
2. Apple M1/M2/M3 + float32 → 用 mps
3. 其他 → cpu
```

强制指定：

```yaml
device: cuda           # 没 GPU 时报错
device: cpu            # 即使有 GPU 也用 CPU
```

## 内存爆炸怎么办 {#oom}

`torchdiffeq.odeint` 跑长仿真容易 OOM：单次调用内部保留 RK k1..k6 中间张量，T·n 增长。
**对策：**`chunk_seconds` 把每个 leg 切成小窗口，每窗口结束 `tensor.detach()`。

```yaml
solver:
  kind: torch_dopri5
  options:
    chunk_seconds: 0.5         # 每 0.5 秒切一个窗口
```

| `chunk_seconds` | 内存占用 | 速度 |
|---|---|---|
| `null`（默认） | O(整个 leg × 状态维度) | 最快 |
| `1.0` | 一半 | 慢 ~5% |
| `0.5` | 1/4 | 慢 ~10% |
| `0.1` | 1/40 | 慢 ~30% |

**OOM 救急流程**：

1. 先试 `chunk_seconds: 0.5`
2. 不够 → `0.2`
3. 还不够 → 同时降 `dense_n`（每段输出点数）和 `rtol`
4. 还不够 → 切回 CPU（`device: cpu`）

数学等价性已由 `tests/integration/test_torch_backend.py::test_chunking_is_numerically_equivalent` 守护：chunked vs 非 chunked 在 rtol=1e-4 下一致。

## dtype 选择

```yaml
solver:
  options:
    torch_dtype: float64     # 默认；高精度
    # torch_dtype: float32   # 快 1.5–2×、省一半显存，精度低 ~5 位
```

电力系统转子角变化 ~10⁻³–10⁰，float32 通常够。**做发表实验或数值对比时还是用 float64**。

> Apple MPS 只支持 float32。device=auto 时如果选到 mps，pylectra 会自动报错并提示你换 cpu 或换 dtype。

## 用 GPU 跑 batch

batch 模式 + torch + joblib 一起用——但**不要**把 worker 数设成 GPU 数 × 大量：每个 worker 都会创建 CUDA context（~1 GB 显存），多了直接 OOM。

```yaml
output:
  parallel:
    n_jobs: 1                  # GPU 全速跑单进程已经够快
    backend: loky
```

如果有多 GPU：

```python
# 在 worker 里指定 GPU id，需要程序化分发
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # 或 "1"
```

更复杂的多 GPU 方案不在 pylectra 的核心 scope 里——可以包一层自己的脚本。

## 验证 GPU 真的在跑

```bash
# 跑仿真期间另开一个终端
nvidia-smi
```

看到 `python` 进程 + 显存占用 + GPU-Util > 0%，就是真的在用 GPU。

或者程序内：

```python
import torch
print("device used:", out.result.metadata.get("torch_device"))
```

## scipy 与 torch 数值差异

它们**不会**逐位一致，因为：

- 不同算法（dop853 是 8 阶；dopri5 是 5 阶）
- 不同步长控制器初始值
- float64 累加顺序不同

但都是同一 ODE 的合理解。pylectra 守护 `< 1% L2 误差`：

```
torch_dopri5 vs scipy_dop853 在 case39 + bus 16 fault：
  Angles  L2 = 0.3%
  Speeds  L2 = 0.1%
  Voltages L2 = 3% （fault 不连续处偏大）
```

科学投稿用 scipy 的结果更稳；要做大规模数据集再切 torch。

## 常见疑问

### Q：明明装了 torch 也有 GPU，pylectra 还是说 device=cpu？

可能：

- `pip install torch` 装到了 CPU 版（PyPI 默认）。`pip uninstall torch` 后改用 CUDA 通道
- conda 环境里 torch 跟 CUDA toolkit 不匹配（conda 版 torch 自带 CUDA runtime；pip 版需要系统装 CUDA）
- 显式指定了 `device: cpu`

### Q：torch 启动巨慢

第一次 `import torch` 在 GPU 机器上要初始化 CUDA context（~1–2 秒）。**之后调用都很快**。如果还是每次都慢，可能是 GPU 在用 `nvidia-persistenced` 时进了节能模式——查看 `nvidia-smi -pm 1`。

### Q：装不上 torchdiffeq？

```bash
# pip 通道
pip install torchdiffeq

# 国内
pip install torchdiffeq -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q：在 CPU 上跑 torch 比 scipy 快？

是。原因是 `torchdiffeq` 用 PyTorch 的 BLAS 后端（OpenBLAS / MKL），并且整个 RHS 是 vectorized tensor 操作，比 scipy 的 Python 解析层快。**不需要 GPU 也能赚到这部分**。

## 接下来读什么

- [为长仿真调内存](../how-to/tune-memory.md) — chunk_seconds 之外的优化技巧
- [pylectra.run.run() API](../reference/api/run.md) — 完整 solver 选项参考
