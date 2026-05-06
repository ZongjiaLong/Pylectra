"""Trivial 'no PSS' implementation — native, zero dependencies on legacy code.

Adds no states and contributes ``Vss = 0`` to the exciter summing junction.
Equivalent to the legacy ``type3_disabled`` PSS but free of MATLAB-port
imports, so it can be used in fully native test rigs.
"""
from __future__ import annotations

import numpy as np

from pylectra.interfaces.pss import PSSModel
from pylectra.registry import register


@register("pss", "none")
class NoPSS(PSSModel):
    type_id = 3
    n_states = 0

    def init(self, Ppss_rows):
        n = Ppss_rows.shape[0] if Ppss_rows.size else 0
        # Match legacy convention: empty state, two columns reserved.
        Xpss0 = np.zeros((n, 0))
        Ppss0 = Ppss_rows.copy() if Ppss_rows.size else np.zeros((0, 0))
        return Xpss0, Ppss0

    def derivative(self, Xpss_rows, Xgen_rows, Ppss_rows):
        return np.zeros_like(Xpss_rows)
