"""Network-topology schematic.

Plots a network case (bus + branch) using a deterministic spring layout when
no explicit coordinates are present, with optional metric-driven coloring of
buses (e.g. final-time |V| or load).

We deliberately keep the implementation matplotlib-only (no networkx, no
graphviz) so it runs in CI without extra wheels.

The spring layout is implemented from scratch (Fruchterman-Reingold, fixed
seed) for reproducibility.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection

from pylectra.core.case import NetworkCase

from .io import journal_figsize
from .style import despine, set_nature_style, PALETTE


_StyleApplied = False


def _ensure_style() -> None:
    global _StyleApplied
    if not _StyleApplied:
        set_nature_style()
        _StyleApplied = True


def _spring_layout(
    n: int,
    edges: Sequence[Tuple[int, int]],
    *,
    seed: int = 0,
    iterations: int = 200,
) -> np.ndarray:
    """Fruchterman-Reingold force-directed layout returning ``(n, 2)`` coords.

    Pure-numpy implementation; deterministic given ``seed``.  Suitable for
    n up to ~few hundred buses (case39 = 39 buses → trivial).
    """
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1.0, 1.0, size=(n, 2))
    if n <= 1:
        return pos

    k = 1.0 / np.sqrt(max(n, 1))
    t = 0.1  # initial "temperature" controls max displacement per iteration
    cooling = t / (iterations + 1)

    e_arr = np.asarray(edges, dtype=int) if len(edges) else np.zeros((0, 2), int)

    for _ in range(iterations):
        # Repulsive forces (vectorised pairwise diff)
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=-1)
        np.fill_diagonal(dist, 1e-9)
        rep_mag = (k * k) / dist
        # zero-out self-interactions
        rep_mag[np.arange(n), np.arange(n)] = 0.0
        unit = delta / dist[..., None]
        force = (unit * rep_mag[..., None]).sum(axis=1)

        # Attractive forces along edges
        if e_arr.size:
            d_e = pos[e_arr[:, 0]] - pos[e_arr[:, 1]]
            d_e_len = np.linalg.norm(d_e, axis=1) + 1e-9
            attr_mag = (d_e_len * d_e_len) / k
            unit_e = d_e / d_e_len[:, None]
            np.add.at(force, e_arr[:, 0], -unit_e * attr_mag[:, None])
            np.add.at(force, e_arr[:, 1],  unit_e * attr_mag[:, None])

        # Apply with temperature cap
        f_len = np.linalg.norm(force, axis=1) + 1e-9
        scale = np.minimum(f_len, t) / f_len
        pos = pos + force * scale[:, None]
        t -= cooling

    # Center & rescale to [-1, 1]
    pos -= pos.mean(axis=0)
    span = max(pos.max() - pos.min(), 1e-9)
    pos = pos * (1.8 / span)
    return pos


def _bus_id_to_idx(bus_array: np.ndarray) -> Dict[int, int]:
    """MATPOWER bus ids are arbitrary positive integers — map to row idx."""
    return {int(bus_array[i, 0]): i for i in range(bus_array.shape[0])}


def plot_network(
    case: Union[NetworkCase, Dict[str, Any], str],
    *,
    color_by: Optional[Union[Sequence[float], np.ndarray, str]] = None,
    cmap: str = "viridis",
    cbar_label: Optional[str] = None,
    bus_size: float = 90.0,
    edge_color: str = "#4D4D4D",
    edge_alpha: float = 0.6,
    edge_lw: float = 1.0,
    show_labels: bool = False,
    title: Optional[str] = None,
    figsize=None,
    seed: int = 0,
) -> Figure:
    """Render a network case as a force-directed schematic.

    Parameters
    ----------
    case:
        :class:`NetworkCase`, the underlying ``mpc`` dict, or a case name
        string (will be loaded via :meth:`NetworkCase.load`).
    color_by:
        Either a per-bus 1-D array of metric values to color bus markers by,
        or one of the strings:

        * ``"vm"``     — bus voltage magnitudes (``mpc.bus[:, VM]``).
        * ``"pd"``     — bus active load (``mpc.bus[:, PD]``).
        * ``"qd"``     — bus reactive load (``mpc.bus[:, QD]``).
        * ``"type"``   — bus type code.

        When None (default) all buses are drawn in a single neutral color.
    show_labels:
        If True, label each bus with its MATPOWER id.
    """
    _ensure_style()

    if isinstance(case, str):
        case_obj = NetworkCase.load(case)
    elif isinstance(case, NetworkCase):
        case_obj = case
    elif isinstance(case, dict):
        case_obj = NetworkCase(case)
    else:
        raise TypeError(
            f"case must be NetworkCase / dict / str, got {type(case).__name__}"
        )

    bus = np.asarray(case_obj.bus)
    branch = np.asarray(case_obj.branch)
    n_bus = bus.shape[0]

    # Build edges using MATPOWER 1-based bus ids → 0-based row indices
    id_to_idx = _bus_id_to_idx(bus)
    edges: list[Tuple[int, int]] = []
    for k in range(branch.shape[0]):
        f, t = int(branch[k, 0]), int(branch[k, 1])
        if f in id_to_idx and t in id_to_idx:
            edges.append((id_to_idx[f], id_to_idx[t]))

    pos = _spring_layout(n_bus, edges, seed=seed)

    # Resolve color values
    values: Optional[np.ndarray] = None
    if color_by is not None:
        if isinstance(color_by, str):
            # MATPOWER column indices: VM=7 (1-based 8), PD=2 (1-based 3),
            # QD=3 (1-based 4), TYPE=1 (1-based 2)
            COLS = {"vm": 7, "pd": 2, "qd": 3, "type": 1}
            key = color_by.lower()
            if key not in COLS:
                raise KeyError(
                    f"unknown color_by={color_by!r}; choose one of "
                    f"{sorted(COLS)} or pass an array"
                )
            values = np.asarray(bus[:, COLS[key]], dtype=float)
            if cbar_label is None:
                cbar_label = key.upper()
        else:
            values = np.asarray(color_by, dtype=float)
            if values.shape[0] != n_bus:
                raise ValueError(
                    f"color_by length {values.shape[0]} != n_bus {n_bus}"
                )

    fig, ax = plt.subplots(figsize=figsize or journal_figsize("single", aspect=0.95))

    # Edges as a LineCollection (faster + uniform style)
    if edges:
        seg = np.array([[pos[a], pos[b]] for (a, b) in edges])
        lc = LineCollection(seg, colors=edge_color, linewidths=edge_lw,
                            alpha=edge_alpha, zorder=1)
        ax.add_collection(lc)

    if values is None:
        ax.scatter(pos[:, 0], pos[:, 1], s=bus_size, color=PALETTE["blue_main"],
                   edgecolor="white", linewidth=1.0, zorder=2)
    else:
        sc = ax.scatter(pos[:, 0], pos[:, 1], s=bus_size, c=values,
                        cmap=cmap, edgecolor="white", linewidth=1.0, zorder=2)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
        if cbar_label:
            cbar.set_label(cbar_label)

    if show_labels:
        for i in range(n_bus):
            ax.text(pos[i, 0], pos[i, 1] + 0.08, str(int(bus[i, 0])),
                    ha="center", va="bottom", fontsize=8, color="#272727")

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])
    despine(ax, left=True, bottom=True)
    if title:
        ax.set_title(title)
    return fig


__all__ = ["plot_network"]
