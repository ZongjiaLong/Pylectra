"""Modal analyzer — small-signal results sorted by damping ratio.

Identical numerical path as :class:`~pylectra.small_signal.finite_difference
.FiniteDifferenceAnalyzer` but with opinionated defaults that are more
useful for modal analysis:

* ``return_eigenvectors=True``  — participation factors require eigenvectors.
* ``return_jacobian=True``      — the full system matrix is stored.
* Eigenvalues are sorted by ascending damping ratio (least-damped modes
  first), making it easy to identify the critical inter-area oscillation.
"""
from __future__ import annotations

import numpy as np

from pylectra.registry import register
from pylectra.small_signal.finite_difference import FiniteDifferenceAnalyzer
from pylectra.interfaces.small_signal import SmallSignalResult


@register("small_signal", "modal")
class ModalAnalyzer(FiniteDifferenceAnalyzer):
    """Jacobian eigenanalysis with full mode information, sorted by damping.

    Parameters are identical to :class:`FiniteDifferenceAnalyzer`.
    Additional defaults:

    * ``return_eigenvectors`` defaults to ``True``.
    * ``return_jacobian`` defaults to ``True``.
    * Eigenvalues are re-ordered from smallest (or most negative) damping
      ratio to largest before being stored in :class:`SmallSignalResult`.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("return_eigenvectors", True)
        kwargs.setdefault("return_jacobian", True)
        super().__init__(**kwargs)

    def analyze(self, rhs, y0: np.ndarray, layout, *, t0: float = 0.0) -> SmallSignalResult:
        res = super().analyze(rhs, y0, layout, t0=t0)

        # Sort by damping ratio (NaN modes go to the end).
        zeta = res.damping_ratios
        sort_key = np.where(np.isnan(zeta), np.inf, zeta)
        order = np.argsort(sort_key)

        res.eigenvalues = res.eigenvalues[order]
        res.damping_ratios = res.damping_ratios[order]
        res.frequencies_hz = res.frequencies_hz[order]
        if res.eigenvectors is not None:
            res.eigenvectors = res.eigenvectors[:, order]

        res.metadata["sorted_by"] = "damping_ratio_ascending"
        return res
