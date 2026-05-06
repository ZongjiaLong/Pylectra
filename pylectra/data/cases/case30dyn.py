"""case30dyn - dynamic simulation data for the IEEE 30-bus test system.

Returns the canonical 7-tuple ``(gen, exc, pss, gov, freq, stepsize, stoptime)``.

Source of dynamic parameters
----------------------------
Synthesised from typical synchronous-machine values used in Pai,
*Energy Function Analysis for Power System Stability* (Kluwer 1989) for the
IEEE 30 test system, cross-checked with PSAT ``d_030_dyn.m`` ranges.

The IEEE 30-bus benchmark does not ship a single canonical dynamic data
set; the values below follow the common academic-literature convention:

* Bus 1: large slack synchronous machine (~260 MW rating).
* Buses 2, 5, 8, 11, 13: smaller generators / synchronous condensers
  with near-identical parameters.

Convention (matches ``case39dyn``):

* ``H`` on system 100 MVA base; reactances on machine MVA base; time
  constants in seconds.
* ``x_l`` is the customary 0.10 placeholder (engine does not consume it).

Bus numbering follows ``pandapower.networks.case_ieee30`` post-``to_mpc``:
generators on buses 1, 2, 5, 8, 11, 13.
"""
import numpy as np


def case30dyn():
    freq = 60.0
    stepsize = 0.001
    stoptime = 10.0

    # Generator: [genmodel excmodel pssmodel govmodel bus unit H r_a x'_d x'_q x_d x_q T'_do T'_qo x_l]
    gen = np.array([
        # bus 1: slack machine (largest unit)
        [2, 3, 3, 1,  1, 1, 10.0, 0, 0.20, 0.30, 1.30, 1.20, 6.0, 0.5, 0.10],
        # buses 2, 5, 8, 11, 13: smaller machines / condensers
        [2, 3, 3, 1,  2, 2,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  5, 3,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1,  8, 4,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1, 11, 5,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
        [2, 3, 3, 1, 13, 6,  6.5, 0, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10],
    ], dtype=float)

    exc = np.array([
        [b, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0]
        for b in (1, 2, 5, 8, 11, 13)
    ], dtype=float)

    gov = np.array([
        [i, 0, 0, 0, 0, 0, 0, 0, 0] for i in range(1, 7)
    ], dtype=float)

    pss = np.array([
        [b, i, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        for i, b in enumerate((1, 2, 5, 8, 11, 13), start=1)
    ], dtype=float)

    return gen, exc, pss, gov, freq, stepsize, stoptime
