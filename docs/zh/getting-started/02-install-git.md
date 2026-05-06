# 安装 Git

_初学者_

**前置阅读：** [什么是 Git 和 GitHub](../concepts/what-is-git-github.md)

> 不想装 git 也行——可以直接下载源码 zip 或者 `pip install pylectra`。本页给想跟最新代码或将来贡献的人看。

## 第一步：判断是否已装

```bash
git --version
```

回复 `git version 2.x.x` → 已装好，跳过本页。
否则按下面步骤装。

## Windows

### 装法 A：用 Git for Windows（推荐）

1. 进入 [https://git-scm.com/download/win](https://git-scm.com/download/win) 下载安装包
2. 双击运行，选项基本一路 Next，**注意以下几个**：
   - "Select Components"：默认即可
   - **"Adjusting your PATH environment"**：选 **"Git from the command line and also from 3rd-party software"**（默认就是这个，确认即可）
   - "Choosing the SSH executable"：默认 "Use bundled OpenSSH"
   - "Configuring the line ending conversions"：选 **"Checkout as-is, commit Unix-style line endings"**（避免 CRLF/LF 引起的莫名 diff）
   - "Configuring the terminal emulator to use with Git Bash"：默认 MinTTY 即可
   - 其余都默认
3. 安装完会附带一个 **Git Bash**（开始菜单里），那是个 Linux 风格的命令行，用 git 比 cmd 顺手

### 装法 B：用 conda 装（如果你已经装好 Miniconda）

```bash
conda install -c conda-forge git
```

## macOS

最快方式：

```bash
xcode-select --install
```

弹出框点 Install，装完即用。`git --version` 会显示 Apple 自带的版本（通常够用）。

也可以装 Homebrew 后 `brew install git` 拿到最新版。

## Linux

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y git

# CentOS / RHEL / Fedora
sudo dnf install -y git
```

## 第二步：基础配置

每个机器都要做一次（git 把这两个字段记进每条提交里）：

```bash
git config --global user.name "你的名字"
git config --global user.email "you@example.com"
```

**邮箱不会被发出去**，只是写进提交记录。常用学校或公司邮箱即可。

可选但推荐：

```bash
# 用 main 而不是 master 作为新仓库的默认分支
git config --global init.defaultBranch main

# 拉取时自动 rebase 而不是 merge（避免无意义的 merge commit）
git config --global pull.rebase true

# 让中文文件名在终端正常显示（Windows 用户尤其需要）
git config --global core.quotepath false
```

## 第三步：测试一下

随便找个目录：

```bash
git clone https://github.com/ZongjiaLong/Pylectra.git
cd pylectra
git log --oneline | head
```

最后一条命令应该输出最近几次提交的简短信息。

> 国内访问 GitHub 慢/超时？两个对策：
>
> 1. 用 [GitHub 镜像](https://kkgithub.com)，把 URL 里的 `github.com` 换成 `kkgithub.com`：
>    ```bash
>    git clone https://kkgithub.com/ZongjiaLong/Pylectra.git
>    ```
> 2. 或者直接走 Gitee 镜像（如果项目维护方有同步）：
>    ```bash
>    git clone https://gitee.com/ZongjiaLong/Pylectra.git
>    ```

## 配置 SSH key（可选，让以后 push 不用反复输密码）

只有当你想往**自己 fork 的仓库**推送代码时才需要。仅作为 pylectra 用户的话**完全跳过**。

如果你确实需要：

```bash
# 生成密钥（一路回车，密码可以不设）
ssh-keygen -t ed25519 -C "you@example.com"

# 显示公钥（把这段贴到 GitHub → Settings → SSH and GPG keys → New SSH key）
cat ~/.ssh/id_ed25519.pub
```

然后克隆时改用 SSH URL：

```bash
git clone git@github.com:ZongjiaLong/Pylectra.git
```

## 常见问题

### Q：Git Bash 和 cmd 用哪个？

Git Bash（Windows 装 git 后送的）更接近 macOS / Linux 的风格，跑大部分 Linux 命令都能跑。**推荐 Git Bash**。

后续教程里我们的命令默认都假设你在一个**类 bash 终端**里——Git Bash、macOS Terminal、Linux 终端、conda 的 Anaconda Prompt 都行。

### Q：报错 `Permission denied (publickey)`？

你正在试图 push，但没配 SSH key（或 key 没加到 GitHub）。回头看上一节"配置 SSH key"。

### Q：`git pull` 报 `divergent branches`？

```bash
git config --global pull.rebase true
git pull
```

之前装时配过这个就不会再遇到。

### Q：clone 一半断了怎么办？

直接 `cd` 进部分克隆的目录然后：

```bash
git fetch --all
```

或者删掉重 clone。

## 接下来读什么

- [安装 Pylectra](03-install-pylectra.md) — 用刚装的 git 把 pylectra 拿到本地，跑起来
