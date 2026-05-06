"""Time-series plots for one :class:`pylectra.core.result.SimulationResult`.

All helpers honor the Nature-grade style applied via
:func:`pylectra.plotting.style.set_nature_style` (called automatically the first
time any helper is invoked).

Each helper accepts either a :class:`SimulationResult` or a path to a
``.h5`` / ``.npz`` sample file (resolved via
:func:`pylectra.plotting._loaders.load_result`).

Returns a :class:`matplotlib.figure.Figure` so callers can save / further
customize as needed.

Supported plot kinds:

* :func:`plot_rotor_angles`   — generator rotor angles vs. time, optionally
  expressed relative to the system mean (the typical post-fault diagnostic).
* :func:`plot_speeds`         — generator speeds vs. time.
* :func:`plot_voltage_magnitudes` — bus voltage magnitudes vs. time.
* :func:`plot_efds`           — exciter field voltages vs. time.
* :func:`plot_overview`       — 2x2 multi-panel (angles / speeds / voltages /
  Efd) ready for paper appendices.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from pylectra.core.result import SimulationResult

from ._loaders import load_result
from .io import journal_figsize
from .style import cycle_colors, despine, nature_palette, set_nature_style


_StyleApplied = False


def _ensure_style() -> None:
    global _StyleApplied
    if not _StyleApplied:
        set_nature_style()
        _StyleApplied = True


def _resolve(source) -> SimulationResult:
    return load_result(source)


def _select_indices(n: int, indices: Optional[Iterable[int]]) -> np.ndarray:
    if indices is None:
        return np.arange(n)
    arr = np.asarray(list(indices), dtype=int)
    if arr.size == 0:
        raise ValueError("indices must be non-empty")
    if arr.min() < 0 or arr.max() >= n:
        raise IndexError(
            f"indices out of range [0, {n}); got "
            f"min={int(arr.min())}, max={int(arr.max())}"
        )
    return arr


# ---------------------------------------------------------------------------
# Per-plot helpers
# ---------------------------------------------------------------------------

def plot_rotor_angles(
    source: Union[SimulationResult, str, Path],
    *,
    relative: bool = True,
    gen_indices: Optional[Sequence[int]] = None,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Generator rotor angles vs. time.

    Parameters
    ----------
    relative:
        If True (default), subtract the system mean angle at each step so
        only inter-machine swings are shown (canonical post-fault view).
    gen_indices:
        Subset of generator indices to plot.  ``None`` → all.
    """
    _ensure_style()
    res = _resolve(source)
    if res.n_steps == 0 or res.n_gen == 0:
        raise ValueError("result has no time-series data to plot")

    idx = _select_indices(res.n_gen, gen_indices)
    t = np.asarray(res.Time)
    angles = np.asarray(res.Angles)[:, idx]
    if relative:
        angles = angles - np.asarray(res.Angles).mean(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single"))
    colors = cycle_colors(palette=palette)
    for i, gen in enumerate(idx):
        ax.plot(t, angles[:, i], color=colors[i % len(colors)],
                lw=1.6, label=f"G{int(gen) + 1}")
    ax.set_xlabel("Time (s)")
    ylabel = "Rotor angle (deg, rel. to mean)" if relative else "Rotor angle (deg)"
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    if len(idx) <= 12:
        ax.legend(loc="best", ncol=min(4, len(idx)), fontsize=10)
    despine(ax)
    return fig


def plot_speeds(
    source: Union[SimulationResult, str, Path],
    *,
    gen_indices: Optional[Sequence[int]] = None,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Generator speed (p.u. of nominal) vs. time."""
    _ensure_style()
    res = _resolve(source)
    if res.n_steps == 0 or res.n_gen == 0:
        raise ValueError("result has no time-series data to plot")

    idx = _select_indices(res.n_gen, gen_indices)
    t = np.asarray(res.Time)
    omega = np.asarray(res.Speeds)[:, idx]

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single"))
    colors = cycle_colors(palette=palette)
    for i, gen in enumerate(idx):
        ax.plot(t, omega[:, i], color=colors[i % len(colors)],
                lw=1.6, label=f"G{int(gen) + 1}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (p.u.)")
    if title:
        ax.set_title(title)
    if len(idx) <= 12:
        ax.legend(loc="best", ncol=min(4, len(idx)), fontsize=10)
    despine(ax)
    return fig


def plot_voltage_magnitudes(
    source: Union[SimulationResult, str, Path],
    *,
    bus_indices: Optional[Sequence[int]] = None,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Bus voltage magnitudes ``|V|`` vs. time."""
    _ensure_style()
    res = _resolve(source)
    if res.n_steps == 0 or res.n_bus == 0:
        raise ValueError("result has no time-series data to plot")

    n_bus = res.n_bus
    idx = _select_indices(n_bus, bus_indices)
    t = np.asarray(res.Time)
    vm = np.abs(np.asarray(res.Voltages))[:, idx]

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("double"))
    colors = cycle_colors(palette=palette)
    # If many buses, fall back to a thin grey background + colored highlights
    if len(idx) <= 16:
        for i, b in enumerate(idx):
            ax.plot(t, vm[:, i], color=colors[i % len(colors)],
                    lw=1.4, label=f"Bus {int(b) + 1}")
        ax.legend(loc="best", ncol=min(4, len(idx)), fontsize=10)
    else:
        for i, b in enumerate(idx):
            ax.plot(t, vm[:, i], color="#4D4D4D", lw=0.6, alpha=0.4)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("|V| (p.u.)")
    if title:
        ax.set_title(title)
    despine(ax)
    return fig


def plot_efds(
    source: Union[SimulationResult, str, Path],
    *,
    gen_indices: Optional[Sequence[int]] = None,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """Exciter field voltages ``Efd`` vs. time."""
    _ensure_style()
    res = _resolve(source)
    if res.n_steps == 0 or res.n_gen == 0:
        raise ValueError("result has no time-series data to plot")

    idx = _select_indices(res.n_gen, gen_indices)
    t = np.asarray(res.Time)
    efd = np.asarray(res.Efds)[:, idx]

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single"))
    colors = cycle_colors(palette=palette)
    for i, gen in enumerate(idx):
        ax.plot(t, efd[:, i], color=colors[i % len(colors)],
                lw=1.6, label=f"G{int(gen) + 1}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(r"$E_{fd}$ (p.u.)")
    if title:
        ax.set_title(title)
    if len(idx) <= 12:
        ax.legend(loc="best", ncol=min(4, len(idx)), fontsize=10)
    despine(ax)
    return fig


def plot_overview(
    source: Union[SimulationResult, str, Path],
    *,
    palette: str = "default",
    title: Optional[str] = None,
    figsize=None,
) -> Figure:
    """2x2 multi-panel: rotor angles, speeds, voltages, Efd.

    Useful as a one-shot 'paper appendix' figure for a single simulation.
    """
    _ensure_style()
    res = _resolve(source)
    if res.n_steps == 0:
        raise ValueError("result has no time-series data to plot")

    fs = figsize or journal_figsize("double", aspect=0.78)
    fig, axes = plt.subplots(2, 2, figsize=fs)

    t = np.asarray(res.Time)
    colors = cycle_colors(palette=palette)
    angles_rel = (np.asarray(res.Angles)
                  - np.asarray(res.Angles).mean(axis=1, keepdims=True))
    omega = np.asarray(res.Speeds)
    vm = np.abs(np.asarray(res.Voltages))
    efd = np.asarray(res.Efds)

    for i in range(res.n_gen):
        c = colors[i % len(colors)]
        axes[0, 0].plot(t, angles_rel[:, i], color=c, lw=1.4)
        axes[0, 1].plot(t, omega[:, i], color=c, lw=1.4)
        axes[1, 1].plot(t, efd[:, i], color=c, lw=1.4)
    # voltages: thin grey
    for b in range(res.n_bus):
        axes[1, 0].plot(t, vm[:, b], color="#4D4D4D", lw=0.5, alpha=0.45)

    axes[0, 0].set_ylabel("Rotor angle (deg, rel.)")
    axes[0, 1].set_ylabel("Speed (p.u.)")
    axes[1, 0].set_ylabel("|V| (p.u.)")
    axes[1, 1].set_ylabel(r"$E_{fd}$ (p.u.)")
    for ax in axes.ravel():
        ax.set_xlabel("Time (s)")
        despine(ax)
    if title:
        fig.suptitle(title, fontsize=14)
    return fig


__all__ = [
    "plot_rotor_angles",
    "plot_speeds",
    "plot_voltage_magnitudes",
    "plot_efds",
    "plot_overview",
]
