"""Nature-grade plotting helpers for ``pylectra`` outputs.

Sub-package layout:

* :mod:`pylectra.plotting.style`        — rcParams + palettes
* :mod:`pylectra.plotting.io`           — figure save / journal sizing
* :mod:`pylectra.plotting.time_series`  — single-result time-series plots
* :mod:`pylectra.plotting.topology`     — network schematic
* :mod:`pylectra.plotting.batch_stats`  — distributions over a sample directory

The high-level :func:`render_plot` dispatcher is what
``python -m pylectra plot ...`` calls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from matplotlib.figure import Figure

from .style import (
    PALETTE,
    PALETTE_NMI_PASTEL,
    DEFAULT_COLORS,
    DEFAULT_COLORS_NMI_PASTEL,
    set_nature_style,
    nature_palette,
    despine,
)
from .io import JOURNAL_WIDTHS_MM, journal_figsize, save_figure
from .time_series import (
    plot_rotor_angles,
    plot_speeds,
    plot_voltage_magnitudes,
    plot_efds,
    plot_overview,
)
from .topology import plot_network
from .batch_stats import (
    load_metadata,
    plot_acceptance_summary,
    plot_metric_histogram,
    plot_metric_violin,
    plot_metric_heatmap,
)
from . import plugins  # noqa: F401  (registers all builtin plots in the registry)


_PLOT_KINDS = {
    # name → (callable, source-kind)
    # source-kind: "result" (single .h5/.npz/yaml), "metadata" (sample dir),
    #              "case" (case name or yaml referencing a case_pf)
    "rotor_angles":       (plot_rotor_angles, "result"),
    "speeds":             (plot_speeds, "result"),
    "voltages":           (plot_voltage_magnitudes, "result"),
    "voltage_magnitudes": (plot_voltage_magnitudes, "result"),
    "efds":               (plot_efds, "result"),
    "overview":           (plot_overview, "result"),
    "topology":           (plot_network, "case"),
    "network":            (plot_network, "case"),
    "acceptance":         (plot_acceptance_summary, "metadata"),
    "histogram":          (plot_metric_histogram, "metadata"),
    "violin":             (plot_metric_violin, "metadata"),
    "heatmap":            (plot_metric_heatmap, "metadata"),
}


def list_plot_kinds() -> list[str]:
    """Return the canonical list of ``--type`` values accepted by the CLI."""
    # de-dup aliases preserving insertion order
    seen = set()
    out: list[str] = []
    for name in _PLOT_KINDS:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _resolve_source_for_result(source: Union[str, Path]) -> Union[str, Path]:
    """If ``source`` is a YAML config, run it once and return a result file
    path; otherwise pass through.

    Running the simulation here makes the CLI ergonomic: users can do
    ``pylectra plot examples/single_case39.yaml --type rotor_angles -o foo.pdf``
    without having to pre-run the simulation themselves.
    """
    p = Path(source)
    if p.suffix.lower() in {".yaml", ".yml"}:
        from pylectra.config import ExperimentConfig
        from pylectra.runners.single import SingleRunner

        cfg = ExperimentConfig.from_yaml(p)
        if cfg.mode != "single":
            raise ValueError(
                f"cannot derive a single-result plot from a {cfg.mode!r} config; "
                f"point to a sample .h5/.npz file instead"
            )
        cfg.plot = False
        runner = SingleRunner(cfg)
        return runner.run().result  # SimulationResult instance
    return source


def _resolve_source_for_case(source: Union[str, Path]) -> Any:
    """If ``source`` is a YAML config, extract its ``case_pf``; otherwise
    treat it as a case name / path consumable by :class:`NetworkCase`."""
    p = Path(source)
    if p.suffix.lower() in {".yaml", ".yml"}:
        from pylectra.config import ExperimentConfig

        cfg = ExperimentConfig.from_yaml(p)
        return cfg.case_pf
    return str(source)


def render(name: str, data: Any, **kwargs):
    """Plugin-style dispatch: render a plot by registered name.

    Mirrors the ``@register("plot", ...)`` lookup used by the rest of the
    framework — useful in notebooks where you want a quick figure without
    going through ``render_plot``'s CLI-oriented file-IO path.

    Examples
    --------
    >>> from pylectra import run
    >>> from pylectra.plotting import render
    >>> res = run("examples/single_case39.yaml")
    >>> fig = render("rotor_angles", res.result, gen_indices=[0, 1, 2])
    >>> fig.savefig("angles.pdf")
    """
    from pylectra.registry import get
    plugin_cls = get("plot", name)
    return plugin_cls().render(data, **kwargs)


def render_plot(
    kind: str,
    source: Union[str, Path],
    output: Union[str, Path],
    *,
    formats: Optional[list[str]] = None,
    plot_kwargs: Optional[Dict[str, Any]] = None,
) -> list[Path]:
    """Render a named plot to ``output`` (and any extra ``formats``).

    Returns the list of files actually written.
    """
    if kind not in _PLOT_KINDS:
        raise KeyError(
            f"unknown plot kind {kind!r}; choose from {list_plot_kinds()}"
        )
    fn, source_kind = _PLOT_KINDS[kind]
    plot_kwargs = dict(plot_kwargs or {})

    if source_kind == "result":
        resolved = _resolve_source_for_result(source)
        fig: Figure = fn(resolved, **plot_kwargs)
    elif source_kind == "case":
        case = _resolve_source_for_case(source)
        fig = fn(case, **plot_kwargs)
    elif source_kind == "metadata":
        # batch_stats helpers take the metadata file/dir directly
        fig = fn(source, **plot_kwargs)
    else:  # pragma: no cover
        raise RuntimeError(f"internal: unknown source_kind {source_kind!r}")

    return save_figure(fig, output, formats=formats, close=True)


__all__ = [
    "PALETTE",
    "PALETTE_NMI_PASTEL",
    "DEFAULT_COLORS",
    "DEFAULT_COLORS_NMI_PASTEL",
    "JOURNAL_WIDTHS_MM",
    "set_nature_style",
    "nature_palette",
    "despine",
    "journal_figsize",
    "save_figure",
    "plot_rotor_angles",
    "plot_speeds",
    "plot_voltage_magnitudes",
    "plot_efds",
    "plot_overview",
    "plot_network",
    "load_metadata",
    "plot_acceptance_summary",
    "plot_metric_histogram",
    "plot_metric_violin",
    "plot_metric_heatmap",
    "render_plot",
    "render",
    "list_plot_kinds",
]
