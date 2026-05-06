# `pylectra.small_signal`

_Reference_

**Prerequisites:** [Small-signal stability analysis](../../tutorials/05-small-signal.md)

Linearisation and eigenvalue analysis API.

## Class hierarchy

```
SmallSignalAnalyzer (ABC)
└── FiniteDifferenceAnalyzer        # @register("small_signal", "finite_difference")
    └── ModalAnalyzer               # @register("small_signal", "modal")
```

## `FiniteDifferenceAnalyzer`

```python
class FiniteDifferenceAnalyzer:
    def __init__(self,
                 epsilon: float = 1e-6,
                 method: str = "central",            # "central" | "forward"
                 drop_reference_mode: bool = True,
                 stability_tolerance: float = 1e-4,
                 return_jacobian: bool = False,
                 return_eigenvectors: bool = False)
```

**Parameters**

| Param | Default | Notes |
|---|---|---|
| `epsilon` | `1e-6` | Finite-difference perturbation step |
| `method` | `"central"` | central (O(ε²), 2n evals) / forward (O(ε), n+1 evals) |
| `drop_reference_mode` | `True` | Ignore the reference-angle near-zero mode |
| `stability_tolerance` | `1e-4` | Re(λ) ≤ tol counts as stable |
| `return_jacobian` | `False` | Keep the full Jacobian in the result |
| `return_eigenvectors` | `False` | Compute right eigenvectors |

## `ModalAnalyzer`

Subclass of `FiniteDifferenceAnalyzer`. Defaults `return_eigenvectors=True` + `return_jacobian=True`. Eigenvalues are sorted by damping (worst first).

```python
from pylectra.registry import get
analyzer = get("small_signal", "modal")()
```

## `analyze(rhs, y0, layout, *, t0=0.0)`

```python
def analyze(self, rhs, y0: np.ndarray, layout, *, t0: float = 0.0) -> SmallSignalResult
```

**Parameters**

| Param | Type | Notes |
|---|---|---|
| `rhs` | callable | `f(t, y) -> dy/dt` (ODE right-hand side) |
| `y0` | `np.ndarray` | Equilibrium state vector (`f(t0, y0) ≈ 0`) |
| `layout` | `StateLayout` | State layout (provides `ngen`, `n_states`) |
| `t0` | float | Jacobian evaluation time (use 0 for autonomous systems) |

## `SmallSignalResult` fields

```python
@dataclass
class SmallSignalResult:
    eigenvalues: np.ndarray              # (n,) complex
    eigenvectors: np.ndarray | None      # (n, n) complex
    jacobian: np.ndarray | None          # (n, n) float
    is_stable: bool
    stability_margin: float              # max Re(λ) after dropping reference mode
    damping_ratios: np.ndarray           # (n,) float; NaN for pure-real or zero modes
    frequencies_hz: np.ndarray           # (n,) float = |Im(λ)| / 2π
    metadata: dict                       # method, epsilon, wall_time_sec, n_states, ...
```

## Usage

### One-off small-signal analysis

```python
from pylectra.run import run

out = run({
    "mode": "single",
    "case_pf": "case39",
    "case_dyn": "case39dyn",
    "skip_integration": True,
    "small_signal": {"kind": "modal"},
})
ss = out.result.small_signal
print(ss.is_stable, ss.stability_margin)
```

### Participation factors

```python
import numpy as np
phi = ss.eigenvectors                        # right eigenvectors (columns)
psi = np.linalg.inv(phi)                     # left eigenvectors (rows)
P = phi * psi.T                              # element-wise → (n_states, n_modes)
P_norm = np.abs(P) / np.abs(P).sum(axis=0, keepdims=True)
```

### Find the worst-damped mode

```python
import numpy as np
osc = ss.eigenvalues[np.abs(ss.eigenvalues.imag) > 0.01]
worst_idx = np.argmin(ss.damping_ratios[np.abs(ss.eigenvalues.imag) > 0.01])
print(f"Worst-damped mode: λ = {osc[worst_idx]:.4f}, ζ = {ss.damping_ratios[worst_idx]:.4f}")
```

## `small_signal_stable` filter

Use small-signal stability as an acceptance criterion in batch mode:

```yaml
mode: batch
small_signal: {kind: finite_difference}     # compute eigenvalues alongside the sim
filters:
  - kind: pf_converged
  - kind: small_signal_stable
    params: {margin_max: -0.05}             # max Re(λ) ≤ -0.05
```

## Performance

| Case | State dim (9 × n_gen) | Central FD time |
|---|---|---|
| case9 | 27 | ~50 ms |
| case39 | 90 | ~200 ms |
| case118 | 486 | ~1.5 s |

`forward` halves the time but drops accuracy from O(ε²) to O(ε). **Stick with `central` unless you have a reason.**

## Next steps

- [Small-signal tutorial](../../tutorials/05-small-signal.md) — full walk-through.
- [SmallSignalAnalyzer ABC](interfaces.md#smallsignalanalyzer) — interface contract.
