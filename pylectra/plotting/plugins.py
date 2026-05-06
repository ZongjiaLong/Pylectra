"""Plot plugin registrations.

Each existing plotting helper in :mod:`pylectra.plotting` is wrapped in a
:class:`pylectra.interfaces.plot.PlotPlugin` subclass and registered under the
``"plot"`` registry category, so the framework's plugin machinery can
enumerate, dispatch, and document plots uniformly with every other plugin
type.

This is a thin re-registration layer — the actual drawing code remains in
``time_series.py``, ``topology.py``, ``batch_stats.py``.  Adding a new plot
later is the same workflow as any other plugin: drop a file in
``pylectra/plotting/``, decorate a class with
``@register("plot", "<name>")``, restart, done.
"""
from __future__ import annotations

from typing import Any, Optional

from pylectra.interfaces.plot import PlotPlugin
from pylectra.registry import register

from .time_series import (
    plot_rotor_angles,
    plot_speeds,
    plot_voltage_magnitudes,
    plot_efds,
    plot_overview,
)
from .topology import plot_network
from .batch_stats import (
    plot_acceptance_summary,
    plot_metric_histogram,
    plot_metric_violin,
    plot_metric_heatmap,
)


# ----------------------------------------------------------- single result
@register("plot", "rotor_angles")
class RotorAnglesPlot(PlotPlugin):
    name = "rotor_angles"
    input_kind = "single"

    def render(self, data, ax=None, **kwargs):
        return plot_rotor_angles(data, **kwargs)

    def expected_inputs(self) -> dict[str, Any]:
        return {
            "relative": (bool, True, "subtract centre-of-inertia angle"),
            "gen_indices": (Optional[list], None, "generators to plot (default: all)"),
            "palette": (str, "default", "color palette name"),
            "title": (Optional[str], None, "axes title"),
            "figsize": (Optional[tuple], None, "(width_in, height_in)"),
        }


@register("plot", "speeds")
class SpeedsPlot(PlotPlugin):
    name = "speeds"
    input_kind = "single"

    def render(self, data, ax=None, **kwargs):
        return plot_speeds(data, **kwargs)


@register("plot", "voltages")
class VoltagesPlot(PlotPlugin):
    name = "voltages"
    input_kind = "single"

    def render(self, data, ax=None, **kwargs):
        return plot_voltage_magnitudes(data, **kwargs)


@register("plot", "efds")
class EfdsPlot(PlotPlugin):
    name = "efds"
    input_kind = "single"

    def render(self, data, ax=None, **kwargs):
        return plot_efds(data, **kwargs)


@register("plot", "overview")
class OverviewPlot(PlotPlugin):
    name = "overview"
    input_kind = "single"

    def render(self, data, ax=None, **kwargs):
        return plot_overview(data, **kwargs)


# --------------------------------------------------------------- topology
@register("plot", "topology")
class TopologyPlot(PlotPlugin):
    name = "topology"
    input_kind = "case"

    def render(self, data, ax=None, **kwargs):
        return plot_network(data, **kwargs)


# ------------------------------------------------------------- batch stats
@register("plot", "acceptance")
class AcceptancePlot(PlotPlugin):
    name = "acceptance"
    input_kind = "batch"

    def render(self, data, ax=None, **kwargs):
        return plot_acceptance_summary(data, **kwargs)


@register("plot", "histogram")
class HistogramPlot(PlotPlugin):
    name = "histogram"
    input_kind = "batch"

    def render(self, data, ax=None, *, column: str, **kwargs):
        return plot_metric_histogram(data, column=column, **kwargs)

    def expected_inputs(self) -> dict[str, Any]:
        return {
            "column": (str, ..., "metric column to histogram (required)"),
            "bins": (int, 30, "number of bins"),
            "color": (Optional[str], None, "single color override"),
            "title": (Optional[str], None, "axes title"),
        }


@register("plot", "violin")
class ViolinPlot(PlotPlugin):
    name = "violin"
    input_kind = "batch"

    def render(self, data, ax=None, *, column: str, **kwargs):
        return plot_metric_violin(data, column=column, **kwargs)


@register("plot", "heatmap")
class HeatmapPlot(PlotPlugin):
    name = "heatmap"
    input_kind = "batch"

    def render(self, data, ax=None, *, column: str, rows: str, cols: str, **kwargs):
        return plot_metric_heatmap(data, column=column, rows=rows, cols=cols, **kwargs)


__all__: list[str] = []  # all access goes through the registry
