"""case118dyn - dynamic simulation data for the IEEE 118-bus test system.

Returns the canonical 7-tuple ``(gen, exc, pss, gov, freq, stepsize, stoptime)``.

Source of dynamic parameters
----------------------------
Synthesised typical-machine values consistent with PSAT ``d_118_dyn.m``
parameter ranges. The IEEE 118-bus benchmark has 54 generators; published
dynamic data sets vary considerably (Pal & Chaudhuri textbook, Sauer-Pai,
Pinceti et al.). The values below follow a representative convention:

* The slack machine (bus 69) gets a higher inertia (~12 s on system base)
  to represent its grid-equivalent role.
* Most generators are assigned uniform "mid-size" parameters typical of
  steam units (PSAT IEEEX1-class machines).
* Per the plan's risk mitigation, this is marked as ``synthesized`` —
  override per machine for production work.

Convention (matches ``case39dyn``):

* ``H`` on system 100 MVA base; reactances on machine MVA base; time
  constants in seconds.
* ``x_l = 0.10`` placeholder (unused by the native engine).

Bus numbering follows ``pandapower.networks.case118`` post-``to_mpc``: the
ordered list of 54 generator buses appears below.
"""
import numpy as np


# Generator buses in pandapower.networks.case118 (post-to_mpc, 1-indexed).
# First entry (bus 69) is the slack.
_GEN_BUSES = (
    69, 1, 4, 6, 8, 10, 12, 15, 18, 19, 24, 25, 26, 27, 31, 32, 34, 36,
    40, 42, 46, 49, 54, 55, 56, 59, 61, 62, 65, 66, 70, 72, 73, 74, 76,
    77, 80, 85, 87, 89, 90, 91, 92, 99, 100, 103, 104, 105, 107, 110,
    111, 112, 113, 116,
)


def case118dyn():
    freq = 60.0
    stepsize = 0.001
    stoptime = 10.0

    # Typical mid-size steam machine parameters used for non-slack units.
    H_default, Xdp, Xqp, Xd, Xq, Tdo, Tqo, Xl = (
        6.5, 0.20, 0.30, 1.05, 0.98, 6.1, 0.3, 0.10
    )
    # Slack machine (bus 69): higher inertia.
    H_slack, Xdp_s, Xqp_s, Xd_s, Xq_s, Tdo_s, Tqo_s = (
        12.0, 0.18, 0.28, 1.25, 1.18, 6.5, 0.5
    )

    # Generator: [genmodel excmodel pssmodel govmodel bus unit H r_a x'_d x'_q x_d x_q T'_do T'_qo x_l]
    rows = []
    for i, bus in enumerate(_GEN_BUSES, start=1):
        if bus == 69:
            rows.append([2, 3, 3, 1, bus, i, H_slack, 0,
                         Xdp_s, Xqp_s, Xd_s, Xq_s, Tdo_s, Tqo_s, Xl])
        else:
            rows.append([2, 3, 3, 1, bus, i, H_default, 0,
                         Xdp, Xqp, Xd, Xq, Tdo, Tqo, Xl])
    gen = np.array(rows, dtype=float)

    exc = np.array([
        [b, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0] for b in _GEN_BUSES
    ], dtype=float)

    gov = np.array([
        [i, 0, 0, 0, 0, 0, 0, 0, 0] for i in range(1, len(_GEN_BUSES) + 1)
    ], dtype=float)

    pss = np.array([
        [b, i, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        for i, b in enumerate(_GEN_BUSES, start=1)
    ], dtype=float)

    return gen, exc, pss, gov, freq, stepsize, stoptime
