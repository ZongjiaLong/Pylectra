"""Figure save / size helpers respecting Nature submission guidelines.

* ``single`` column = 89 mm wide (~3.5 in)
* ``double`` column = 183 mm wide (~7.2 in)
* ``page``   width  = 247 mm (~9.7 in) — for poster-style multi-panels

These match the Nature ``column_width_mm`` quoted in the journal's
"Final figure submission guide".

The :func:`save_figure` helper saves at vector PDF + raster PNG by default
(both useful for a publication round-trip), with text kept as live ``<text>``
elements in SVG/PDF (``svg.fonttype = 'none'`` set in :mod:`pylectra.plotting.style`).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
from matplotlib.figure import Figure


_MM_PER_INCH = 25.4

#: Journal-standard widths in millimetres.
JOURNAL_WIDTHS_MM = {
    "single": 89.0,
    "double": 183.0,
    "page":   247.0,
}


def journal_figsize(
    width: Union[str, float] = "single",
    aspect: float = 0.62,
    height: Optional[float] = None,
) -> Tuple[float, float]:
    """Return ``(w_in, h_in)`` for a journal-width figure.

    Parameters
    ----------
    width:
        Either a name from :data:`JOURNAL_WIDTHS_MM` or an explicit width
        in millimetres.
    aspect:
        Height / width ratio.  ``0.62`` ≈ golden ratio, the Nature default
        for line plots.  Ignored if ``height`` is provided.
    height:
        Explicit height in inches (overrides ``aspect``).
    """
    if isinstance(width, str):
        if width not in JOURNAL_WIDTHS_MM:
            raise KeyError(
                f"unknown journal width {width!r}; choose from "
                f"{sorted(JOURNAL_WIDTHS_MM)} or pass a float in mm"
            )
        w_mm = JOURNAL_WIDTHS_MM[width]
    else:
        w_mm = float(width)
    w_in = w_mm / _MM_PER_INCH
    h_in = float(height) if height is not None else w_in * float(aspect)
    return (w_in, h_in)


def save_figure(
    fig: Figure,
    path: Union[str, os.PathLike],
    *,
    formats: Optional[Sequence[str]] = None,
    dpi: int = 600,
    pad: float = 1.5,
    bbox_inches: str = "tight",
    close: bool = False,
) -> list[Path]:
    """Save ``fig`` to one or more formats.

    Parameters
    ----------
    fig:
        Figure to save.
    path:
        Output path.  If ``formats`` is None, the file extension is used
        (with ``.pdf`` falling back to ``.pdf`` only — no PNG twin).  If
        ``formats`` is provided, the extension on ``path`` is stripped and
        each format produces ``path.<fmt>``.
    formats:
        Iterable of extensions like ``["pdf", "png"]`` or ``["svg"]``.
    dpi:
        Raster DPI.  Defaults to 600 (Nature minimum 300, but 600 reproduces
        well on print + screen).
    pad:
        ``tight_layout`` pad applied before saving.
    bbox_inches:
        Passed straight through to :meth:`matplotlib.figure.Figure.savefig`.
    close:
        If True, ``plt.close(fig)`` after saving (handy in batch scripts).

    Returns
    -------
    list of paths actually written.
    """
    fig.tight_layout(pad=float(pad))
    base = Path(path)
    base.parent.mkdir(parents=True, exist_ok=True)

    if formats is None:
        suffix = base.suffix.lstrip(".") or "pdf"
        targets: Iterable[Tuple[Path, str]] = [(base, suffix)]
    else:
        stem = base.with_suffix("")
        targets = [(stem.with_suffix(f".{fmt.lstrip('.')}"), fmt.lstrip("."))
                   for fmt in formats]

    saved: list[Path] = []
    for target_path, fmt in targets:
        # SVG/PDF do not need DPI (vector); raster formats do.
        save_kwargs = {"bbox_inches": bbox_inches}
        if fmt.lower() in {"png", "jpg", "jpeg", "tiff"}:
            save_kwargs["dpi"] = int(dpi)
        fig.savefig(target_path, format=fmt, **save_kwargs)
        saved.append(target_path)

    if close:
        plt.close(fig)
    return saved


__all__ = ["JOURNAL_WIDTHS_MM", "journal_figsize", "save_figure"]
