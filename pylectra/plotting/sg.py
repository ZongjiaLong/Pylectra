"""Native ``PlotSG`` — quick-look matplotlib plots of a dynamic-sim trajectory.

Direct port of ``pylectra/_legacy/Auxiliary/PlotSG.py``. Only used by
:class:`pylectra.runners.single.SingleRunner` after the native engines /
torch backend complete a run, mirroring the legacy ``plot=True`` behaviour
of MatDyn's ``rundyn``.
"""
from __future__ import annotations

import numpy as np


def plot_sg(n, Time, Voltages, Efds, Angles, Speeds, Eq_trs, Ed_trs, Tes, TM, Vss) -> None:
    """Render the standard 5-panel single-generator dynamic-sim plot set."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping plots.")
        return

    Angles = Angles[:n]
    Speeds = Speeds[:n]
    Eq_trs = Eq_trs[:n]
    Ed_trs = Ed_trs[:n]
    Tes = Tes[:n]
    TM = TM[:n]
    Vss = Vss[:n]
    Efds = Efds[:n]
    Voltages = Voltages[:n]
    Time = Time[:n]

    plt.close("all")

    def _plot(y, ylab):
        fig, ax = plt.subplots()
        ax.plot(Time, y, linewidth=1)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(ylab)
        ax.set_xlim(0, float(Time[-1]))
        fig.tight_layout()

    _plot(Angles, r"$\delta$ [deg]")
    _plot(Speeds, r"$\omega_r$ [p.u.]")
    _plot(Tes, r"$T_e$ [p.u.]")
    _plot(np.abs(Voltages), r"$V_{bus}$ [p.u.]")
    _plot(Efds, r"$E_{fd}$ [p.u.]")
    plt.show()


__all__ = ["plot_sg"]
