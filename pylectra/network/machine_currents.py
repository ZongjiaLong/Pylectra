"""Native ``MachineCurrents`` — Id/Iq/Pe from generator state and bus voltage."""
from __future__ import annotations

import numpy as np


def machine_currents(Xgen, Pgen, U, gentype):
    """Return ``(Id, Iq, Pe)`` for every generator.

    Type-2 (4th-order two-axis) generators are computed from
    ``(delta, Eq', Ed', xd', xq')``; other types leave zeros.
    """
    ngen = Xgen.shape[0]
    Id = np.zeros(ngen)
    Iq = np.zeros(ngen)
    Pe = np.zeros(ngen)

    gentype = np.asarray(gentype).ravel()
    type2 = np.flatnonzero(gentype == 2)

    if type2.size:
        delta = Xgen[type2, 0]
        Eq_tr = Xgen[type2, 2]
        Ed_tr = Xgen[type2, 3]
        xd_tr = Pgen[type2, 8]
        xq_tr = Pgen[type2, 9]

        theta = np.angle(U)
        absU = np.abs(U[type2])
        vd = -absU * np.sin(delta - theta[type2])
        vq = absU * np.cos(delta - theta[type2])

        Id[type2] = (vq - Eq_tr) / xd_tr
        Iq[type2] = -(vd - Ed_tr) / xq_tr
        Pe[type2] = (Eq_tr * Iq[type2] + Ed_tr * Id[type2]
                     + (xd_tr - xq_tr) * Id[type2] * Iq[type2])

    return Id, Iq, Pe
