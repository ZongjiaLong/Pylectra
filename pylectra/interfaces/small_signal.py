"""Abstract base class for small-signal stability analyzers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class SmallSignalResult:
    """Outcome of a small-signal stability analysis at one equilibrium point.

    Attributes
    ----------
    eigenvalues : (n,) complex ndarray
        Eigenvalues of the Jacobian J = df/dy at the equilibrium.
    eigenvectors : (n, n) complex ndarray or None
        Right eigenvectors (column j = eigenvector for eigenvalues[j]).
    jacobian : (n, n) float ndarray or None
        The Jacobian matrix itself. Optional; kept only if return_jacobian=True.
    is_stable : bool
        True iff all eigenvalues satisfy Re(lambda) <= stability_tolerance,
        ignoring the single reference-angle zero mode if drop_reference_mode=True.
    stability_margin : float
        max(Re(lambda)) over the relevant spectrum. Negative = stable.
    damping_ratios : (n,) float ndarray
        For each eigenvalue sigma+j*omega, zeta = -sigma / sqrt(sigma^2 + omega^2).
        NaN where sigma=omega=0.
    frequencies_hz : (n,) float ndarray
        Oscillation frequency |omega|/(2*pi) for each eigenvalue.
    metadata : dict
        Analyzer-specific fields (method, epsilon, wall_time_sec, n_states …).
    """

    eigenvalues: np.ndarray
    eigenvectors: Optional[np.ndarray] = None
    jacobian: Optional[np.ndarray] = None
    is_stable: bool = False
    stability_margin: float = float("nan")
    damping_ratios: np.ndarray = field(default_factory=lambda: np.array([]))
    frequencies_hz: np.ndarray = field(default_factory=lambda: np.array([]))
    metadata: Dict[str, Any] = field(default_factory=dict)


class SmallSignalAnalyzer(ABC):
    """Compute small-signal stability properties at an ODE equilibrium point.

    Plugin category: ``"small_signal"``.

    Subclasses must implement :meth:`analyze`.  The ``rhs`` passed to
    :meth:`analyze` is the ODE right-hand side as a plain callable
    ``f(t, y) -> dy/dt``.  The caller guarantees that ``f(t0, y0) ≈ 0``
    (i.e. ``y0`` is the equilibrium).
    """

    @abstractmethod
    def analyze(
        self,
        rhs,
        y0: np.ndarray,
        layout,
        *,
        t0: float = 0.0,
    ) -> SmallSignalResult:
        """Linearise the system around ``y0`` and return spectral properties.

        Parameters
        ----------
        rhs :
            Callable ``f(t, y) -> dy/dt`` (the ODE right-hand side).
        y0 :
            Equilibrium state vector, shape ``(n,)``.
        layout :
            :class:`pylectra.engine.state.StateLayout` — carries ``ngen`` and
            dimension information.  Implementations may ignore this if they
            only need the raw state size.
        t0 :
            Time at which to evaluate the Jacobian (autonomous systems: 0.0).
        """
