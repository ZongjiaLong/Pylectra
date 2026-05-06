"""Abstract base class for turbine governor dynamic models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np


class GovernorModel(ABC):
    """Per-type governor model."""

    type_id: int = 0
    n_states: int = 1

    @abstractmethod
    def init(
        self,
        Pm0_rows: np.ndarray,
        Pgov_rows: np.ndarray,
        omega0_rows: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(Xgov0_rows, Pgov_rows_updated)``."""

    @abstractmethod
    def derivative(
        self,
        Xgov_rows: np.ndarray,
        Pgov_rows: np.ndarray,
        Vgov_rows: np.ndarray,
    ) -> np.ndarray:
        """Compute ``dXgov/dt``."""
