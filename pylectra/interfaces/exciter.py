"""Abstract base class for exciter (AVR) dynamic models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np


class ExciterModel(ABC):
    """Per-type exciter dynamic model.

    The legacy code ships with type 3 ("constant Efd", trivial dynamics) and
    type 4 (IEEE DC1A-like).  ``type_id`` matches the value in the second
    column of the ``Pgen`` matrix.
    """

    type_id: int = 0
    n_states: int = 1  # rows of Xexc this model owns

    @abstractmethod
    def init(
        self,
        Efd0_rows: np.ndarray,
        Xgen0_rows: np.ndarray,
        Pexc_rows: np.ndarray,
        Vexc_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(Xexc0_rows, Pexc_rows_updated)``."""

    @abstractmethod
    def derivative(
        self,
        Xexc_rows: np.ndarray,
        Xgen_rows: np.ndarray,
        Pexc_rows: np.ndarray,
        Vexc_rows: np.ndarray,
        Vpss_rows: np.ndarray,
    ) -> np.ndarray:
        """Compute ``dXexc/dt``."""
