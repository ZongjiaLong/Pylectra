"""Phase 7 smoke tests: every registered plot plugin renders without error.

Uses the Phase 0 golden batch outputs as input data, plus a pandapower
case for the topology plot.  We don't pixel-compare images — we just
verify each plugin's ``render`` is wired and the resulting Figure has
non-empty axes.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for CI

import matplotlib.pyplot as plt
import pytest

import pylectra  # noqa: F401  (triggers discovery)
from pylectra.registry import get, list_plugins
from pylectra.plotting import render

REPO = Path(__file__).resolve().parents[2]
BATCH_GOLDEN = REPO / "tests" / "golden" / "batch_case39_seed42_count5"
SAMPLE_H5 = BATCH_GOLDEN / "sample_000000.h5"
METADATA = BATCH_GOLDEN / "metadata.parquet"

# Minimum set every plot plugin tested below must belong to.
EXPECTED_PLUGINS = {
    "rotor_angles", "speeds", "voltages", "efds", "overview",
    "topology", "acceptance", "histogram", "violin", "heatmap",
}


def teardown_function(_):
    plt.close("all")


# --------------------------------------------------------------- registration
def test_all_expected_plot_plugins_registered():
    names = set(list_plugins("plot")["plot"])
    missing = EXPECTED_PLUGINS - names
    assert not missing, f"missing plot plugins: {missing}"


# -------------------------------------------------------- single-result plots
@pytest.mark.parametrize("name", ["rotor_angles", "speeds", "voltages",
                                  "efds", "overview"])
def test_single_result_plot_renders(name):
    if not SAMPLE_H5.exists():
        pytest.skip("golden sample h5 not available")
    fig = render(name, SAMPLE_H5)
    assert fig is not None
    # All defined plots create at least one Axes with data.
    axes = fig.get_axes()
    assert len(axes) >= 1
    # At least one axis has at least one line/patch/image drawn.
    has_artist = any(
        ax.lines or ax.patches or ax.images or ax.collections for ax in axes
    )
    assert has_artist, f"plot {name!r} produced empty axes"


# -------------------------------------------------------------- batch plots
def test_acceptance_plot_renders():
    if not METADATA.exists():
        pytest.skip("golden metadata not available")
    fig = render("acceptance", METADATA)
    assert fig.get_axes()


def test_histogram_plot_renders():
    if not METADATA.exists():
        pytest.skip("golden metadata not available")
    fig = render("histogram", METADATA, column="filter_voltage_range_metric")
    assert fig.get_axes()


def test_violin_plot_renders():
    if not METADATA.exists():
        pytest.skip("golden metadata not available")
    fig = render("violin", METADATA, column="filter_angle_stability_metric")
    assert fig.get_axes()


# ---------------------------------------------------------------- topology
def test_topology_plot_renders_from_case_name():
    """Pass the case name string; plot_network resolves it via NetworkCase."""
    fig = render("topology", "case39")
    assert fig.get_axes()


# --------------------------------------------------- input_kind metadata sane
def test_each_plugin_has_consistent_input_kind():
    for name in EXPECTED_PLUGINS:
        plugin = get("plot", name)()
        assert plugin.input_kind in {"single", "batch", "case", "sweep",
                                     "small_signal"}
