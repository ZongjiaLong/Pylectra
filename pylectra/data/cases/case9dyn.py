"""case9dyn - dynamic simulation data for the WSCC 9-bus system.

Returns the canonical 7-tuple ``(gen, exc, pss, gov, freq, stepsize, stoptime)``
matching ``case39dyn`` so the same engine code path is reused.

Source of dynamic parameters
----------------------------
Anderson & Fouad, *Power System Control and Stability*, 2nd ed., Tables 6.6
and 6.7 (Western System 9-bus, 3-machine equivalent). Reproduced verbatim in
PSAT toolkit (``d_kundur1.m`` / ``d_009.m``) and in Sauer & Pai
*Power System Dynamics and Stability* Appendix D.

Convention (matches ``case39dyn``):

* Generator inertia ``H`` is on the **system 100 MVA base** (so ``H * 100``
  equals the per-machine kinetic energy in MWs).
* All reactances ``x_d, x'_d, x_q, x'_q, x_l`` are on the **machine MVA base**.
* Time constants ``T'_do, T'_qo`` are seconds.

Bus numbering follows the MATPOWER 1-indexed convention used by
``pandapower.networks.case9`` after ``to_mpc(net, init='flat')``: generators
sit on buses 1, 2, 3.

No exciter/governor/PSS dynamics are modelled by default — exciters are
populated with the same simple first-order block as ``case39dyn`` (so
generator terminal voltage is held), governors and PSS are placeholders
(``govmodel=1`` constant power; ``pssmodel=3`` no-op) following the existing
case39 convention.
"""
import numpy as np


def case9dyn():
    freq = 60.0
    stepsize = 0.001
    stoptime = 10.0

    # Generator: [genmodel excmodel pssmodel govmodel bus unit H r_a x'_d x'_q x_d x_q T'_do T'_qo x_l]
    # genmodel 2 = two-axis transient model; excmodel 3 = simple AVR;
    # pssmodel 3 = no-op; govmodel 1 = constant mechanical power.
    gen = np.array([
        # bus 1: Gen 1, hydro, 247.5 MVA
        [2, 3, 3, 1, 1, 1, 23.64, 0, 0.0608, 0.0969, 0.1460, 0.0969, 8.96, 0.31, 0.0336],
        # bus 2: Gen 2, steam, 192 MVA
        [2, 3, 3, 1, 2, 2,  6.40, 0, 0.1198, 0.1969, 0.8958, 0.8645, 6.00, 0.535, 0.0521],
        # bus 3: Gen 3, steam, 128 MVA
        [2, 3, 3, 1, 3, 3,  3.01, 0, 0.1813, 0.2500, 1.3125, 1.2578, 5.89, 0.60,  0.0742],
    ], dtype=float)

    # First-order exciter [bus Tv mu k Ef_min Ef_max <padding>]
    exc = np.array([
        [1, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [2, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
        [3, 0.95, 10, 1, -10, 10, 0, 0, 0, 0, 0],
    ], dtype=float)

    # Governor [gen K T1 T2 T3 Pup Pdown Pmax Pmin] - placeholder rows.
    gov = np.array([
        [i, 0, 0, 0, 0, 0, 0, 0, 0] for i in range(1, 4)
    ], dtype=float)

    # PSS [bus pres_idx pssgain washout T1 T2 T3 T4 T5 T6 ymax ymin] - no-op.
    pss = np.array([
        [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ], dtype=float)

    return gen, exc, pss, gov, freq, stepsize, stoptime
