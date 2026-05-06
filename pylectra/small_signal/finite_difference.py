"""Small-signal analyzer using numerical Jacobian via finite differences.

The Jacobian J = df/dy is computed column-by-column by perturbing each state
variable and re-evaluating the ODE right-hand side.  No automatic
differentiation or special symbolic treatment is required — the ODE ``rhs``
callable is treated as a black box.

Power-system note
-----------------
The state vector y has dimension ``9 * ngen`` (4 generator + 1 exciter +
4 governor states per machine).  All coupling — through the augmented Y-bus,
machine currents, and feedback controllers — is automatically captured because
each Jacobian column evaluation calls the full ``rhs(t, y)`` once.

Eigenvalue interpretation
--------------------------
* A stable equilibrium has all eigenvalues with Re(λ) ≤ 0.
* One eigenvalue near zero is expected (it reflects the degree of freedom that
  allows shifting all rotor angles by a constant — this is physically harmless).
  Set ``drop_reference_mode=True`` (default) to exclude it from the stability
  verdict.
* The ``stability_margin`` is max(Re(λ)) over the relevant spectrum.  A
  negative value means stable; positive means unstable.
* For oscillatory modes (complex eigenvalue λ = σ ± jω), the damping ratio
  ζ = −σ / sqrt(σ² + ω²).  A common engineering threshold is ζ ≥ 0.05 (5 %).
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np
from scipy.linalg import eig

from pylectra.registry import register
from pylectra.interfaces.small_signal import SmallSignalAnalyzer, SmallSignalResult


@register("small_signal", "finite_difference")
class FiniteDifferenceAnalyzer(SmallSignalAnalyzer):
    """Numerical Jacobian (finite differences) + dense eigendecomposition.

    Parameters
    ----------
    epsilon : float
        Perturbation size.  ``1e-6`` balances truncation vs. round-off error
        for typical per-unit power-system states.
    method : {"central", "forward"}
        ``"central"`` uses ``2n`` RHS evaluations but is O(ε²) accurate.
        ``"forward"`` uses only ``n+1`` evaluations (faster for large systems).
    drop_reference_mode : bool
        If True, the eigenvalue closest to the origin (|λ| smallest) is
        excluded from the stability check.  This handles the reference-angle
        degree of freedom that always produces a near-zero eigenvalue.
    stability_tolerance : float
        An eigenvalue with Re(λ) ≤ stability_tolerance is considered stable.
        Set slightly above zero to absorb floating-point noise.
    return_jacobian : bool
        Whether to store the full n × n Jacobian in the result.
    return_eigenvectors : bool
        Whether to compute and store right eigenvectors.
    """

    def __init__(
        self,
        epsilon: float = 1e-6,
        method: str = "central",
        drop_reference_mode: bool = True,
        stability_tolerance: float = 1e-4,
        return_jacobian: bool = False,
        return_eigenvectors: bool = False,
    ):
        if method not in ("forward", "central"):
            raise ValueError(
                f"method must be 'forward' or 'central', got {method!r}"
            )
        self.epsilon = float(epsilon)
        self.method = method
        self.drop_reference_mode = bool(drop_reference_mode)
        self.stability_tolerance = float(stability_tolerance)
        self.return_jacobian = bool(return_jacobian)
        self.return_eigenvectors = bool(return_eigenvectors)

    # ------------------------------------------------------------------
    def analyze(
        self,
        rhs,
        y0: np.ndarray,
        layout,
        *,
        t0: float = 0.0,
    ) -> SmallSignalResult:
        t_start = time.perf_counter()
        y0 = np.asarray(y0, dtype=float).ravel()
        n = y0.size
        eps = self.epsilon

        # ---- Build Jacobian column by column -------------------------
        J = np.empty((n, n), dtype=float)
        f0 = np.asarray(rhs(t0, y0), dtype=float)

        if self.method == "forward":
            for j in range(n):
                yp = y0.copy()
                yp[j] += eps
                fp = np.asarray(rhs(t0, yp), dtype=float)
                J[:, j] = (fp - f0) / eps
        else:  # central
            for j in range(n):
                yp = y0.copy(); yp[j] += eps
                ym = y0.copy(); ym[j] -= eps
                fp = np.asarray(rhs(t0, yp), dtype=float)
                fm = np.asarray(rhs(t0, ym), dtype=float)
                J[:, j] = (fp - fm) / (2.0 * eps)

        # ---- Eigendecomposition --------------------------------------
        if self.return_eigenvectors:
            evals, evecs = eig(J, right=True)
            evecs_out: Optional[np.ndarray] = evecs
        else:
            evals = eig(J, right=False)
            evecs_out = None

        # ---- Derived quantities --------------------------------------
        sigma = np.real(evals)
        omega = np.imag(evals)
        with np.errstate(invalid="ignore", divide="ignore"):
            mag = np.sqrt(sigma * sigma + omega * omega)
            zeta = np.where(mag > 0.0, -sigma / mag, np.nan)
        freq_hz = np.abs(omega) / (2.0 * np.pi)

        # ---- Stability check -----------------------------------------
        # Optionally ignore the eigenvalue closest to the origin.
        mask = np.ones(n, dtype=bool)
        if self.drop_reference_mode and n > 0:
            idx_min = int(np.argmin(np.abs(evals)))
            if np.abs(evals[idx_min]) < 1e-3:
                mask[idx_min] = False

        relevant_real = sigma[mask]
        margin = float(relevant_real.max()) if relevant_real.size else float("-inf")
        is_stable = bool(margin <= self.stability_tolerance)

        return SmallSignalResult(
            eigenvalues=evals,
            eigenvectors=evecs_out,
            jacobian=J if self.return_jacobian else None,
            is_stable=is_stable,
            stability_margin=margin,
            damping_ratios=zeta,
            frequencies_hz=freq_hz,
            metadata={
                "method": self.method,
                "epsilon": eps,
                "n_states": n,
                "n_rhs_calls": 2 * n if self.method == "central" else n + 1,
                "wall_time_sec": time.perf_counter() - t_start,
            },
        )
