"""4-state IEEE turbine-governor — native rewrite of legacy type 2.

State vector (per machine), shape ``(n, 4)``:

==  ====  =====================================
0   Pm    mechanical power output [pu]
1   P     intermediate state (lead-lag block)
2   x     governor state
3   z     servo position
==  ====  =====================================

Pgov layout (matching the legacy ``GovernorInit`` output, hence cols 1..9):

* col 1 : K       (gain)
* col 2 : T1      (lead-lag denominator)
* col 3 : T2      (lead-lag numerator)
* col 4 : T3      (servo time constant)
* col 5 : Pup     (rate-limit upper)
* col 6 : Pdown   (rate-limit lower)
* col 7 : Pmax    (output upper saturation)
* col 8 : Pmin    (output lower saturation)
* col 9 : P0      (steady-state power reference set during ``init``)

State equations
---------------

::

    dx/dt  = K · (−x/T1 + (1 − T2/T1)·(ω − ω_s))
    dP/dt  = x/T1 + (T2/T1)·(ω − ω_s)
    y      = (P0 − P − Pm) / T3                # raw rate signal
    y      = clip(y, Pdown, Pup)               # rate-limit
    dz/dt  = y                                 # servo
    dPm/dt = y if Pmin ≤ z ≤ Pmax else 0       # mechanical-power lock
"""
from __future__ import annotations

import numpy as np

from pylectra.interfaces.governor import GovernorModel
from pylectra.registry import register

from pylectra.core import freq as _f


@register("governor", "ieee_g")
class IEEETurbineGovernor(GovernorModel):
    type_id = 2
    n_states = 4

    def init(self, Pm0_rows, Pgov_rows, omega0_rows):
        n = Pgov_rows.shape[0]
        Xgov0 = np.zeros((n, 4))
        Pgov0 = np.zeros((n, max(Pgov_rows.shape[1] + 2, 10)))
        Pgov0[:, : Pgov_rows.shape[1]] = Pgov_rows
        if n == 0:
            return Xgov0, Pgov0

        Pm0 = np.asarray(Pm0_rows).ravel()
        K = Pgov_rows[:, 1]
        T1 = Pgov_rows[:, 2]
        T2 = Pgov_rows[:, 3]
        omega0 = np.asarray(omega0_rows).ravel()
        omegas = 2.0 * np.pi * float(_f.freq)

        P0 = K * (omegas - omega0)
        x0 = T1 * (1.0 - T2 / T1) * (omegas - omega0)

        Xgov0[:, 0] = Pm0
        Xgov0[:, 1] = P0      # P
        Xgov0[:, 2] = x0      # x
        Xgov0[:, 3] = Pm0     # z

        Pgov0[:, 9] = Pm0     # P0 reference stored for derivative.
        return Xgov0, Pgov0

    def derivative(self, Xgov_rows, Pgov_rows, Vgov_rows):
        F = np.zeros_like(Xgov_rows)
        n = Xgov_rows.shape[0]
        if n == 0:
            return F

        Pm = Xgov_rows[:, 0]
        P = Xgov_rows[:, 1]
        x = Xgov_rows[:, 2]
        z = Xgov_rows[:, 3]

        K = Pgov_rows[:, 1]
        T1 = Pgov_rows[:, 2]
        T2 = Pgov_rows[:, 3]
        T3 = Pgov_rows[:, 4]
        Pup = Pgov_rows[:, 5]
        Pdown = Pgov_rows[:, 6]
        Pmax = Pgov_rows[:, 7]
        Pmin = Pgov_rows[:, 8]
        P0 = Pgov_rows[:, 9]

        omega = np.asarray(Vgov_rows).ravel()
        omegas = 2.0 * np.pi * float(_f.freq)
        domega = omega - omegas

        dx = K * (-x / T1 + (1.0 - T2 / T1) * domega)
        dP = x / T1 + (T2 / T1) * domega
        y = (P0 - P - Pm) / T3
        y = np.clip(y, Pdown, Pup)

        dz = y.copy()
        dPm = np.where((z > Pmax) | (z < Pmin), 0.0, y)

        F[:, 0] = dPm
        F[:, 1] = dP
        F[:, 2] = dx
        F[:, 3] = dz
        return F
