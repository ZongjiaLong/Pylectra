# Install Git

_Beginner_

**Prerequisites:** [What is Git and GitHub](../concepts/what-is-git-github.md)

> Skipping git is fine if you only want to use pylectra — download a release zip or `pip install pylectra` directly. This page is for people who want the latest source or plan to contribute.

## Step 1 — Check whether git is installed

```bash
git --version
```

If you see `git version 2.x.x`, skip this page.
Otherwise install it.

## Windows

### Option A — Git for Windows (recommended)

1. Download the installer from [https://git-scm.com/download/win](https://git-scm.com/download/win).
2. Double-click and click **Next** through most options. **Pay attention to**:
   - "Select Components": defaults are fine.
   - **"Adjusting your PATH environment"**: choose **"Git from the command line and also from 3rd-party software"** (the default).
   - "Choosing the SSH executable": "Use bundled OpenSSH" (default).
   - "Configuring the line ending conversions": choose **"Checkout as-is, commit Unix-style line endings"** to avoid CRLF/LF noise in diffs.
   - "Configuring the terminal emulator": MinTTY is fine.
3. The installer ships **Git Bash** (find it in the Start menu) — a Linux-style shell that handles git much more naturally than `cmd`.

### Option B — Install via conda (if Miniconda is already set up)

```bash
conda install -c conda-forge git
```

## macOS

The fastest path:

```bash
xcode-select --install
```

Click Install when the dialog pops up. After that `git --version` shows Apple's bundled version (good enough).

You can also `brew install git` if you have Homebrew and want the latest.

## Linux

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y git

# CentOS / RHEL / Fedora
sudo dnf install -y git
```

## Step 2 — Basic configuration

One-time setup per machine (git stamps these onto every commit):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

**The email is never sent anywhere by git** — it just goes into commit metadata. Use your university or work address.

Optional but recommended:

```bash
# Use main, not master, as the default branch name for new repos
git config --global init.defaultBranch main

# Auto-rebase on pull (avoids meaningless merge commits)
git config --global pull.rebase true

# Render non-ASCII filenames correctly (especially helpful on Windows)
git config --global core.quotepath false
```

## Step 3 — Quick test

In any directory:

```bash
git clone https://github.com/ZongjiaLong/Pylectra.git
cd pylectra
git log --oneline | head
```

The last command should print short messages from the most recent commits.

## (Optional) SSH keys to skip password prompts

Only needed if you'll push to your own fork. As a pylectra user, **skip this entirely**.

If you do need it:

```bash
# Generate a key (press Enter for the default path, leave passphrase empty for no prompt)
ssh-keygen -t ed25519 -C "you@example.com"

# Show the public key — paste this into GitHub → Settings → SSH and GPG keys → New SSH key
cat ~/.ssh/id_ed25519.pub
```

Then clone via the SSH URL:

```bash
git clone git@github.com:ZongjiaLong/Pylectra.git
```

## FAQ

### Q: Git Bash or cmd on Windows?

Git Bash (shipped with Git for Windows) is closer to macOS / Linux shells and runs most Linux-style commands. **Prefer Git Bash.**

Subsequent tutorials assume a **bash-like terminal** — Git Bash, macOS Terminal, Linux terminal, or Anaconda Prompt all qualify.

### Q: `Permission denied (publickey)` on push?

You haven't added an SSH key (or it's not registered on GitHub). See "SSH keys" above.

### Q: `git pull` reports `divergent branches`?

```bash
git config --global pull.rebase true
git pull
```

If you set `pull.rebase` during the initial config you won't hit this.

### Q: A clone died half-way — what now?

`cd` into the partial directory and:

```bash
git fetch --all
```

or wipe the folder and `git clone` again.

## Next steps

- [Install Pylectra](03-install-pylectra.md) — use git to fetch pylectra and run it locally.
