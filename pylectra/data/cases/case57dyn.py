"""case57dyn - dynamic simulation data for the IEEE 57-bus test system.

Returns the canonical 7-tuple ``(gen, exc, pss, gov, freq, stepsize, stoptime)``.

Source of dynamic parameters
----------------------------
Synthesised typical-machine values consistent with PSAT ``d_057_dyn.m``
parameter ranges. The IEEE 57-bus benchmark is primarily a steady-state
test case; dynamic parameters reported in the literature are
implementation-specific. Values below match the convention used by Vittal
& Bergen (1986) and PSAT defaults: large slack machine at bus 1 plus six
generators / condensers with comparable parameters.

Convention (matches ``case39dyn``):

* ``H`` on system 100 MVA base; reactances on machine MVA base; time
  constants in seconds.
* ``x_l = 0.10`` placeholder (unused by the native engine).

Bus numbering follows ``pandapower.networks.case57`` post-``to_mpc``:
generators on buses 1, 2, 3, 6, 8, 9, 12.
"""
import numpy as np


def case57dyn():
    freq = 60.0
    stepsize = 0.001
    stoptime = 10.0

    # Generator: [genmodel excmodel pssmodel govmodel bus unit H r_a x'_d x'_q x_d x_q T'_do T'_qo x_l]
    gen = np.array([
        # bus 1: slack (large unit)
        [2, 3, 3, 1,  1, 1, 12.0, 0, 0.18, 0.28, 1.25, 1.18, 6.5, 0.5, 0.10],
        # buses 2, 3, 6, 8, 9, 12: smaller generators / condensers
        [2, 3, 3, 1,  2, 2,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  3, 3,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  6, 4,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  8, 5,  8.0, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  9, 6,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1, 12, 7, 10.0, 0, 0.18, 0.28, 1.20, 1.15, 6.3, 0.4, 0.10],
    ], dtype=float)

    _gen_buses = (1, 2, 3, 6, 8, 9, 12)

    exc = np.array([
        [b, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0] for b in _gen_buses
    ], dtype=float)

    gov = np.array([
        [i, 0, 0, 0, 0, 0, 0, 0, 0] for i in range(1, len(_gen_buses) + 1)
    ], dtype=float)

    pss = np.array([
        [b, i, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        for i, b in enumerate(_gen_buses, start=1)
    ], dtype=float)

    return gen, exc, pss, gov, freq, stepsize, stoptime
