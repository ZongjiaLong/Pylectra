# 什么是 Python 包？

_初学者_

> 本页面给从 MATLAB / C / Fortran 转过来的电力工程师看。如果你已经熟悉 `import numpy as np`，可以直接跳到本页底部的"接下来读什么"。

## 一句话定义

**包**（package）就是一个**已经写好的、放在网上、别人可以用一条命令装到自己电脑上**的 Python 代码集合。

电力工程师每天在用的"工具箱"概念，在 Python 里就叫"包"：

| MATLAB 里的概念 | Python 里的对应物 |
|---|---|
| Toolbox（如 Power System Toolbox） | Package（如 `pylectra`、`pandapower`） |
| `addpath('mytoolbox/')` | `import mytoolbox`（前提是装好了） |
| 函数 `myfunc.m` | 函数 `myfunc()`，写在 `.py` 文件里 |
| `which myfunc` | `print(myfunc.__module__)` |

## 怎么"装"一个包

Python 的官方包管理器叫 **pip**。装一个包的命令：

```bash
pip install pylectra
```

这条命令做了三件事：

1. 上 [PyPI](https://pypi.org)（Python 官方包仓库，类似 MATLAB 的 File Exchange）下载这个包
2. 解析它声明的依赖（比如 `pylectra` 依赖 `numpy`、`scipy`、`pandas`），递归把这些依赖也装好
3. 放到当前 Python 的 **site-packages** 目录，使任何 Python 脚本里 `import pylectra` 都能找到它

> ⚠️ **国内网络访问 PyPI 慢？** 用清华镜像：
> ```bash
> pip install pylectra -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

## `import` 是什么

```python
import numpy as np            # 把 numpy 整个包导入，别名 np
from pylectra.run import run  # 只导入 pylectra.run 子模块里的 run 函数
```

`import` 等价于 MATLAB 的 `addpath` + 加载，但更精细：

- `import X`：把整个包加载到内存，访问时写 `X.foo()`
- `from X import foo`：只把 `foo` 拿出来，可以直接 `foo()`
- `import X as Y`：换个短名（社区惯例 `numpy → np`、`pandas → pd`）

如果你看到报错：

```
ModuleNotFoundError: No module named 'pylectra'
```

意思是"我要的这个包在当前 Python 环境里没装"。99% 的情况是：

- 还没运行 `pip install pylectra`
- 或者 `pip` 装到了别的 Python 里（不同 Python 版本各有自己的 site-packages）

后者就需要看下一篇 [什么是虚拟环境](what-is-virtual-env.md)。

## 一个包长什么样

打开 `pylectra` 在你磁盘上的安装位置，会看到：

```
pylectra/
├── __init__.py          # 包的入口；import pylectra 就是执行这个
├── run.py               # 一个子模块（里面是 run() 函数）
├── registry.py
├── models/
│   ├── __init__.py      # 子包也需要 __init__.py
│   └── generators/
│       ├── __init__.py
│       └── two_axis.py  # 一个发电机模型
└── ...
```

**每个 `__init__.py` 在告诉 Python：这个文件夹是个（子）包，可以被 import。**
里面通常会写一些"启动逻辑"，比如：

```python
# pylectra/__init__.py
from . import _legacy           # 先初始化 vendored legacy
from . import registry          # 再加载注册表
from .run import run            # 暴露 run 函数到顶层
__version__ = "0.1.0"
```

这样用户写 `from pylectra import run` 就能直接拿到 `run` 函数。

## 第三方 vs 标准库

Python 自带一批**标准库**，无需 `pip install` 就能用：

```python
import os         # 文件系统
import math       # 基础数学
import json       # JSON 读写
import pathlib    # 路径处理（推荐用法）
```

需要额外装的叫**第三方包**：`numpy`、`scipy`、`pandas`、`matplotlib`、`pylectra` 都是。

## 常见疑问

### Q：和 MATLAB Toolbox 比，体积是不是大很多？

不大。一个 Python 包通常几 MB 到几十 MB（除了 `torch` 这种带 GPU 算子的，会到 200 MB 以上）。装包时 pip 会把所有依赖一次性下载，所以第一次装 `pylectra` 可能花 1–3 分钟。

### Q：怎么知道我装了哪些包？

```bash
pip list                        # 列出当前 Python 环境装的所有包
pip show pylectra              # 看 pylectra 的版本、安装位置、依赖
```

### Q：装错了怎么卸载？

```bash
pip uninstall pylectra
```

## 接下来读什么

- [什么是虚拟环境](what-is-virtual-env.md) — 不要把所有包堆到系统 Python，每个项目用一个隔离环境
