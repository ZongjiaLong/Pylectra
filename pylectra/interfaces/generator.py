"""Abstract base class for generator dynamic models.

A *model* corresponds to one row-type in the dynamic generator matrix
(``Pgen``).  The current legacy code only implements the 4th-order (type 2)
machine but new model types (type 6 sub-transient, GENROU, GENSAL …) plug in
the same way.

A *bank* (kept inside :class:`pylectra.core.system.DynamicSystem`) groups all
machines and dispatches the right rows to each registered model.  Model
implementations should therefore be written as pure functions of the rows they
own — they must not look at machines outside ``rows``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np


class GeneratorModel(ABC):
    """Per-type generator dynamic model.

    Subclasses must declare:

    * ``type_id``: the integer that identifies this model in the first column
      of the legacy ``Pgen`` matrix.
    * ``n_states``: number of state variables per machine (legacy code uses 4
      for the type-2 model: ``[delta, omega, Eq', Ed']``).
    """

    type_id: int = 0
    n_states: int = 4

    @abstractmethod
    def init(
        self,
        Pgen_rows: np.ndarray,
        U_rows: np.ndarray,
        gen_rows: np.ndarray,
        baseMVA: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Steady-state initialisation.

        Returns ``(Efd0, Xgen0)`` where ``Efd0`` has shape ``(nrows,)`` and
        ``Xgen0`` has shape ``(nrows, n_states)``.
        """

    @abstractmethod
    def derivative(
        self,
        Xgen_rows: np.ndarray,
        Xexc_rows: np.ndarray,
        Xgov_rows: np.ndarray,
        Pgen_rows: np.ndarray,
        Vgen_rows: np.ndarray,
        freq: float,
    ) -> np.ndarray:
        """Compute ``dX/dt`` for these rows.  Output shape ``(nrows, n_states)``."""

    @abstractmethod
    def currents(
        self,
        Xgen_rows: np.ndarray,
        Pgen_rows: np.ndarray,
        Ubus_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(Id, Iq, Pe)`` for these rows."""
