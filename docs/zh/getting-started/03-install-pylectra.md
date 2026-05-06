# 安装 Pylectra

_初学者_

**前置阅读：** [安装 Python](01-install-python.md)、[安装 Git](02-install-git.md)、[什么是虚拟环境](../concepts/what-is-virtual-env.md)

## 选哪条路

| 你的需求 | 推荐路径 |
|---|---|
| 只想跑 pylectra，不改源码 | **路径 1：从 PyPI 装** |
| 想跟最新代码 / 看实现 / 改 bug | **路径 2：源码安装（开发模式）** |
| 不想装 git，又想看源码 | **路径 3：下载 zip** |

三条路都需要先按 [安装 Python](01-install-python.md) 装好 Miniconda。

## 路径 1：从 PyPI 装

```bash
# 1. 创建一个独立环境（避免污染系统 Python）
conda create -n pylectra-env python=3.11 -y
conda activate pylectra-env

# 2. 装 pylectra（核心）
pip install pylectra

# 3. 推荐附加安装 pandapower 后端
pip install pylectra[pandapower]
```

> 国内网络？先 [配置清华 pip 镜像](01-install-python.md#mirrors)，否则可能下载超时。

验证：

```bash
python -c "import pylectra; print(pylectra.__version__)"
```

应该输出版本号，比如 `0.1.0`。

## 路径 2：源码安装（开发模式）

适合想阅读源码、做修改、提 PR 的用户。

```bash
# 1. 拿源码
git clone https://github.com/ZongjiaLong/Pylectra.git
cd pylectra

# 2. 创建独立环境
conda create -n pylectra-dev python=3.11 -y
conda activate pylectra-dev

# 3. 编辑模式安装（pip install -e .）
pip install -e .

# 4. 也可以一起装 dev / docs / torch 工具链
pip install -e ".[dev]"          # 含 pytest / ruff
pip install -e ".[docs]"         # 含 mkdocs 文档构建
pip install -e ".[torch]"        # 含 torchdiffeq GPU 求解器
pip install -e ".[all]"          # 一键全装（需要约 2 GB 硬盘）
```

`-e .`（editable）的妙处：你改源码后**不用重装**，下次 `import pylectra` 就读到改动。

## 路径 3：下载 zip（不用 git）

1. 进入 [pylectra Releases 页面](https://github.com/ZongjiaLong/Pylectra/releases)
2. 找最新版本，点 **Source code (zip)** 下载
3. 解压到任意目录（**避开含中文或空格的路径**，如不要放在 "C:\我的项目\"）
4. 命令行进入解压后目录：

```bash
cd 解压后的路径\pylectra-0.1.0
conda create -n pylectra-env python=3.11 -y
conda activate pylectra-env
pip install -e .
```

## 验证安装

不论用哪条路，最后跑这两条命令验证：

```bash
# 1. 包能 import
python -c "import pylectra; print('OK', pylectra.__version__)"

# 2. CLI 能跑
python -m pylectra info
```

第二条命令会列出所有内置插件——12 个类别、几十个名字。看到这个输出说明 **pylectra 完全装好了**。

## 装额外科学计算包

后续教程会用到：

```bash
# 推荐用 conda 装这些（带 C/Fortran 编译，conda 装更稳）
conda install -c conda-forge numpy scipy matplotlib pandas h5py pyarrow

# pandapower 后端（路径 1 已经包含；路径 2/3 单独装）
conda install -c conda-forge pandapower

# Jupyter Notebook（可选，做交互式分析很方便）
conda install -c conda-forge jupyterlab
```

## 跑一个最小 smoke test

```bash
python -m pylectra run examples/single_case39.yaml
```

> 路径 1 的用户可能没有 `examples/` 目录。要么改用路径 2/3 拿到源码，要么从 [GitHub examples 文件夹](https://github.com/ZongjiaLong/Pylectra/tree/main/examples) 单独下载几个 yaml。

预期看到一段日志（约 30 秒），最后会有：

```
[single] simulation completed in X.XX seconds
```

恭喜，你已经跑通了第一次仿真。详细解读在 [你的第一次仿真](04-first-simulation.md)。

## 常见问题

### Q：`conda create` 报 SSL 错误

通常是镜像源问题或代理问题。先试：

```bash
conda config --remove-key channels         # 重置为默认源
conda create -n pylectra-env python=3.11   # 重试
```

如果还不行，参考 [安装 Python 第五步](01-install-python.md#mirrors) 配镜像。

### Q：`pip install pylectra` 卡在 "Building wheel for h5py..."

`h5py` 需要 HDF5 C 库。**改用 conda 装**：

```bash
conda install -c conda-forge h5py
pip install pylectra
```

### Q：`pandapower` 装不上

```bash
conda install -c conda-forge pandapower
```

走 conda 通常不会出问题。

### Q：怎么升级 pylectra？

```bash
# 路径 1（PyPI）
pip install --upgrade pylectra

# 路径 2（源码）
cd pylectra
git pull            # 拉最新代码
pip install -e .    # 不需要每次都跑，除非依赖变了
```

### Q：怎么彻底卸载？

```bash
conda activate pylectra-env
pip uninstall pylectra        # 卸包

conda deactivate
conda env remove -n pylectra-env   # 删整个环境
```

## 接下来读什么

- [你的第一次仿真](04-first-simulation.md) — 跑通第一个 case39 fault 仿真，理解每个 YAML 字段
