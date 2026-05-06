# 在 Jupyter 中使用 pylectra

_中级_

**前置阅读：** [单次确定性仿真](../tutorials/01-single-run.md)、[可视化教程](../tutorials/04-visualization.md)

Jupyter Notebook（或 JupyterLab）特别适合 pylectra 的**交互式探索**——改一个参数、跑一次、马上看图。

## 安装 + 启动

环境里装 jupyterlab：

```bash
conda activate pylectra-env
conda install -c conda-forge jupyterlab        # 或 pip install jupyterlab
```

启动：

```bash
jupyter lab
```

浏览器自动打开 `http://localhost:8888`。新建一个 Notebook（右上角 +），选 `Python 3 (ipykernel)`。

> 公司 / 校园网络打不开浏览器？复制终端里 `http://localhost:8888/?token=xxx` 那一行手动粘到浏览器。

## 第一个 cell：导入 + 跑

```python
%matplotlib inline                  # 让 matplotlib 图显示在 cell 下面

from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
render("rotor_angles", out.result, gen_indices=[0, 1, 2, 3])
```

按 `Shift+Enter` 跑——图直接出现在下方。

## 配方 1：调参实验循环

```python
# Cell 1 - 一次性导入
from pylectra.run import run
from pylectra.plotting import render
import matplotlib.pyplot as plt

# Cell 2 - 改这里然后 Shift+Enter
fault_duration = 0.10              # 改这一行
out = run("examples/single_case39.yaml",
          fault={"kind": "bus_fault",
                 "params": {"bus": 16, "t_fault": 0.2,
                            "duration": fault_duration}},
          plot=False, verbose=0)
print(f"max angle dev = {out.result.max_angle_deviation_deg:.2f}°")
render("rotor_angles", out.result)
plt.show()
```

每次改 Cell 2 第一行的 `fault_duration` 重跑——交互体验比 CLI 快得多。

## 配方 2：参数扫描 + 内联表格

```python
import pandas as pd
from pylectra.run import run

records = []
for d in [0.02, 0.05, 0.08, 0.12, 0.16]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": d}},
              plot=False, verbose=0)
    records.append({"duration": d,
                    "max_dev": out.result.max_angle_deviation_deg,
                    "pf_ok":   out.result.pf_success})

pd.DataFrame(records).style.format({"max_dev": "{:.1f}°"})
```

Jupyter 自动把 `pd.DataFrame.style` 渲染成漂亮的 HTML 表格。

## 配方 3：交互滑块

用 `ipywidgets`：

```bash
conda install -c conda-forge ipywidgets
```

```python
import ipywidgets as widgets
from IPython.display import display
from pylectra.run import run
from pylectra.plotting import render
import matplotlib.pyplot as plt

def show_run(bus=16, duration=0.05):
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              plot=False, verbose=0)
    fig = render("rotor_angles", out.result, gen_indices="all")
    plt.show()
    print(f"max dev = {out.result.max_angle_deviation_deg:.2f}°")

widgets.interact(show_run,
                 bus=widgets.IntSlider(min=1, max=39, step=1, value=16),
                 duration=widgets.FloatSlider(min=0.01, max=0.3, step=0.01,
                                              value=0.05))
```

拖滑块直接看仿真结果——最直观的"看谁的故障母线最危险"工具。

## 配方 4：保存 Notebook 状态 + 缓存仿真

`pickle` 持久化中间结果：

```python
import pickle, os

cache = "out_cached.pkl"
if os.path.exists(cache):
    with open(cache, "rb") as f:
        out = pickle.load(f)
    print("loaded cached")
else:
    out = run("examples/batch_case39.yaml")     # 长仿真
    with open(cache, "wb") as f:
        pickle.dump(out, f)
    print("ran fresh")
```

`SimulationResult` 是可 pickle 的（除非附带 `pd.DataFrame` 之外的非可序列化字段）。

## 配方 5：%timeit 性能比较

```python
%timeit run("examples/single_case39.yaml", \
            solver={"kind": "modified_euler"}, plot=False, verbose=0)
# 1 loop, best of 5: 9.4 s per loop

%timeit run("examples/single_case39.yaml", \
            solver={"kind": "scipy_dop853"}, plot=False, verbose=0)
# 1 loop, best of 5: 5.1 s per loop
```

## 处理大输出

batch 模式返回的 `BatchResult` 很重，一旦 print 到 cell 输出会卡住浏览器。**只 print 关键标量**：

```python
out = run("examples/batch_case39.yaml")
print(f"accepted: {out.result.n_accepted}/{out.result.n_total}")
# 不要直接 print(out)！
```

要看每个样本的细节，读 metadata.parquet：

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")
meta.head()
```

## 服务器上的 Jupyter

如果你在远程服务器上跑 Jupyter，本地浏览器访问需要 SSH 隧道：

```bash
# 本地终端
ssh -L 8888:localhost:8888 user@server

# 服务器上
jupyter lab --no-browser --port 8888

# 本地浏览器打开 http://localhost:8888
```

## 常见疑问

### Q：图不显示

确认第一个 cell 运行了 `%matplotlib inline`。某些场景需要 `%matplotlib widget`（更现代，可缩放）：

```bash
conda install -c conda-forge ipympl
```

```python
%matplotlib widget
```

### Q：`No module named 'pylectra'`

Jupyter 用的不是你激活的 conda 环境。确认：

```python
import sys
print(sys.executable)
# 应该是 .../envs/pylectra-env/python.exe
```

如果不是——把 conda 环境注册成 Jupyter kernel：

```bash
conda activate pylectra-env
pip install ipykernel
python -m ipykernel install --user --name pylectra-env --display-name "Python (pylectra-env)"
```

刷新 Jupyter，新建 Notebook 时选 `Python (pylectra-env)`。

### Q：matplotlib 字体乱码（中文）

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

放在 Notebook 最上面那个 cell。

## 接下来读什么

- [可视化教程](../tutorials/04-visualization.md) — 把 Notebook 里画的图存为 PDF 投稿
- [参数扫描](parameter-sweep.md) — 自动化你在 Notebook 里手动改的实验
