"""Classical 2nd-order swing-equation generator.

Constant flux behind transient reactance: the only state variables are the
rotor angle δ and the electrical angular speed ω.  Suitable for first-swing
stability studies where flux dynamics can be neglected; it is also the
canonical pedagogical model in textbooks (Kundur §3.4, Sauer–Pai §3.6).

State vector (per machine) — shape ``(n_gen, 2)``:

==  ====  ===========================================
0   δ     rotor angle [rad]
1   ω     electrical angular speed [rad/s]
==  ====  ===========================================

Required parameters from ``Pgen_rows``:

* col  6 : H        (inertia constant, MWs/MVA)
* col  8 : xd'      (transient reactance behind which |E'| is held constant)

State equations
---------------

::

    dδ/dt   = ω − ω_s
    dω/dt   = (π·f / H) · (Pm − Pe)

with ``Pe = Re{ E' · conj(I) } = (|E'|·|U|/xd') · sin(δ − θ)`` and
``E' = |E'| · ∠δ`` held constant.

To keep a uniform 4-column state layout with the rest of the codebase, the
output array is widened to four columns: ``[δ, ω, |E'|, 0]``.  ``|E'|`` and
the unused 4th column are constants for this model.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register

from pylectra.core.idx import idx_gen


@register("generator", "classical")
class ClassicalGenerator(GeneratorModel):
    """2nd-order swing equation; n_states is reported as 4 to keep the
    DynamicSystem state layout uniform across model types (cols 2/3 unused).
    """

    type_id = 1
    n_states = 4  # uniform layout; cols 2 (|E'|) and 3 (0) are constants.

    def init(
        self,
        Pgen_rows: np.ndarray,
        U_rows: np.ndarray,
        gen_rows: np.ndarray,
        baseMVA: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        (GEN_BUS, PG, QG, *_rest) = idx_gen()
        n = Pgen_rows.shape[0]
        if n == 0:
            return np.zeros(n), np.zeros((n, 4))

        xd_tr = Pgen_rows[:, 8]
        from pylectra.core import freq as _f

        omega0 = np.full(n, 2.0 * np.pi * float(_f.freq))
        Ia0 = (gen_rows[:, PG] - 1j * gen_rows[:, QG]) / np.conj(U_rows) / baseMVA

        # Voltage behind transient reactance.
        Eprime = U_rows + 1j * xd_tr * Ia0
        delta0 = np.angle(Eprime)
        Eabs = np.abs(Eprime)

        Xgen0 = np.zeros((n, 4))
        Xgen0[:, 0] = delta0
        Xgen0[:, 1] = omega0
        Xgen0[:, 2] = Eabs
        # col 3 unused
        Efd0 = Eabs.copy()  # treated as the constant field reference
        return Efd0, Xgen0

    def derivative(
        self,
        Xgen_rows: np.ndarray,
        Xexc_rows: np.ndarray,
        Xgov_rows: np.ndarray,
        Pgen_rows: np.ndarray,
        Vgen_rows: np.ndarray,
        freq: float,
    ) -> np.ndarray:
        omegas = 2.0 * np.pi * float(freq)
        omega = Xgen_rows[:, 1]
        H = Pgen_rows[:, 6]
        Pe = Vgen_rows[:, 2]
        Pm = Xgov_rows[:, 0]

        F = np.zeros_like(Xgen_rows)
        F[:, 0] = omega - omegas
        F[:, 1] = (np.pi * float(freq) / H) * (Pm - Pe)
        # cols 2, 3 stay zero (constants)
        return F

    def currents(
        self,
        Xgen_rows: np.ndarray,
        Pgen_rows: np.ndarray,
        Ubus_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        delta = Xgen_rows[:, 0]
        Eabs = Xgen_rows[:, 2]
        xd_tr = Pgen_rows[:, 8]

        theta = np.angle(Ubus_rows)
        absU = np.abs(Ubus_rows)
        # Eprime in rectangular: Ex + jEy
        Ex = Eabs * np.cos(delta)
        Ey = Eabs * np.sin(delta)
        Ux = absU * np.cos(theta)
        Uy = absU * np.sin(theta)
        # Stator current in network frame: I = (E' − U) / (j xd')
        Ix = (Ey - Uy) / xd_tr
        Iy = -(Ex - Ux) / xd_tr

        # Project to d/q for compatibility with downstream code.
        Id = -Ix * np.sin(delta) + Iy * np.cos(delta)
        Iq = Ix * np.cos(delta) + Iy * np.sin(delta)
        Pe = Ex * Ix + Ey * Iy
        return Id, Iq, Pe
