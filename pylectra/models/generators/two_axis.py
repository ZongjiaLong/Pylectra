"""Native 4th-order two-axis synchronous generator.

This is a clean Pythonic reference implementation of the same physics as the
legacy ``Models.Generators.Generator`` (model type 2), but with no
dependence on legacy code.  It is registered under the name ``"two_axis"``.

State vector (per machine) — shape ``(n_gen, 4)``:

==  ====  ===========================================
0   δ     rotor angle [rad]
1   ω     electrical angular speed [rad/s]
2   Eq′   transient EMF on q-axis [pu]
3   Ed′   transient EMF on d-axis [pu]
==  ====  ===========================================

Parameter columns of ``Pgen_rows`` follow the historical layout used by
the rest of the codebase so the same dynamic-data files work::

    col  6 : H        (inertia constant)
    col  8 : xd'      (d-axis transient reactance)
    col  9 : xq'      (q-axis transient reactance)
    col 10 : xd       (d-axis synchronous reactance)
    col 11 : xq       (q-axis synchronous reactance)
    col 12 : Td0'     (d-axis open-circuit time constant)
    col 13 : Tq0'     (q-axis open-circuit time constant)

State equations
---------------

::

    dδ/dt   = ω − ω_s
    dω/dt   = (π·f / H) · (Pm − Pe)              (D = 0 here)
    dEq'/dt = (1 / Td0') · (Efd − Eq' + (xd − xd')·Id)
    dEd'/dt = (1 / Tq0') · (−Ed' − (xq − xq')·Iq)

Stator algebraic relations (in machine d/q frame referenced to δ)::

    vd = −|U| · sin(δ − θ)
    vq =  |U| · cos(δ − θ)
    Id = (vq − Eq') / xd'
    Iq = −(vd − Ed') / xq'
    Pe = Eq'·Iq + Ed'·Id + (xd' − xq')·Id·Iq
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register

from pylectra.core.idx import idx_gen


@register("generator", "two_axis")
class TwoAxisGenerator(GeneratorModel):
    """4th-order two-axis synchronous machine — native reference impl."""

    type_id = 2
    n_states = 4

    # --------------------------------------------------------------- init
    def init(
        self,
        Pgen_rows: np.ndarray,
        U_rows: np.ndarray,
        gen_rows: np.ndarray,
        baseMVA: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        (GEN_BUS, PG, QG, *_rest) = idx_gen()

        n = Pgen_rows.shape[0]
        Xgen0 = np.zeros((n, 4))
        Efd0 = np.zeros(n)

        if n == 0:
            return Efd0, Xgen0

        xd_tr = Pgen_rows[:, 8]
        xq_tr = Pgen_rows[:, 9]
        xd = Pgen_rows[:, 10]
        xq = Pgen_rows[:, 11]

        # Steady state: ω = ω_s.  Read the system frequency from the
        # pylectra-native holder (the legacy engine mirrors it on Loaddyn).
        from pylectra.core import freq as _f

        omega0 = np.full(n, 2.0 * np.pi * float(_f.freq))

        Ia0 = (gen_rows[:, PG] - 1j * gen_rows[:, QG]) / np.conj(U_rows) / baseMVA
        phi0 = np.angle(Ia0)

        Eq0 = U_rows + 1j * xq * Ia0
        delta0 = np.angle(Eq0)

        Id0 = -np.abs(Ia0) * np.sin(delta0 - phi0)
        Iq0 = np.abs(Ia0) * np.cos(delta0 - phi0)

        Efd0[:] = np.abs(Eq0) - (xd - xq) * Id0
        Eq_tr0 = Efd0 + (xd - xd_tr) * Id0
        Ed_tr0 = -(xq - xq_tr) * Iq0

        Xgen0[:, 0] = delta0
        Xgen0[:, 1] = omega0
        Xgen0[:, 2] = Eq_tr0
        Xgen0[:, 3] = Ed_tr0
        return Efd0, Xgen0

    # ---------------------------------------------------------- derivative
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
        Eq_tr = Xgen_rows[:, 2]
        Ed_tr = Xgen_rows[:, 3]

        H = Pgen_rows[:, 6]
        xd_tr = Pgen_rows[:, 8]
        xq_tr = Pgen_rows[:, 9]
        xd = Pgen_rows[:, 10]
        xq = Pgen_rows[:, 11]
        Td0_tr = Pgen_rows[:, 12]
        Tq0_tr = Pgen_rows[:, 13]

        Id = Vgen_rows[:, 0]
        Iq = Vgen_rows[:, 1]
        Pe = Vgen_rows[:, 2]

        Efd = Xexc_rows[:, 0]
        Pm = Xgov_rows[:, 0]

        F = np.empty_like(Xgen_rows)
        F[:, 0] = omega - omegas
        F[:, 1] = (np.pi * float(freq) / H) * (Pm - Pe)   # damping D = 0
        F[:, 2] = (Efd - Eq_tr + (xd - xd_tr) * Id) / Td0_tr
        F[:, 3] = (-Ed_tr - (xq - xq_tr) * Iq) / Tq0_tr
        return F

    # ----------------------------------------------------------- currents
    def currents(
        self,
        Xgen_rows: np.ndarray,
        Pgen_rows: np.ndarray,
        Ubus_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        delta = Xgen_rows[:, 0]
        Eq_tr = Xgen_rows[:, 2]
        Ed_tr = Xgen_rows[:, 3]
        xd_tr = Pgen_rows[:, 8]
        xq_tr = Pgen_rows[:, 9]

        theta = np.angle(Ubus_rows)
        absU = np.abs(Ubus_rows)
        vd = -absU * np.sin(delta - theta)
        vq = absU * np.cos(delta - theta)

        Id = (vq - Eq_tr) / xd_tr
        Iq = -(vd - Ed_tr) / xq_tr
        Pe = Eq_tr * Iq + Ed_tr * Id + (xd_tr - xq_tr) * Id * Iq
        return Id, Iq, Pe
