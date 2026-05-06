"""Constant-power governor — native rewrite of legacy type 1.

State ``Xgov[:, 0] = Pm``; ``dPm/dt = 0``.  The state vector is widened to
4 columns to match the uniform layout enforced by
:class:`pylectra.core.system.DynamicSystem`; columns 1..3 are unused.
"""
from __future__ import annotations

import numpy as np

from pylectra.interfaces.governor import GovernorModel
from pylectra.registry import register


@register("governor", "constant_power")
class ConstantPowerGovernor(GovernorModel):
    type_id = 1
    n_states = 4  # uniform layout; only col 0 carries Pm.

    def init(self, Pm0_rows, Pgov_rows, omega0_rows):
        n = Pgov_rows.shape[0]
        Xgov0 = np.zeros((n, 4))
        if n:
            Xgov0[:, 0] = np.asarray(Pm0_rows).ravel()
        # Pad Pgov to ≥10 cols (legacy GovernorInit adds two columns).
        Pgov0 = np.zeros((n, max(Pgov_rows.shape[1] + 2, 10)))
        Pgov0[:, : Pgov_rows.shape[1]] = Pgov_rows
        return Xgov0, Pgov0

    def derivative(self, Xgov_rows, Pgov_rows, Vgov_rows):
        return np.zeros_like(Xgov_rows)
