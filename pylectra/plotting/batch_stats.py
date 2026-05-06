"""Batch-result statistics plots.

These read the metadata table written by :class:`pylectra.io.metadata_writer.MetadataWriter`
(``metadata.parquet`` or ``metadata.csv``) and produce summary plots over
many samples — the workflow you want when generating ML datasets.

Three families:

* :func:`plot_metric_violin`     — distribution of one numeric column,
  optionally split by another categorical column.
* :func:`plot_metric_histogram`  — histogram + KDE-like fill for one column.
* :func:`plot_acceptance_summary` — accept / reject / pf-fail bar chart.
* :func:`plot_metric_heatmap`    — pairwise mean of one metric over two
  categorical / binned columns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .io import journal_figsize
from .style import (DEFAULT_COLORS, PALETTE, cycle_colors, despine,
                    nature_palette, set_nature_style)


PathLike = Union[str, Path]
_StyleApplied = False


def _ensure_style() -> None:
    global _StyleApplied
    if not _StyleApplied:
        set_nature_style()
        _StyleApplied = True


# ---------------------------------------------------------------------------
# Metadata loader
# ---------------------------------------------------------------------------

def load_metadata(source: Union[PathLike, pd.DataFrame]) -> pd.DataFrame:
    """Resolve ``source`` to a pandas :class:`DataFrame`.

    Accepts a DataFrame directly, a ``.parquet`` path, a ``.csv`` path, or
    a directory — in which case ``metadata.parquet`` then ``metadata.csv``
    are tried inside it.
    """
    if isinstance(source, pd.DataFrame):
        return source
    p = Path(source)
    if p.is_dir():
        for name in ("metadata.parquet", "metadata.csv"):
            cand = p / name
            if cand.exists():
                p = cand
                break
        else:
            raise FileNotFoundError(
                f"no metadata.parquet/csv inside directory {p}"
            )
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() == ".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    raise ValueError(
        f"unsupported metadata extension {p.suffix!r}; want .parquet or .csv"
    )


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def plot_acceptance_summary(
    source: Union[PathLike, pd.DataFrame],
    *,
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Bar chart of accepted / rejected / pf-failed counts."""
    _ensure_style()
    df = load_metadata(source)

    n_total = len(df)
    n_pf_fail = int((~df["pf_success"].astype(bool)).sum()) if "pf_success" in df else 0
    n_passed = int(df["passed"].astype(bool).sum()) if "passed" in df else 0
    n_rejected = n_total - n_passed - n_pf_fail
    if n_rejected < 0:
        n_rejected = 0

    cats = ["Accepted", "Rejected", "PF failed"]
    vals = [n_passed, n_rejected, n_pf_fail]
    colors = [PALETTE["green_3"], PALETTE["red_2"], PALETTE["neutral_mid"]]

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single", aspect=0.7))
    bars = ax.bar(cats, vals, color=colors, edgecolor="black", linewidth=1.5)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.01,
                str(int(v)), ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Number of samples")
    if title:
        ax.set_title(title)
    despine(ax)
    return fig


def plot_metric_histogram(
    source: Union[PathLike, pd.DataFrame],
    column: str,
    *,
    bins: Union[int, Sequence[float]] = 30,
    color: Optional[str] = None,
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Histogram of one numeric metadata column."""
    _ensure_style()
    df = load_metadata(source)
    if column not in df.columns:
        raise KeyError(
            f"column {column!r} not in metadata; available: {list(df.columns)}"
        )
    series = pd.to_numeric(df[column], errors="coerce").dropna().to_numpy()
    if series.size == 0:
        raise ValueError(f"column {column!r} has no numeric values")

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single"))
    ax.hist(series, bins=bins,
            color=color or PALETTE["blue_secondary"],
            edgecolor="white", linewidth=1.0, alpha=0.92)
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    if title:
        ax.set_title(title)
    despine(ax)
    return fig


def plot_metric_violin(
    source: Union[PathLike, pd.DataFrame],
    column: str,
    *,
    by: Optional[str] = None,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Violin plot of one column, optionally split by a categorical column."""
    _ensure_style()
    df = load_metadata(source)
    if column not in df.columns:
        raise KeyError(
            f"column {column!r} not in metadata; available: {list(df.columns)}"
        )

    if by is None:
        groups = [pd.to_numeric(df[column], errors="coerce")
                  .dropna().to_numpy()]
        labels = [column]
    else:
        if by not in df.columns:
            raise KeyError(f"by column {by!r} not in metadata")
        groups = []
        labels = []
        for key, sub in df.groupby(by):
            vals = pd.to_numeric(sub[column], errors="coerce").dropna().to_numpy()
            if vals.size:
                groups.append(vals)
                labels.append(str(key))
        if not groups:
            raise ValueError(f"no numeric values to plot for {column!r} by {by!r}")

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single"))
    parts = ax.violinplot(groups, showmedians=True, showextrema=False)
    colors = cycle_colors(palette=palette)
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(colors[i % len(colors)])
        body.set_edgecolor("black")
        body.set_alpha(0.85)
    if "cmedians" in parts:
        parts["cmedians"].set_color("black")

    ax.set_xticks(np.arange(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(column)
    if title:
        ax.set_title(title)
    despine(ax)
    return fig


def plot_metric_heatmap(
    source: Union[PathLike, pd.DataFrame],
    column: str,
    *,
    rows: str,
    cols: str,
    aggfunc: str = "mean",
    cmap: str = "magma",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Pivot-table heatmap of ``column`` aggregated over ``rows`` × ``cols``."""
    _ensure_style()
    df = load_metadata(source)
    for c in (column, rows, cols):
        if c not in df.columns:
            raise KeyError(f"column {c!r} not in metadata")

    df = df.copy()
    df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=[column])
    if df.empty:
        raise ValueError(
            f"no numeric values for {column!r} after coercion"
        )

    pivot = df.pivot_table(index=rows, columns=cols, values=column,
                           aggfunc=aggfunc)

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single", aspect=0.9))
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(c) for c in pivot.columns], rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(r) for r in pivot.index])
    ax.set_xlabel(cols)
    ax.set_ylabel(rows)
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label(f"{aggfunc}({column})")
    if title:
        ax.set_title(title)
    return fig


__all__ = [
    "load_metadata",
    "plot_acceptance_summary",
    "plot_metric_histogram",
    "plot_metric_violin",
    "plot_metric_heatmap",
]
