# 什么是 Git 和 GitHub？

_初学者_

> 如果你只是想**用** pylectra（而不是改它），其实可以**绕过**整个 git/GitHub 流程：直接从项目页面下载一个 zip 解压。本页面是为想跟上后续版本、或将来贡献代码的人写的。

## 一句话定义

- **Git** 是一个**版本控制工具**——记录"谁在什么时候改了哪几行代码"。
- **GitHub** 是一个**代码托管网站**——把 Git 仓库放在云上，供别人下载、协作、提交问题。

类比：

| 现实概念 | Git | GitHub |
|---|---|---|
| Word 的"修订记录" | 提交（commit）历史 | — |
| 实验室共享盘里的"v1 / v2 / v3 备份" | 分支（branch） | 远程仓库（remote） |
| 多人合作改一份合同 | 合并（merge） | Pull Request（PR） |
| 报 bug | — | Issue |

## Git 的最小心智模型

把代码看作**一棵树**，每次保存（叫**提交 / commit**）就是在树上加一个节点：

```
A ─ B ─ C ─ D ← main 分支当前最新
```

每个节点（commit）记录：

- **谁**做的（作者）
- **什么时候**做的
- **改了哪些行**（diff）
- **一句话说明**（commit message）

如果想试一个改动但又不确定，开一个**分支**：

```
A ─ B ─ C ─ D                  ← main
            \
             E ─ F             ← my-feature
```

`my-feature` 上随便改，main 不受影响。试好了把它**合并回**（merge）main：

```
A ─ B ─ C ─ D ─────── G        ← main（G 是合并提交）
            \       /
             E ─ F
```

## 用 Git 拿到 pylectra

这就一条命令：

```bash
git clone https://github.com/ZongjiaLong/Pylectra.git
cd pylectra
```

`clone` 把整个仓库（含全部历史、所有分支）拷到本地一个文件夹。

如果只是要某次发布的代码：

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/ZongjiaLong/Pylectra.git
```

`--branch v0.1.0` 切到那个版本标签，`--depth 1` 只拿最新一次提交（省网速）。

## 取最新代码 / 提交自己的修改

```bash
# 取上游最新（不会动你本地未提交的修改）
git pull

# 看哪些文件改了
git status

# 暂存要提交的改动
git add my_new_plugin.py

# 提交
git commit -m "Add new generator model X"

# 推送到 GitHub（如果你有这个仓库的写权限）
git push
```

如果你没有写权限但想贡献，标准流程是：

1. 在 GitHub 网页上 **Fork** 这个仓库（在你账户下做一份拷贝）
2. 在自己 fork 上 clone、改、commit、push
3. 回到原仓库网页，点 **New Pull Request**，把自己的改动**提交给上游审核**

## GitHub 上能干什么

进入 [github.com/ZongjiaLong/Pylectra](https://github.com/ZongjiaLong/Pylectra)（示例 URL），你会看到：

| 标签页 | 用途 |
|---|---|
| **Code** | 浏览所有源文件、README、目录树 |
| **Issues** | 报 bug、提需求、问问题 |
| **Pull requests** | 别人提交的待审核改动 |
| **Discussions** | 论坛式讨论 |
| **Actions** | 自动跑的测试 / CI |
| **Releases** | 历史发布版本（可下载 zip / tar.gz） |
| **Wiki** | 额外文档（pylectra 不用，主文档在 docs/） |

## 完全不会 git，能用 pylectra 吗？

可以。两条路：

### 路 1：直接下载 zip

进入 [Releases](https://github.com/ZongjiaLong/Pylectra/releases)，找到最新版本，点 **Source code (zip)** 下载，解压。然后照常 `pip install -e .`。

缺点：拿不到 main 分支上还没发版的最新修复，升级要重新下载。

### 路 2：从 PyPI 装（最简单）

```bash
pip install pylectra
```

完全跳过 git 和 GitHub。缺点：拿不到源代码、不能轻松看实现、不能改本地文件做调试。

## 学多深就够用了？

电力工程师做研究通常只需要：

- `git clone` 拿代码
- `git pull` 取最新
- `git status` / `git log` 看状态
- `git checkout v0.1.0` 切到某个版本

要往上游贡献代码再学：

- `git branch` / `git checkout -b`
- `git add` / `git commit`
- `git push`
- GitHub 网页上的 Pull Request 流程

更高阶（rebase、cherry-pick、stash）可以以后再学，**绝大部分时候用不到**。

## 接下来读什么

- [安装 Git](../getting-started/02-install-git.md) — 在你的电脑上装好 git，跟着第一条 `git clone` 试一下
