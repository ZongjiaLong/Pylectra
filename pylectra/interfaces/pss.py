"""Abstract base class for power-system stabiliser (PSS) dynamic models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np


class PSSModel(ABC):
    """Per-type PSS dynamic model.

    The legacy code provides a single trivial type (``type_id = 3`` = "no PSS",
    i.e. ``dXpss = 0``).
    """

    type_id: int = 0
    n_states: int = 0

    @abstractmethod
    def init(
        self,
        Ppss_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(Xpss0_rows, Ppss_rows_updated)``."""

    @abstractmethod
    def derivative(
        self,
        Xpss_rows: np.ndarray,
        Xgen_rows: np.ndarray,
        Ppss_rows: np.ndarray,
    ) -> np.ndarray:
        """Compute ``dXpss/dt``."""
