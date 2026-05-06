"""Phase 5: small-signal analyzer correctness on synthetic ODEs.

We construct linear and weakly-nonlinear systems whose Jacobian eigenvalues
are known analytically and verify that
:class:`pylectra.small_signal.finite_difference.FiniteDifferenceAnalyzer` and
:class:`pylectra.small_signal.modal.ModalAnalyzer` recover them.

Test systems
------------

1. **Damped harmonic oscillator** — ``ẋ₁ = x₂``, ``ẋ₂ = −ω₀²·x₁ − 2ζω₀·x₂``.
   Analytic eigenvalues: ``λ = −ζω₀ ± jω₀√(1−ζ²)``.

2. **Diagonal real spectrum** — ``ẋᵢ = −kᵢ·xᵢ`` with prescribed ``kᵢ``.
   Eigenvalues are simply ``−kᵢ``.

3. **Unstable saddle** — ``ẋ₁ = x₁``, ``ẋ₂ = −x₂``.  Mixed-sign spectrum
   exercises the ``is_stable`` flag; ``drop_reference_mode=False`` is needed
   here because there's no rotational symmetry.
"""
from __future__ import annotations

import numpy as np
import pytest

import pylectra  # noqa: F401  (registers analyzers)
from pylectra.registry import get


# A minimal stand-in for ``StateLayout`` (the analyzer only reads ``ngen``
# when it does the reference-angle drop, otherwise tolerates None).
class _Layout:
    def __init__(self, n):
        self.ngen = max(n // 9, 1)
        self.n_states = n


# -------------------------------------------------------------- oscillator
@pytest.mark.parametrize("omega0,zeta", [(2 * np.pi * 1.0, 0.05),
                                         (2 * np.pi * 0.5, 0.10),
                                         (2 * np.pi * 2.0, 0.20)])
def test_damped_oscillator_spectrum(omega0, zeta):
    A = np.array([[0.0, 1.0], [-omega0**2, -2 * zeta * omega0]])

    def rhs(t, y):
        return A @ y

    cls = get("small_signal", "finite_difference")
    analyzer = cls(epsilon=1e-7, method="central",
                   drop_reference_mode=False, return_jacobian=True)
    res = analyzer.analyze(rhs, np.zeros(2), _Layout(2))

    np.testing.assert_allclose(res.jacobian, A, rtol=0, atol=1e-5)

    expected = np.sort_complex(np.array([
        -zeta * omega0 + 1j * omega0 * np.sqrt(1 - zeta ** 2),
        -zeta * omega0 - 1j * omega0 * np.sqrt(1 - zeta ** 2),
    ]))
    got = np.sort_complex(res.eigenvalues)
    np.testing.assert_allclose(got, expected, rtol=1e-4, atol=1e-6)

    # Damping ratio should match within FD precision.
    assert np.isclose(np.nanmax(res.damping_ratios), zeta, rtol=1e-3)
    assert res.is_stable is True


# ------------------------------------------------------------ diagonal spectrum
def test_diagonal_real_spectrum_recovered():
    k = np.array([0.5, 1.0, 2.0, 3.5, 7.0])
    A = -np.diag(k)

    def rhs(t, y):
        return A @ y

    cls = get("small_signal", "finite_difference")
    analyzer = cls(epsilon=1e-7, drop_reference_mode=False)
    res = analyzer.analyze(rhs, np.zeros(len(k)), _Layout(len(k)))

    eigs = np.sort(res.eigenvalues.real)
    expected = np.sort(-k)
    np.testing.assert_allclose(eigs, expected, rtol=1e-5, atol=1e-7)
    # Pure-real, so all damping ratios are ±1; treat ±1 as full damping.
    assert res.is_stable is True
    assert res.stability_margin < 0


# ----------------------------------------------------------- unstable saddle
def test_unstable_saddle_detected():
    A = np.diag([1.0, -1.0])

    def rhs(t, y):
        return A @ y

    cls = get("small_signal", "finite_difference")
    analyzer = cls(epsilon=1e-7, drop_reference_mode=False)
    res = analyzer.analyze(rhs, np.zeros(2), _Layout(2))
    assert res.is_stable is False
    assert res.stability_margin > 0
    np.testing.assert_allclose(np.sort(res.eigenvalues.real), [-1.0, 1.0],
                               rtol=1e-6, atol=1e-7)


# ----------------------------------------------------------- modal sort order
def test_modal_analyzer_sorts_by_damping():
    # Two oscillators with very different damping; modal must put the
    # lightly-damped one first.
    A = np.zeros((4, 4))
    omega1, z1 = 2 * np.pi * 1.0, 0.02   # poorly-damped
    omega2, z2 = 2 * np.pi * 1.5, 0.30   # well-damped
    A[0, 1] = 1.0
    A[1, 0] = -omega1 ** 2
    A[1, 1] = -2 * z1 * omega1
    A[2, 3] = 1.0
    A[3, 2] = -omega2 ** 2
    A[3, 3] = -2 * z2 * omega2

    def rhs(t, y):
        return A @ y

    cls = get("small_signal", "modal")
    res = cls(drop_reference_mode=False).analyze(rhs, np.zeros(4), _Layout(4))

    # First non-NaN damping in the sorted output must be ≈ z1 (poorly damped).
    zetas = res.damping_ratios[~np.isnan(res.damping_ratios)]
    assert np.isclose(zetas[0], z1, rtol=5e-3), \
        f"expected first damping ≈ {z1}, got {zetas[:2]}"
    assert res.eigenvectors is not None and res.jacobian is not None
