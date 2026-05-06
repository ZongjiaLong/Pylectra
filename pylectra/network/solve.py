"""Native ``SolveNetwork`` — solve ``Y · U = I_g`` via the LU from :func:`aug_ybus`."""
from __future__ import annotations

import numpy as np


def solve_network(Xgen, Pgen, Ly, Uy, Py, gbus, gentype):
    """Return bus voltage vector ``U`` (complex, length nb).

    Signature mirrors the legacy three-factor ``(Ly, Uy, Py)`` shape so
    callers can pass the augmented LU object as the first slot and ``None``
    for the other two.
    """
    ngen = gbus.size
    Igen = np.zeros(ngen, dtype=complex)

    gentype = np.asarray(gentype).ravel()
    type2 = np.flatnonzero(gentype == 2)

    if type2.size:
        delta = Xgen[type2, 0]
        Eq_tr = Xgen[type2, 2]
        Ed_tr = Xgen[type2, 3]
        xd_tr = Pgen[type2, 8]
        Igen[type2] = (Eq_tr + 1j * Ed_tr) * np.exp(1j * delta) / (1j * xd_tr)

    nb = Ly.shape[0]
    Ig = np.zeros(nb, dtype=complex)
    Ig[gbus] = Igen

    return Ly.solve(Ig)
