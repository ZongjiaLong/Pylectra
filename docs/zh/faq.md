# 常见问题

_参考资料_

按主题分组，找不到答案？去 [GitHub Issues](https://github.com/ZongjiaLong/Pylectra/issues) 提问。

## 安装

### Q：`pip install pylectra` 卡住或超时

国内访问 PyPI 慢。换清华镜像：

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip install pylectra
```

详见 [安装 Python — 配置国内镜像](getting-started/01-install-python.md#mirrors)。

### Q：`Building wheel for h5py` 卡住

`h5py` 需要 HDF5 C 库。**改用 conda 装**：

```bash
conda install -c conda-forge h5py
pip install pylectra
```

### Q：`pandapower` 装不上

```bash
conda install -c conda-forge pandapower
```

如果还不行，确认 Python 版本 ≥ 3.10。

### Q：装在哪个目录？

**Windows 强烈建议装到 D 盘**（如 `D:\Miniconda3`）—— 不要装到 `C:\Program Files`，路径含空格会让某些 Python 包报错。

### Q：装错了怎么彻底卸载？

```bash
conda activate pylectra-env
pip uninstall pylectra
conda deactivate
conda env remove -n pylectra-env       # 删整个环境
```

## 第一次跑

### Q：`ModuleNotFoundError: No module named 'pylectra'`

99% 是装到了别的 Python：

```bash
which python                           # macOS / Linux
where python                           # Windows
pip -V                                 # 看 pip 装到哪
```

输出里如果包含 `pylectra-env`，说明环境对了。否则 `conda activate pylectra-env` 重新激活。

### Q：`KeyError: 'kind' = 'xxx'`

YAML 里的 `kind` 不在注册表里。两种可能：

1. 拼错了 → `python -m pylectra info` 看正确名字
2. 你写了自定义插件但没被加载 → 确认它在 `pylectra/<category>/` 下、文件名不是 `_` 开头

### Q：`power flow did not converge`

潮流不收敛。试：

- 换求解器：`power_flow: {kind: pandapower}`
- 放宽容忍：`tolerance_mva: 1.0e-6`
- 检查 case 是否合理（极端负荷 / 拓扑不连通）

### Q：仿真画出来转子角飞天

故障太严苛 / 系统不稳定。试：

- 缩短 `fault.params.duration`
- 换 `solver: {kind: scipy_dop853, options: {rtol: 1e-8}}` 排除数值发散
- 检查 `out.result.pf_success` 是不是 False

### Q：第一个仿真没弹画图窗口

- YAML 里 `plot: true` 了吗？
- CLI 加了 `--no-plot`？
- macOS 用户可能要装 `pip install pyqt5`，或用画图命令存文件：
  ```bash
  python -m pylectra plot examples/single_case39.yaml \
    --type rotor_angles --output rotor.pdf
  ```

## Batch 模式

### Q：`UnicodeEncodeError: 'ascii' codec can't encode characters` (Windows)

中文用户名（如 `龙宗加`）+ joblib `loky` 后端的已知问题。设环境变量：

```bash
# Windows cmd
set JOBLIB_TEMP_FOLDER=D:\joblib_tmp
python -m pylectra run examples/batch_case39.yaml

# PowerShell
$env:JOBLIB_TEMP_FOLDER = "D:\joblib_tmp"
```

详见 [并行 batch — Windows 非 ASCII 用户名](how-to/parallel-batch.md)。

### Q：batch 通过率太低

意味着扰动太剧烈、过滤器太严。

- 减小 `scenarios.generators[*].params.sigma_pct`
- 放宽 `voltage_range.vmin / vmax`
- 提高 `angle_stability.max_dev_deg`

### Q：batch 占内存爆了

按顺序排查：

1. `n_jobs` 太大 → 砍半（`n_jobs: 4` 而非 `-1`）
2. `keep_failed: false` 已开？
3. case 太大？看 [调内存 how-to](how-to/tune-memory.md)
4. 终极：分段跑（每 100 个一档）

### Q：batch 跑完成但 metadata.parquet 是空的

检查：

- 没有任何样本通过过滤 → `keep_failed: false` 时不写
- 临时方案：开 `keep_failed: true` 至少看到所有样本的拒绝原因

## 性能

### Q：仿真比 MATLAB 慢

求解器选错了。`modified_euler` 是为兼容老 MATLAB 输出而保留的——**生产推荐 `scipy_dop853`**：

```yaml
solver:
  kind: scipy_dop853
  options: {rtol: 1.0e-6}
```

通常步数减半、墙钟减半。

### Q：torch 在 CPU 上比 scipy 还慢

torch 的 CUDA context 启动 + 第一次仿真 import 开销大。**torch 优势在 GPU**或者**重复多次仿真**（worker 复用）。

case39 单次仿真用 scipy 即可；case500+ 或 batch 1000+ 才考虑 torch。

### Q：怎么知道 GPU 真的在用？

```bash
nvidia-smi                             # 看 GPU 利用率
```

或在 Python：

```python
import torch
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
```

### Q：n_jobs=8 速度只比 n_jobs=2 快 30%

OpenBLAS / MKL 在每个 worker 内部又开了多线程，导致超线程争抢。固定单线程：

```bash
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
python -m pylectra run examples/batch_case39.yaml
```

## CCT 模式

### Q：`CCT 在 [low, high] 之外，请加宽 bracket`

bracket 边界不对：

- `low` 必须稳定（缩短）
- `high` 必须不稳定（增大）

试 `low: 0.001, high: 0.50` 重新跑。

### Q：CCT 收敛但与文献值差异大

文献值通常用特定动力学参数 + 特定求解器。pylectra 的 case39 默认用 `case39dyn` + `modified_euler`，可能与你的参考不同。

- 用同样的求解器 + 同样的容忍度
- 用同样的稳定判据（180° / 90°）
- 用同样的故障类型（bolted vs impedance）

## 小信号

### Q：`stability_margin > 0`，但仿真看起来稳定

平衡点不稳定 ≠ 大扰动响应不稳定。两种可能：

1. 你的 case_dyn 模型参数不对（小信号严苛揭示了 bug）
2. 平衡点附近有缓慢发散模态，仿真 5-10 秒看不出来

试用 `kind: modal` 看最差阻尼模态的频率，再跑长 30 秒仿真验证。

### Q：所有阻尼比都是 NaN

所有特征值都是 0（无振荡）—— 通常是 case 退化（无负荷、无故障）。换个能体现动态的 case。

## 可视化

### Q：中文标签乱码

matplotlib 默认字体没中文。Notebook 第一个 cell 加：

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

### Q：图保存为 PDF 后字体被栅格化

`set_nature_style()` 默认设了 `svg.fonttype = "none"`，PDF 也会嵌入字体。如果还是栅格化，检查：

- `matplotlib >= 3.7`
- 用 `fig.savefig("x.pdf")` 而不是 `plt.savefig`（前者保留 figure 状态）

### Q：CLI `pylectra plot` 报 `unknown plot kind`

`python -m pylectra info --category plot` 看注册名。常见拼错：`rotor-angles` 应为 `rotor_angles`（下划线）。

## Jupyter

### Q：Notebook 里 `import pylectra` 报 ModuleNotFound

Jupyter 用的不是 `pylectra-env`。注册 kernel：

```bash
conda activate pylectra-env
pip install ipykernel
python -m ipykernel install --user --name pylectra-env --display-name "Python (pylectra-env)"
```

刷新 Jupyter，新建 Notebook 时选 `Python (pylectra-env)`。

## 进阶 / 开发

### Q：怎么贡献代码？

见 [CONTRIBUTING.md](https://github.com/ZongjiaLong/Pylectra/blob/main/CONTRIBUTING.md)。简而言之：fork → 写一个新插件文件 → 加测试 → PR。

### Q：API 会破坏向后兼容吗？

0.1.x 系列会保持 YAML schema 与 `pylectra.run.run()` 签名稳定。0.2.0 计划**删除** `pylectra/_legacy/` —— 但**只影响想 import legacy 内部模块**的用户，公共 API 不变。

### Q：能否离线安装？

从有网机器：

```bash
pip download pylectra -d ./pylectra-pkgs
```

打包整个 `pylectra-pkgs/` 拷到目标机：

```bash
pip install --no-index --find-links ./pylectra-pkgs pylectra
```

## 接下来读什么

- [调内存](how-to/tune-memory.md) — 内存相关问题
- [并行 batch](how-to/parallel-batch.md) — 并行性能
- [GitHub Issues](https://github.com/ZongjiaLong/Pylectra/issues) — 提新问题
