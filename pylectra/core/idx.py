"""MATPOWER-style column indices for ``mpc`` arrays — pylectra-native copy.

These are the same constants exposed by the legacy ``PowerFlow.idx_bus``,
``PowerFlow.idx_brch`` and ``PowerFlow.idx_gen`` modules, but living
inside ``pylectra/`` so the framework no longer needs to reach into the legacy
package to look them up.

The values are pure data (small integers); duplicating them is cheap and
removes the largest single class of legacy imports inside ``pylectra/``.

Re-exported as three submodules for namespace compatibility:

* ``pylectra.core.idx.bus``    — bus column indices  (BUS_I, BUS_TYPE, PD …)
* ``pylectra.core.idx.brch``   — branch column indices (F_BUS, T_BUS, BR_R …)
* ``pylectra.core.idx.gen``    — generator column indices (GEN_BUS, PG, QG …)

Plus the ``idx_bus()``, ``idx_brch()``, ``idx_gen()`` callables that
return the same tuples the legacy code did, for drop-in replacement.
"""
from __future__ import annotations

# ============================================================ bus indices
# Bus types (values stored in BUS_TYPE column).
PQ = 1
PV = 2
REF = 3
NONE = 4

# Bus matrix column indices (0-based).
BUS_I = 0       # bus number
BUS_TYPE = 1    # bus type
PD = 2          # Pd, real power demand (MW)
QD = 3          # Qd, reactive power demand (MVAr)
GS = 4          # Gs, shunt conductance
BS = 5          # Bs, shunt susceptance
BUS_AREA = 6    # area number
VM = 7          # Vm, voltage magnitude (p.u.)
VA = 8          # Va, voltage angle (degrees)
BASE_KV = 9     # baseKV (kV)
ZONE = 10       # loss zone
VMAX = 11
VMIN = 12

# OPF outputs.
LAM_P = 13
LAM_Q = 14
MU_VMAX = 15
MU_VMIN = 16


def idx_bus():
    """Return the legacy ``idx_bus()`` tuple, in MATLAB column order."""
    return (PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA,
            VM, VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN)


# ========================================================= branch indices
F_BUS = 0
T_BUS = 1
BR_R = 2
BR_X = 3
BR_B = 4
RATE_A = 5
RATE_B = 6
RATE_C = 7
TAP = 8
SHIFT = 9
BR_STATUS = 10
ANGMIN = 11
ANGMAX = 12

# Power flow output columns.
PF_BR = 13
QF_BR = 14
PT_BR = 15
QT_BR = 16

# OPF output columns.
MU_SF = 17
MU_ST = 18
MU_ANGMIN = 19
MU_ANGMAX = 20


def idx_brch():
    """Return the legacy ``idx_brch()`` tuple."""
    return (F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C,
            TAP, SHIFT, BR_STATUS, PF_BR, QF_BR, PT_BR, QT_BR,
            MU_SF, MU_ST, ANGMIN, ANGMAX, MU_ANGMIN, MU_ANGMAX)


# ====================================================== generator indices
GEN_BUS = 0
PG = 1
QG = 2
QMAX = 3
QMIN = 4
VG = 5
MBASE = 6
GEN_STATUS = 7
PMAX = 8
PMIN = 9
PC1 = 10
PC2 = 11
QC1MIN = 12
QC1MAX = 13
QC2MIN = 14
QC2MAX = 15
RAMP_AGC = 16
RAMP_10 = 17
RAMP_30 = 18
RAMP_Q = 19
APF = 20

MU_PMAX = 21
MU_PMIN = 22
MU_QMAX = 23
MU_QMIN = 24


def idx_gen():
    """Return the legacy ``idx_gen()`` tuple."""
    return (GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN,
            MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN, PC1, PC2, QC1MIN, QC1MAX,
            QC2MIN, QC2MAX, RAMP_AGC, RAMP_10, RAMP_30, RAMP_Q, APF)
