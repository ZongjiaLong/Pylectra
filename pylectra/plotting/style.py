"""Nature-grade matplotlib style for ``pylectra`` plotting.

Mirrors the rcParams typically required by Nature-family journals so
figures produced by this package look publication-ready out of the box:

* Arial sans-serif
* No top / right spines
* ``axes.linewidth = 2.5``
* ``font.size = 16``
* ``svg.fonttype = 'none'``  (text remains editable in SVG/PDF exports)
* No legend frame

Two palette families are exposed:

* ``PALETTE`` — the default categorical palette (saturated, signal-rich).
* ``PALETTE_NMI_PASTEL`` — low-saturation pastel set used when several
  compared methods belong to one or two related families.

Helpers:

* :func:`set_nature_style` — apply rcParams (call once before plotting).
* :func:`nature_palette` — return a list of hex codes by name.
* :func:`despine` — strip top/right spines from arbitrary axes.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Palettes — Nature/NMI-style restrained colour systems
# ---------------------------------------------------------------------------

PALETTE = {
    "blue_main":      "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_1":        "#DDF3DE",
    "green_2":        "#AADCA9",
    "green_3":        "#8BCF8B",
    "red_1":          "#F6CFCB",
    "red_2":          "#E9A6A1",
    "red_strong":     "#B64342",
    "neutral_light":  "#CFCECE",
    "neutral_mid":    "#767676",
    "neutral_dark":   "#4D4D4D",
    "neutral_black":  "#272727",
    "gold":           "#FFD700",
    "teal":           "#42949E",
    "violet":         "#9A4D8E",
    "magenta":        "#EA84DD",
}

DEFAULT_COLORS: List[str] = [
    PALETTE["blue_main"],
    PALETTE["green_3"],
    PALETTE["red_strong"],
    PALETTE["teal"],
    PALETTE["violet"],
    PALETTE["neutral_light"],
]

PALETTE_NMI_PASTEL = {
    "baseline_dark": "#484878",
    "baseline_mid":  "#7884B4",
    "baseline_soft": "#B4C0E4",
    "ours_tiny":     "#E4E4F0",
    "ours_base":     "#E4CCD8",
    "ours_large":    "#F0C0CC",
    "bg_lilac":      "#E0E0F0",
    "bg_aqua":       "#E0F0F0",
    "bg_peach":      "#F0E0D0",
    "neutral_light": "#D8D8D8",
    "neutral_mid":   "#A8A8A8",
    "neutral_dark":  "#606060",
    "delta_up":      "#2E9E44",
    "delta_down":    "#E53935",
}

DEFAULT_COLORS_NMI_PASTEL: List[str] = [
    PALETTE_NMI_PASTEL["baseline_dark"],
    PALETTE_NMI_PASTEL["baseline_mid"],
    PALETTE_NMI_PASTEL["baseline_soft"],
    PALETTE_NMI_PASTEL["ours_tiny"],
    PALETTE_NMI_PASTEL["ours_base"],
    PALETTE_NMI_PASTEL["ours_large"],
]


_PALETTE_REGISTRY = {
    "default":    DEFAULT_COLORS,
    "nature":     DEFAULT_COLORS,
    "nmi_pastel": DEFAULT_COLORS_NMI_PASTEL,
    "pastel":     DEFAULT_COLORS_NMI_PASTEL,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_nature_style(
    font_size: float = 16.0,
    axes_linewidth: float = 2.5,
    use_tex: bool = False,
) -> None:
    """Apply Nature-grade rcParams.

    Call once before creating any figures.  Idempotent.

    Parameters
    ----------
    font_size:
        Base font size.  Use ``8`` for dense journal-width multi-panels,
        ``24`` for large bar panels.
    axes_linewidth:
        Spine / tick linewidth.  Use ``1`` for tiny multi-panel grids,
        ``3`` for big bars.
    use_tex:
        Set ``rcParams['text.usetex'] = True``.  Requires a working LaTeX
        installation.
    """
    # ── MANDATORY: editable SVG text ─────────────────────────────────────
    mpl.rcParams["font.family"]       = "sans-serif"
    mpl.rcParams["font.sans-serif"]   = ["Arial", "DejaVu Sans", "Liberation Sans"]
    mpl.rcParams["svg.fonttype"]      = "none"

    # ── Layout & style ───────────────────────────────────────────────────
    mpl.rcParams["font.size"]         = float(font_size)
    mpl.rcParams["axes.spines.right"] = False
    mpl.rcParams["axes.spines.top"]   = False
    mpl.rcParams["axes.linewidth"]    = float(axes_linewidth)
    mpl.rcParams["legend.frameon"]    = False

    # Tick styling — keep ticks legible at the chosen axes_linewidth.
    mpl.rcParams["xtick.major.width"] = float(axes_linewidth) * 0.6
    mpl.rcParams["ytick.major.width"] = float(axes_linewidth) * 0.6
    mpl.rcParams["xtick.minor.width"] = float(axes_linewidth) * 0.4
    mpl.rcParams["ytick.minor.width"] = float(axes_linewidth) * 0.4

    if use_tex:
        mpl.rcParams["text.usetex"] = True


def nature_palette(name: str = "default") -> List[str]:
    """Return a list of hex colors for ``name``.

    Available names: ``default`` / ``nature`` (signal-rich), ``nmi_pastel`` /
    ``pastel`` (unified-family low-saturation).
    """
    key = name.lower()
    if key not in _PALETTE_REGISTRY:
        raise KeyError(
            f"unknown palette {name!r}; available: "
            f"{sorted(_PALETTE_REGISTRY)}"
        )
    # return a copy so callers can mutate freely
    return list(_PALETTE_REGISTRY[key])


def despine(ax, *, top: bool = True, right: bool = True,
            left: bool = False, bottom: bool = False) -> None:
    """Hide selected spines on a matplotlib axes."""
    spines = {"top": top, "right": right, "left": left, "bottom": bottom}
    for side, hide in spines.items():
        if hide:
            ax.spines[side].set_visible(False)


def cycle_colors(colors: Optional[Iterable[str]] = None,
                 palette: str = "default") -> List[str]:
    """Return a deterministic color list, defaulting to ``palette``.

    Useful when looping over a variable number of series — callers can
    do ``for x, c in zip(series, cycle_colors(n=len(series)))``.
    """
    base = list(colors) if colors is not None else nature_palette(palette)
    return base


__all__ = [
    "PALETTE",
    "PALETTE_NMI_PASTEL",
    "DEFAULT_COLORS",
    "DEFAULT_COLORS_NMI_PASTEL",
    "set_nature_style",
    "nature_palette",
    "despine",
    "cycle_colors",
]
