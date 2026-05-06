"""Constant-Efd exciter — native rewrite of the legacy type 4.

State ``Xexc[:, 0] = Efd``; ``dEfd/dt = 0``.  Useful as a zero-dynamic
baseline (open-loop) and for unit-tests of the surrounding loop.
"""
from __future__ import annotations

import numpy as np

from pylectra.interfaces.exciter import ExciterModel
from pylectra.registry import register


@register("exciter", "constant")
class ConstantExciter(ExciterModel):
    type_id = 4
    n_states = 1

    def init(self, Efd0_rows, Xgen0_rows, Pexc_rows, Vexc_rows):
        n = Pexc_rows.shape[0]
        Xexc0 = np.zeros((n, 1))
        if n:
            Xexc0[:, 0] = Efd0_rows
        # Mirror legacy ExciterInit: emit Pexc with at least 7 cols.
        Pexc0 = np.zeros((n, max(Pexc_rows.shape[1], 7)))
        Pexc0[:, : Pexc_rows.shape[1]] = Pexc_rows
        return Xexc0, Pexc0

    def derivative(self, Xexc_rows, Xgen_rows, Pexc_rows, Vexc_rows, Vpss_rows):
        return np.zeros_like(Xexc_rows)
