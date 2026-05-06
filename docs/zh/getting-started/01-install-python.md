# 安装 Python

_初学者_

**前置阅读：** [什么是 Python 包](../concepts/what-is-python-package.md)

> 本页教你从零装好 Python。已经会 `python --version` 的人可以跳到 [安装 Git](02-install-git.md)。
> 我们**强烈推荐用 Miniconda**，而不是直接装 Python.org 的安装包——因为它一站式解决了 Python + 包管理 + 虚拟环境 + C/Fortran 编译器（电力工程常用的 `scipy`、`pandapower` 都需要）。

## 第一步：判断当前是否已装

打开命令行：

- **Windows**：按 `Win + R` → 输入 `cmd` → 回车
- **macOS**：`Cmd + 空格` → 输入 `Terminal` → 回车
- **Linux**：`Ctrl + Alt + T`

输入：

```bash
python --version
```

如果回复 `Python 3.10.x` 或更高，**说明已经装好了**，跳过本页。
如果是 2.7.x、3.8.x 之类的旧版本，建议跟下面流程装个 Miniconda 用新版 Python，老的留着不动也无碍。
如果显示 "命令未找到 / not recognized"，那就要装。

## 第二步：下载 Miniconda

进入：[https://docs.conda.io/projects/miniconda/en/latest/](https://docs.conda.io/projects/miniconda/en/latest/)

> 国内访问慢？用清华镜像：[https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/](https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/)
> 选最新的 `Miniconda3-latest-Windows-x86_64.exe`（Windows 用户）或对应你系统的版本。

按系统选下载：

| 操作系统 | 下载文件 |
|---|---|
| Windows 10/11 | `Miniconda3-latest-Windows-x86_64.exe` |
| macOS（Intel 芯片） | `Miniconda3-latest-MacOSX-x86_64.pkg` |
| macOS（M1/M2/M3 芯片） | `Miniconda3-latest-MacOSX-arm64.pkg` |
| Linux | `Miniconda3-latest-Linux-x86_64.sh` |

> 不知道自己 Mac 是哪种芯片？点苹果菜单 → "关于本机"，看处理器一栏。Apple M1/M2/M3 → 选 arm64；Intel Core → 选 x86_64。

## 第三步：安装

### Windows

1. 双击下载的 `.exe` 文件
2. 一路 **Next**
3. **重要**：到 "Advanced Installation Options" 页面时
   - ✅ 勾上 **"Add Miniconda3 to my PATH environment variable"**（虽然安装器会标红警告，**对我们的场景请勾上**——能让你在任何命令行里直接用 `python` 和 `conda`）
   - ✅ 勾上 **"Register Miniconda3 as my default Python"**
4. 点 Install，等几分钟，完成

### macOS

1. 双击 `.pkg` 文件
2. 跟提示一路 Continue → Install
3. 安装完打开 Terminal，输入 `conda --version` 验证

### Linux

打开终端，进入下载目录：

```bash
bash Miniconda3-latest-Linux-x86_64.sh
```

按提示：

- 阅读 license → 输 `yes`
- 选安装路径（默认 `~/miniconda3` 即可）→ 回车
- 询问 "Do you wish to update your shell profile..." → 输 `yes`

安装完关闭终端、重新打开。

## 第四步：验证安装

新开一个命令行窗口（**必须新开**，旧窗口里 PATH 还没更新），输入：

```bash
conda --version
python --version
```

应该看到类似：

```
conda 24.3.0
Python 3.12.x
```

如果 `conda --version` 报"命令未找到"：

- **Windows**：可能是 PATH 没加。打开"开始菜单 → Anaconda Prompt (miniconda3)"，从这个特殊命令行启动 conda 即可。或者重装时勾上"Add to PATH"。
- **macOS / Linux**：`source ~/.bashrc`（或 `~/.zshrc`），再试。

## 第五步：配置国内镜像（可选但强烈推荐） {#mirrors}

国内默认从国外服务器装包，慢且容易超时。改用清华镜像：

```bash
# 配置 conda 用清华镜像
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
conda config --set show_channel_urls yes

# 配置 pip 用清华镜像（永久生效）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

之后无论是 `conda install xxx` 还是 `pip install xxx`，都自动从国内服务器拉取，速度提升 10–100 倍。

## 常见问题

### Q：装的时候为什么不直接用 Python 官网安装包？

可以用，但你接下来还要：

- 自己装 `pip install` 各种包
- 自己学 `venv` 做环境隔离
- `pandapower` 等带 C 扩展的包可能要装 Visual Studio 编译器

Miniconda 一次性把这些全打包了，**对电力工程师的工作流更友好**。

### Q：Anaconda 和 Miniconda 区别？

- **Anaconda**：3 GB 大全套，预装几百个数据科学包
- **Miniconda**：~100 MB，只装 Python + conda，包按需装

我们推荐 Miniconda——干净、占地小，需要的包用 `conda install` 或 `pip install` 一条命令就能加。

### Q：能不能装在 D 盘？

**Windows 用户强烈建议装在 D 盘**（如 `D:\Miniconda3`），不要装到 `C:\Program Files`——后者路径有空格，部分 Python 包会报错。

### Q：装错了怎么卸载？

- **Windows**：控制面板 → 程序与功能 → Miniconda3 → 卸载
- **macOS / Linux**：直接 `rm -rf ~/miniconda3`，再编辑 `~/.bashrc` / `~/.zshrc` 删掉 `conda init` 那段

## 接下来读什么

- [安装 Git](02-install-git.md) — 装 git，准备从 GitHub 拿 pylectra 源码
