"""case14dyn - dynamic simulation data for the IEEE 14-bus test system.

Returns the canonical 7-tuple ``(gen, exc, pss, gov, freq, stepsize, stoptime)``.

Source of dynamic parameters
----------------------------
PSAT toolkit ``d_014_dyn.m`` (Milano, *Power System Modelling and Scripting*,
Springer 2010, Appendix D). Five synchronous machines: one main generator at
bus 1 plus four synchronous condensers at buses 2, 3, 6, 8.

Convention (matches ``case39dyn``):

* ``H`` on system 100 MVA base; reactances on machine MVA base; time
  constants in seconds.
* PSAT supplies ``T'_qo = 0`` for the slack machine; we substitute
  ``T'_qo = 0.3`` (typical value used by the four condensers in the same
  dataset) so the two-axis model avoids a degenerate q-axis time constant.
* ``x_l`` is not given by PSAT for this case; we fill ``0.10`` (typical
  synchronous-machine leakage reactance). The native engine does not consume
  this field, so the value is informational only.

Bus numbering follows ``pandapower.networks.case14`` post-``to_mpc`` output:
generators on buses 1, 2, 3, 6, 8.
"""
import numpy as np


def case14dyn():
    freq = 60.0
    stepsize = 0.001
    stoptime = 10.0

    # Generator: [genmodel excmodel pssmodel govmodel bus unit H r_a x'_d x'_q x_d x_q T'_do T'_qo x_l]
    gen = np.array([
        # bus 1: main slack generator
        [2, 3, 3, 1, 1, 1, 5.148, 0, 0.2995, 0.646, 0.8979, 0.646, 7.4, 0.3, 0.10],
        # bus 2-8: synchronous condensers (identical PSAT params)
        [2, 3, 3, 1, 2, 2, 6.54,  0, 0.185,  0.36,  1.05,   0.98,  6.1, 0.3, 0.10],
        [2, 3, 3, 1, 3, 3, 6.54,  0, 0.185,  0.36,  1.05,   0.98,  6.1, 0.3, 0.10],
        [2, 3, 3, 1, 6, 4, 6.54,  0, 0.185,  0.36,  1.05,   0.98,  6.1, 0.3, 0.10],
        [2, 3, 3, 1, 8, 5, 6.54,  0, 0.185,  0.36,  1.05,   0.98,  6.1, 0.3, 0.10],
    ], dtype=float)

    # First-order exciter [bus Tv mu k Ef_min Ef_max <padding>]
    exc = np.array([
        [1, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [2, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [3, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [6, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [8, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
    ], dtype=float)

    # Governor [gen K T1 T2 T3 Pup Pdown Pmax Pmin] - placeholder rows.
    gov = np.array([
        [i, 0, 0, 0, 0, 0, 0, 0, 0] for i in range(1, 6)
    ], dtype=float)

    # PSS [bus pres_idx pssgain washout T1 T2 T3 T4 T5 T6 ymax ymin] - no-op.
    pss = np.array([
        [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [6, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [8, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ], dtype=float)

    return gen, exc, pss, gov, freq, stepsize, stoptime
