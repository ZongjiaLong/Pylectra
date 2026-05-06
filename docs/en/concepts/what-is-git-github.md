# What is Git and GitHub?

_Beginner_

> If you only want to **use** pylectra (not modify it), you can skip git/GitHub entirely — just download a release zip. This page is for people who want to track ongoing development or contribute later.

## One-line definitions

- **Git** is a **version-control tool** — it records "who changed which lines, and when".
- **GitHub** is a **code-hosting website** — it stores Git repositories in the cloud so others can download, collaborate, and report issues.

Analogies:

| Real-world concept | Git | GitHub |
|---|---|---|
| Word's "track changes" | commit history | — |
| Lab share drive's "v1 / v2 / v3 backups" | branches | remote repository |
| Multi-person edits on a contract | merge | Pull Request (PR) |
| Bug reports | — | Issues |

## The minimal mental model

Think of code as a **tree**. Every save (called a **commit**) adds a node:

```
A ─ B ─ C ─ D ← latest tip of the main branch
```

Each commit records:

- **Who** authored it.
- **When** it happened.
- **Which lines** changed (the diff).
- **A short message** describing the change.

If you want to try something experimental without disturbing main, open a **branch**:

```
A ─ B ─ C ─ D                  ← main
            \
             E ─ F             ← my-feature
```

You can iterate freely on `my-feature` without affecting main. When happy, **merge** it back:

```
A ─ B ─ C ─ D ─────── G        ← main (G is the merge commit)
            \       /
             E ─ F
```

## Get pylectra with git

A single command:

```bash
git clone https://github.com/pylectra/pylectra.git
cd pylectra
```

`clone` copies the entire repository (full history, all branches) into a local folder.

For just one specific release:

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/pylectra/pylectra.git
```

`--branch v0.1.0` checks out that version tag; `--depth 1` fetches only the latest commit (saves bandwidth).

## Pull updates / push your own changes

```bash
# Fetch upstream changes (won't touch uncommitted local edits)
git pull

# See which files you've changed
git status

# Stage edits
git add my_new_plugin.py

# Commit
git commit -m "Add new generator model X"

# Push to GitHub (only if you have write access)
git push
```

If you don't have write access but want to contribute, the standard flow is:

1. Click **Fork** on the repo's GitHub page (creates a copy under your account).
2. Clone your fork, edit, commit, push.
3. Go back to the original repo, click **New Pull Request** to submit your branch for review.

## What can you do on GitHub?

Visit [github.com/pylectra/pylectra](https://github.com/pylectra/pylectra) (illustrative URL):

| Tab | Purpose |
|---|---|
| **Code** | Browse source, README, file tree |
| **Issues** | Bug reports, feature requests, questions |
| **Pull requests** | Pending changes awaiting review |
| **Discussions** | Forum-style threads |
| **Actions** | CI / automated test runs |
| **Releases** | Tagged versions (downloadable zip / tar.gz) |
| **Wiki** | Extra docs (pylectra doesn't use it; the main docs live in `docs/`) |

## Can I use pylectra without learning git?

Yes — two paths:

### Path 1 — download a release zip

Visit the [Releases](https://github.com/pylectra/pylectra/releases) page, pick the newest version, click **Source code (zip)**, unzip, then `pip install -e .` as usual.

Drawback: no quick access to bug fixes that have landed on main but aren't released; upgrading means re-downloading.

### Path 2 — install from PyPI (simplest)

```bash
pip install pylectra
```

Skips git and GitHub entirely. Drawback: no source files locally; harder to read the implementation or patch things for debugging.

## How much git is enough?

For typical research use:

- `git clone` to fetch the code.
- `git pull` to update.
- `git status` / `git log` to inspect.
- `git checkout v0.1.0` to switch to a specific version.

To contribute upstream, also learn:

- `git branch` / `git checkout -b`
- `git add` / `git commit`
- `git push`
- The Pull Request flow on GitHub's website.

Advanced topics (rebase, cherry-pick, stash) can wait — most days you won't need them.

## Next steps

- [Install Git](../getting-started/02-install-git.md) — install git on your machine and try a `git clone`.
