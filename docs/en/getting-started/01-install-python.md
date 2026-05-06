# Install Python

_Beginner_

**Prerequisites:** [What is a Python package](../concepts/what-is-python-package.md)

> Step-by-step Python install from scratch. If you can already run `python --version`, jump to [Install Git](02-install-git.md).
> We **strongly recommend Miniconda** instead of the plain Python.org installer — it bundles Python + package management + virtual environments + the C/Fortran compiler toolchain (`scipy`, `pandapower`, etc. need it).

## Step 1 — Check whether Python is already installed

Open a terminal:

- **Windows**: `Win + R` → type `cmd` → Enter
- **macOS**: `Cmd + Space` → type `Terminal` → Enter
- **Linux**: `Ctrl + Alt + T`

Type:

```bash
python --version
```

If you see `Python 3.10.x` or later, **you're already set up** — skip this page.
If it's 2.7.x or 3.8.x, follow the steps below to install Miniconda alongside; the old one can stay untouched.
If it says "command not found / not recognised", proceed.

## Step 2 — Download Miniconda

Open: [https://docs.conda.io/projects/miniconda/en/latest/](https://docs.conda.io/projects/miniconda/en/latest/)

Pick the file matching your system:

| OS | File |
|---|---|
| Windows 10/11 | `Miniconda3-latest-Windows-x86_64.exe` |
| macOS (Intel) | `Miniconda3-latest-MacOSX-x86_64.pkg` |
| macOS (Apple Silicon M1/M2/M3) | `Miniconda3-latest-MacOSX-arm64.pkg` |
| Linux | `Miniconda3-latest-Linux-x86_64.sh` |

> Not sure which Mac chip you have? Apple menu → "About This Mac" → look at "Processor". Apple M1/M2/M3 → arm64; Intel Core → x86_64.

## Step 3 — Install

### Windows

1. Double-click the downloaded `.exe`.
2. Click **Next** through the wizard.
3. **Important**: on the "Advanced Installation Options" page:
   - ✅ Tick **"Add Miniconda3 to my PATH environment variable"** (the installer warns in red, but for our use case **please tick it** — it lets you call `python` / `conda` from any shell).
   - ✅ Tick **"Register Miniconda3 as my default Python"**.
4. Click Install, wait a few minutes, finish.

### macOS

1. Double-click the `.pkg`.
2. Continue → Install.
3. Open Terminal and verify with `conda --version`.

### Linux

In a terminal, in the download directory:

```bash
bash Miniconda3-latest-Linux-x86_64.sh
```

Follow the prompts:

- Read the licence → type `yes`.
- Choose install path (default `~/miniconda3` is fine) → Enter.
- "Do you wish to update your shell profile..." → `yes`.

Close and reopen the terminal afterwards.

## Step 4 — Verify

Open a **fresh** terminal (the old window may not have the updated `PATH` yet):

```bash
conda --version
python --version
```

You should see something like:

```
conda 24.3.0
Python 3.12.x
```

If `conda --version` reports "command not found":

- **Windows**: PATH may not have been added. Use "Start menu → Anaconda Prompt (miniconda3)" — that special shell always finds conda. Or rerun the installer and tick "Add to PATH".
- **macOS / Linux**: `source ~/.bashrc` (or `~/.zshrc`), then retry.

## Step 5 — (Optional) configure mirrors for faster downloads {#mirrors}

In some regions PyPI's default servers are slow. The Tsinghua mirror is a popular alternative:

```bash
# conda → Tsinghua
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
conda config --set show_channel_urls yes

# pip → Tsinghua (persistent)
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

Subsequent `conda install` and `pip install` calls then pull from the mirror, often 10–100× faster.

## FAQ

### Q: Why not just use the Python.org installer?

You can. But you'd then need to:

- Install every package manually with `pip install ...`.
- Learn `venv` for environment isolation.
- For C-extension packages like `pandapower`, supply Visual Studio's compiler yourself.

Miniconda bundles all of this.

### Q: Anaconda vs Miniconda?

- **Anaconda**: ~3 GB, ships a few hundred pre-installed data-science packages.
- **Miniconda**: ~100 MB, just Python + conda. Add what you need on demand.

We recommend Miniconda — clean, small, and you can `conda install` / `pip install` whatever else you need later.

### Q: Can I install on a non-system drive?

**Windows**: yes — and **prefer somewhere like `D:\Miniconda3`** rather than `C:\Program Files\...`. The latter contains a space, which a few Python packages stumble over.

### Q: How do I uninstall?

- **Windows**: Control Panel → Programs → Miniconda3 → Uninstall.
- **macOS / Linux**: `rm -rf ~/miniconda3` and clean up the `conda init` block in `~/.bashrc` / `~/.zshrc`.

## Next steps

- [Install Git](02-install-git.md) — install git so you can fetch pylectra's source from GitHub.
