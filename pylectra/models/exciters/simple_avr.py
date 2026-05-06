"""Native first-order AVR exciter (clean rewrite of legacy type 3).

Single-state automatic voltage regulator with cosine-projected terminal
voltage feedback::

    dEfd/dt = (−Efd − μ·k·|U|·cos(δ − θ) + L) / Tv

Pexc layout (cols 1..6 used):

* col 1 : Tv          (regulator time constant, s)
* col 2 : μ           (gain modifier)
* col 3 : k           (regulator gain)
* col 4 : Efd_min     (lower limit, currently informational only)
* col 5 : Efd_max     (upper limit; legacy MATLAB code used col 4 for both)
* col 6 : L           (steady-state forcing computed during ``init``)

State ``Xexc[:, 0] = Efd``.
"""
from __future__ import annotations

import numpy as np

from pylectra.interfaces.exciter import ExciterModel
from pylectra.registry import register


@register("exciter", "simple_avr")
class SimpleAVR(ExciterModel):
    """Native rewrite of the legacy type-3 first-order AVR."""

    type_id = 3
    n_states = 1

    # --------- init ---------------------------------------------------
    def init(self, Efd0_rows, Xgen0_rows, Pexc_rows, Vexc_rows):
        n = Pexc_rows.shape[0]
        Xexc0 = np.zeros((n, 1))
        # Pad Pexc to ≥7 cols so col 6 (L) always exists.
        Pexc0 = np.zeros((n, max(Pexc_rows.shape[1], 7)))
        Pexc0[:, : Pexc_rows.shape[1]] = Pexc_rows

        if n == 0:
            return Xexc0, Pexc0

        Efd0 = Efd0_rows
        mu = Pexc_rows[:, 2]
        k = Pexc_rows[:, 3]

        Vexc_arr = np.asarray(Vexc_rows)
        U = Vexc_arr[:, 0] if Vexc_arr.ndim == 2 else Vexc_arr
        V = np.abs(U)
        theta = np.angle(U)
        delta = Xgen0_rows[:, 0]

        L = Efd0 + mu * k * V * np.cos(delta - theta)
        Pexc0[:, 6] = L
        Xexc0[:, 0] = Efd0
        return Xexc0, Pexc0

    # --------- derivative --------------------------------------------
    def derivative(self, Xexc_rows, Xgen_rows, Pexc_rows, Vexc_rows, Vpss_rows):
        F = np.zeros_like(Xexc_rows)
        if Xexc_rows.shape[0] == 0:
            return F

        Efd = Xexc_rows[:, 0]
        Tv = Pexc_rows[:, 1]
        mu = Pexc_rows[:, 2]
        k = Pexc_rows[:, 3]
        L = Pexc_rows[:, 6]

        Vexc_arr = np.asarray(Vexc_rows)
        U = Vexc_arr[:, 0] if Vexc_arr.ndim == 2 else Vexc_arr
        V = np.abs(U)
        theta = np.angle(U)
        delta = Xgen_rows[:, 0]

        F[:, 0] = (-Efd - mu * k * V * np.cos(delta - theta) + L) / Tv
        return F
