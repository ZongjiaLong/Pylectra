"""DynamicSystem facade — bundles one network case with its dynamic data.

The legacy :func:`rundyn` carries a giant positional argument list through its
inner loops (``Pgen, Pexc, Pgov, Ppss, genmodel, excmodel, govmodel,
pssmodel, Ly, Uy, Py, gbus, baseMVA, ...``).  :class:`DynamicSystem` collects
these in one object so solvers and runners receive a single handle.

For Phase 1 the system is a *data container* — the inner ODE loop is still
executed by the legacy procedural code via the :class:`LegacySimRunner`
wrapper.  Phase 2 will move the loop into the solver plugin so individual
generator / exciter banks can be exposed at this layer.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .case import NetworkCase

from .freq import set_freq as _set_freq


@dataclass
class DynamicSystem:
    """A network case + its dynamic data, ready for time-domain simulation."""

    case: NetworkCase
    Pgen: np.ndarray
    Pexc: np.ndarray
    Pgov: np.ndarray
    Ppss: np.ndarray
    freq: float
    stepsize: float
    stoptime: float

    # Derived integer model-type vectors (filled in __post_init__)
    genmodel: np.ndarray = field(init=False)
    excmodel: np.ndarray = field(init=False)
    govmodel: np.ndarray = field(init=False)
    pssmodel: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.Pgen = np.asarray(self.Pgen, dtype=float)
        self.Pexc = np.asarray(self.Pexc, dtype=float)
        self.Pgov = np.asarray(self.Pgov, dtype=float)
        self.Ppss = np.asarray(self.Ppss, dtype=float)

        if self.Pgen.shape[1] < 4:
            raise ValueError("Pgen must have at least 4 columns (model selectors)")

        self.genmodel = self.Pgen[:, 0].astype(int)
        self.excmodel = self.Pgen[:, 1].astype(int)
        self.pssmodel = self.Pgen[:, 2].astype(int)
        self.govmodel = self.Pgen[:, 3].astype(int)

        # Update the pylectra-native frequency holder (and mirror to
        # ``Models._globals`` for legacy code paths) so plugins reading
        # ``pylectra.core.freq.freq`` and legacy ``Models._globals.freq``
        # both see the value provided here.
        _set_freq(float(self.freq))

    # ------------------------------------------------------------------
    @property
    def n_gen(self) -> int:
        return int(self.Pgen.shape[0])

    def copy(self) -> "DynamicSystem":
        """Deep copy (case + numpy arrays)."""
        return DynamicSystem(
            case=self.case.copy(),
            Pgen=deepcopy(self.Pgen),
            Pexc=deepcopy(self.Pexc),
            Pgov=deepcopy(self.Pgov),
            Ppss=deepcopy(self.Ppss),
            freq=self.freq,
            stepsize=self.stepsize,
            stoptime=self.stoptime,
        )

    # ------------------------------------------------------------------
    @classmethod
    def from_legacy(cls, case_pf, case_dyn) -> "DynamicSystem":
        """Build from the legacy ``case_pf`` / ``case_dyn`` arguments.

        ``case_pf`` may be a name string, a dict, or a :class:`NetworkCase`.
        ``case_dyn`` may be a name string or a dict.
        """
        from pylectra.io.dyn_loaders import (
            loaddyn as Loaddyn,
            loadgen as Loadgen,
            loadexc as Loadexc,
            loadgov as Loadgov,
            loadpss as Loadpss,
        )

        if isinstance(case_pf, NetworkCase):
            case = case_pf
        else:
            case = NetworkCase.load(case_pf)

        freq, stepsize, stoptime = Loaddyn(case_dyn)
        Pgen = Loadgen(case_dyn, 0)
        # Mirror the rundyn quirk: duplicate xd_tr (col 9) into col 10.
        if Pgen.shape[1] < 10:
            Pgen = np.hstack([Pgen, np.zeros((Pgen.shape[0], 10 - Pgen.shape[1]))])
        Pgen[:, 9] = Pgen[:, 8]

        Pexc = Loadexc(case_dyn)
        Ppss = Loadpss(case_dyn)
        Pgov = Loadgov(case_dyn)

        return cls(
            case=case,
            Pgen=Pgen,
            Pexc=Pexc,
            Pgov=Pgov,
            Ppss=Ppss,
            freq=freq,
            stepsize=stepsize,
            stoptime=stoptime,
        )

    def to_dyn_dict(self) -> dict:
        """Return the dict shape accepted by all legacy ``Load*`` functions."""
        return {
            "gen": self.Pgen,
            "exc": self.Pexc,
            "gov": self.Pgov,
            "pss": self.Ppss,
            "freq": self.freq,
            "stepsize": self.stepsize,
            "stoptime": self.stoptime,
        }
