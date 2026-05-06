# 什么是虚拟环境？

_初学者_

**前置阅读：** [什么是 Python 包](what-is-python-package.md)

## 为什么需要虚拟环境

假设你电脑上装了一个 Python，所有 `pip install` 都装到这一个 Python 里。
过一段时间会发生这样的事：

- 项目 A 用 `pandas==1.5`
- 项目 B 用 `pandas==2.2`（接口有改动，1.5 的代码会跑不动）
- 系统某个工具脚本依赖 `pandas==1.3`

只用一个 Python，三个需求装不到一起 —— 这就是 **依赖冲突**。
解决方法：**给每个项目建一个独立的"虚拟环境"**，每个环境有自己的包列表，互不干扰。

> 类比：MATLAB 的工作目录 + `userpath` 配置每个项目用不同的工具箱版本。

## 两种主流方案

### 方案 A：conda（推荐给电力工程师）

[Anaconda](https://www.anaconda.com/download) / [Miniconda](https://docs.conda.io/projects/miniconda/) 是科学计算圈最常用的发行版，**自带 Python + 虚拟环境管理 + 编译器工具链**。装一次就够。

电力工程师推荐用 **Miniconda**（轻量，~100 MB）：

```bash
# 创建一个名叫 pylectra-env 的新环境，里面装 Python 3.11
conda create -n pylectra-env python=3.11

# 进入这个环境
conda activate pylectra-env

# 在环境里装 pylectra（这条 pip 只影响当前环境）
pip install pylectra

# 用完离开
conda deactivate
```

进入环境后，命令行提示符会变成 `(pylectra-env) C:\Users\...>`，这表示你**正处于这个独立环境**，所有 `pip` / `python` 命令都只对它生效。

### 方案 B：venv（Python 自带，无需额外安装）

```bash
# 在当前目录建一个名叫 .venv 的环境
python -m venv .venv

# 激活
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux

# 装包
pip install pylectra

# 退出
deactivate
```

`venv` 创建出来的就是一个文件夹（叫 `.venv` 是社区惯例，前面的点表示隐藏目录）。
要"删掉这个环境"，**直接删除这个文件夹**就行。

## 什么时候用哪个？

| 场景 | 推荐 |
|---|---|
| 同时跑多个 Python 版本（3.10 / 3.11 / 3.12） | conda |
| 装 `pandapower`、`scipy` 这种带 C/Fortran 编译的科学包，又怕缺编译器 | conda |
| 公司机器没有管理员权限，但能装个软件 | conda（Miniconda 用户级安装） |
| 已经装好 Python，只想要最轻量的隔离 | venv |

我们文档后续都用 conda 作为示例，因为电力工程师圈最常用。

## 一个常见误区

**没激活环境就 `pip install`** —— 包装到了"系统 Python"或者"上一个激活的环境"，下次激活新环境去 `import` 就报 `ModuleNotFoundError`。

排查方法：

```bash
# 看当前 Python 在哪
where python                     # Windows
which python                     # macOS / Linux

# 看 pip 在装到哪
pip -V
```

输出里如果有你环境的名字（比如 `pylectra-env`），就是对的。

## 常见疑问

### Q：每个项目都建一个环境，硬盘会不会爆？

每个环境**几百 MB**到 1 GB（含 numpy/scipy/matplotlib 等）。一两个项目无所谓；如果你有几十个，可以共用一个"通用科学环境"，只为有冲突的项目单建。

### Q：环境装坏了怎么办？

直接 `conda env remove -n pylectra-env`（或 `rm -rf .venv`）然后重建。**不要修复，不要硬装** —— 重建比修复快。

### Q：我把 conda、pip 混用了，有问题吗？

一般没事，但建议：**conda 装"系统级"二进制包**（`numpy`、`scipy`、`pandapower` 在 conda 里都有），**pip 装纯 Python 的轻量包**（`pylectra` 这种）。先 `conda install`，再 `pip install`。

### Q：我能在一个环境里同时用 Jupyter Notebook 吗？

可以。`conda activate pylectra-env` 后 `pip install jupyterlab`，然后 `jupyter lab` 启动即可。Notebook 默认就用当前激活环境的 Python。

## 接下来读什么

- [安装 Pylectra](../getting-started/03-install-pylectra.md) — 用上面学到的虚拟环境，把 pylectra 装好
