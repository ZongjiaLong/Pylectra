# Small-signal stability analysis

_Advanced_

**Prerequisites:** [Single deterministic simulation](01-single-run.md)

## Large-disturbance vs. small-signal

| Aspect | Large-disturbance (CCT) | Small-signal |
|---|---|---|
| Physical meaning | Can the system return to equilibrium after a fault? | Do small perturbations near equilibrium decay? |
| Mathematical tool | Full nonlinear ODE integration | Jacobian eigenvalues |
| Output metrics | CCT [s] | Damping ζ, frequency f, stability margin σ |
| Engineering question | Survives major disturbances | Inter-area / local-mode oscillations |

The two are **complementary** — typical research papers report both.

## One-line theory

Linearise the system at equilibrium y₀:

$$
\dot{y} = f(y) \quad\Longrightarrow\quad \dot{\Delta y} = J \cdot \Delta y, \quad J = \frac{\partial f}{\partial y}\bigg|_{y_0}
$$

The **eigenvalues** of J, λ = σ ± jω, determine:

- **σ < 0**: perturbation decays exponentially (stable).
- **σ > 0**: perturbation grows exponentially (unstable).
- **ζ = −σ / √(σ² + ω²)**: damping ratio; **< 5 % is typically a risk**.
- **f = |ω| / (2π)**: oscillation frequency [Hz].

## YAML template

```yaml
mode: single
case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: scipy_dop853}

fault: null                              # No fault needed
skip_integration: true                   # Skip time-domain integration; only equilibrium + eigenvalues

small_signal:
  kind: finite_difference                # finite_difference | modal
  options:
    epsilon: 1.0e-7                      # FD perturbation step
    method: central                      # central | forward
    drop_reference_mode: true            # Drop the zero mode from the reference-angle DOF
    return_eigenvectors: false
    return_jacobian: false
```

`skip_integration: true` makes pylectra **only compute the equilibrium** (PF + multi-machine init + small-signal) — much faster than a full time-domain run.

## Run it

```python
from pylectra.run import run

out = run("examples/single_case39_smallsignal.yaml")
ss = out.result.small_signal
print(f"is_stable        = {ss.is_stable}")
print(f"stability_margin = {ss.stability_margin:.4f} (max Re(λ))")
print(f"# eigenvalues    = {ss.eigenvalues.shape[0]}")
```

## Interpreting the result

### Damping table

```python
import numpy as np
import pandas as pd

df = pd.DataFrame({
    "real":     ss.eigenvalues.real,
    "imag":     ss.eigenvalues.imag,
    "freq_hz":  ss.frequencies_hz,
    "damping":  ss.damping_ratios,
})

# Sort by damping ratio (worst-damped first)
df["abs_imag"] = df["imag"].abs()
oscillatory = df[df["abs_imag"] > 0.01].copy()  # only oscillatory modes
oscillatory = oscillatory.sort_values("damping").head(10)
print(oscillatory.to_string())
```

Typical output:

```
     real      imag   freq_hz  damping
0  -0.21    7.15      1.14     0.029   ← worst damped
1  -0.42    6.93      1.10     0.061
2  -0.78   10.33      1.64     0.075
...
```

Row 0: ζ ≈ 3 %, below the 5 % threshold — **the system poorly damps a 1.14 Hz inter-area mode**. Classic case for adding a PSS or retuning the AVR.

### Complex-plane scatter

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.scatter(ss.eigenvalues.real, ss.eigenvalues.imag, alpha=0.6)
ax.axvline(0, color="red", linestyle="--", label="stability boundary")
ax.set_xlabel("Re(λ)  [1/s]")
ax.set_ylabel("Im(λ)  [rad/s]")
ax.legend()
plt.show()
```

Left of the red line = stable; right = unstable.

## Two analyzers

### `finite_difference`

Jacobian computed by **numerical differentiation**.

- 1–2 RHS evaluations per Jacobian column.
- Jacobian is `9 × ngen × ngen`-ish.
- Pros: **completely black-box**, no model derivation needed.
- Cons: sensitive to `epsilon` choice.

```yaml
small_signal:
  kind: finite_difference
  options: {epsilon: 1.0e-7, method: central}
```

### `modal`

Inherits from `finite_difference`, defaults `return_eigenvectors=True` and sorts by damping. **Use this for modal analysis**.

```yaml
small_signal:
  kind: modal
```

```python
ss = run("...yaml").result.small_signal
ss.eigenvectors      # (n_states, n_states) complex matrix
# Column j is the right eigenvector of eigenvalues[j]
```

## Participation factors

To identify "which state variable contributes most to which mode" you need the Hadamard product of right and left eigenvectors — the classical Verghese-Pérez-Arriaga formula.

pylectra returns `eigenvectors` but does **not** compute participation factors directly. Manual:

```python
import numpy as np
phi = ss.eigenvectors                    # right eigenvectors (columns)
psi = np.linalg.inv(phi)                 # left eigenvectors (rows)

# Participation factor P[i, k] = phi[i, k] * psi[k, i]
P = phi * psi.T                          # element-wise
P_abs = np.abs(P)
P_norm = P_abs / P_abs.sum(axis=0, keepdims=True)   # normalise per mode

# Top 5 states for the worst-damped mode
top_states = np.argsort(P_norm[:, 0])[::-1][:5]
print("Worst mode is dominated by these states:", top_states)
```

## Small-signal sweeps in batch mode

Use small-signal stability as a filter:

```yaml
mode: batch
small_signal:
  kind: finite_difference
filters:
  - kind: pf_converged
  - kind: small_signal_stable
    params:
      margin_max: -0.05      # require max Re(λ) ≤ -0.05 (minimum decay rate)
```

The `small_signal_stable` filter rejects unstable / poorly-damped samples, leaving a stable dataset.

## Performance hints

```
finite_difference takes ~ 9 * ngen RHS evaluations per Jacobian:
- case9    (3 gens)   → 27 evals  → ~50 ms
- case39   (10 gens)  → 90 evals  → ~200 ms
- case118  (54 gens)  → 486 evals → ~1.5 s
```

`method: forward` halves the evaluation count but is O(ε) rather than O(ε²). **`central` is the safe default**.

## FAQ

### Q: `stability_margin > 0` — what does it mean?

Equilibrium is unstable. But that **isn't necessarily a physical instability**:

- Power flow may have converged to the wrong equilibrium.
- Multi-machine init didn't reach steady state (loose `epsilon`).
- Model parameters are off.

First check `out.result.pf_success` and the ε reported in `ss.metadata`.

### Q: What is `drop_reference_mode`?

Power systems have one **degree of freedom**: rotating every rotor angle by a constant still satisfies the equations (reference-angle freedom). This produces a spurious λ = 0 mode in the Jacobian. With `drop_reference_mode: true`, the eigenvalue closest to 0 is excluded from the stability verdict.

### Q: Are `modal` and `finite_difference` numerically identical?

Yes — `modal` is `finite_difference` + sorting + eigenvectors-on by default.

## Next steps

- [pylectra.small_signal API](../reference/api/small_signal.md) — full field list.
- [Custom filters](../how-to/add-new-filter.md) — write your own small-signal criterion.
