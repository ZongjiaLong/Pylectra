# Critical Clearing Time (CCT) analysis

_Intermediate_

**Prerequisites:** [Single deterministic simulation](01-single-run.md)

## What is CCT?

**CCT (Critical Clearing Time)** is a classic transient-stability metric:

> "After a fault, how many seconds can pass before clearing it, and still keep the system stable?"

- Cleared **early** → short disturbance, system recovers.
- Cleared **late** → rotor angles drift too far apart, the system loses synchronism.

CCT is the boundary between stable and unstable. Algorithmically it's a **bisection search**: try fault durations in `[low, high]` repeatedly, narrowing in on the boundary.

## YAML template

```yaml
mode: cct

case_pf:  case39
case_dyn: case39dyn
power_flow: {kind: newton}
solver:     {kind: modified_euler}

cct:
  bus: 16             # faulted bus
  t_fault: 0.2        # fault apply time (fixed)
  low: 0.01           # bisection lower bound (must be stable)
  high: 0.30          # bisection upper bound (must be unstable)
  tol: 0.005          # convergence tolerance [s]
  max_iter: 15        # maximum bisection iterations
  stability_filter:
    kind: angle_stability      # how to judge stability
    params:
      max_dev_deg: 180.0

verbose: 1
```

## Run it

```bash
python -m pylectra run examples/cct_case39.yaml
```

Output:

```
[cct] bracket check: low=0.01, high=0.3 (snapped to step 0.001)
[cct] iter  0: duration=0.1500 → unstable
[cct] iter  1: duration=0.0750 → stable
[cct] iter  2: duration=0.1125 → stable
[cct] iter  3: duration=0.1310 → unstable
[cct] iter  4: duration=0.1218 → stable
[cct] iter  5: duration=0.1264 → stable
[cct] iter  6: duration=0.1287 → unstable
[cct] iter  7: duration=0.1276 → unstable
[cct] CCT ≈ 0.1264 s (bracket [0.1264, 0.1276], 8 iters, converged=True)
```

Each iteration runs a full simulation (~10 total). For case39 + bus 16, CCT ≈ **127 ms**.

## Bracket sanity checks

Before bisecting, pylectra verifies:

- `duration = low` → must be **stable** (otherwise CCT lies below `low`; result invalid).
- `duration = high` → must be **unstable** (otherwise CCT lies above `high`; bracket misses it).

If either check fails, no bisection runs — instead a warning:

```
CCT outside bracket [0.01, 0.30]; widen the bracket.
```

## Choosing a stability criterion

`cct.stability_filter` defines "what counts as stable". Two common picks:

### `angle_stability` (recommended default)

```yaml
stability_filter:
  kind: angle_stability
  params:
    max_dev_deg: 180.0    # any rotor angle further than 180° from the COI = lost synchronism
```

180° is the textbook first-swing threshold. For conservative studies use 120° or 90°.

### `voltage_range` (voltage stability)

```yaml
stability_filter:
  kind: voltage_range
  params:
    vmin: 0.7
    vmax: 1.2
    tail_fraction: 0.3
```

Counts as "voltage-unstable" if bus voltages don't recover to the band after the fault.

### Composite criteria

Only one `stability_filter` allowed. To enforce "angle-stable AND voltage-stable", write a **custom filter** ([how-to](../how-to/add-new-filter.md)) that ANDs multiple criteria.

## Programmatic call

```python
from pylectra.run import run

out = run("examples/cct_case39.yaml", verbose=0)
print(f"CCT = {out.result.cct * 1000:.1f} ms")
print(f"  bracket:   [{out.result.bracket_low:.4f}, {out.result.bracket_high:.4f}]")
print(f"  iters:     {out.result.iterations}")
print(f"  converged: {out.result.converged}")
```

## Use case: CCT-by-bus sweep

```python
from pylectra.run import run
import matplotlib.pyplot as plt

buses = [4, 14, 16, 21, 23, 26, 29]
ccts = []
for b in buses:
    out = run("examples/cct_case39.yaml",
              cct={"bus": b, "t_fault": 0.2, "low": 0.01, "high": 0.40,
                   "tol": 0.005, "max_iter": 15,
                   "stability_filter": {"kind": "angle_stability",
                                        "params": {"max_dev_deg": 180.0}}},
              verbose=0)
    ccts.append(out.result.cct)
    print(f"bus {b}: CCT = {out.result.cct*1000:.1f} ms")

plt.bar([str(b) for b in buses], [c * 1000 for c in ccts])
plt.xlabel("faulted bus")
plt.ylabel("CCT [ms]")
plt.show()
```

> Slow (~10 sims per bar × 7 = 70 sims). Speed up with [`scipy_dop853`](01-single-run.md#choosing-a-solver) or wrap the loop in joblib.

## FAQ

### Q: Why pick a `[0.01, 0.30]` bracket?

Too narrow triggers the bracket-sanity failure; too wide wastes iterations. Rule of thumb:

- **IEEE benchmark cases (39 / 68 / 118)**: `[0.01, 0.40]`.
- **Small microgrids**: `[0.001, 0.10]`.
- **Large transmission grids**: `[0.05, 0.50]`.

### Q: What does `tol: 0.005` mean?

The bisection stops once `bracket_high - bracket_low ≤ 0.005 s`. **5 ms precision is usually enough** — CCT itself has ±10 ms physical uncertainty driven by fault type and protection coordination.

### Q: Power flow + initialisation re-runs every iteration?

Yes — fault duration changes the event schedule. The case itself doesn't change so PF always converges (one less thing to debug).

### Q: Does the `modified_euler` solver introduce step quantisation?

Yes. With a 1 ms step, events can only fire on integer milliseconds. pylectra's CCT runner **snaps candidates to the step grid** automatically, so `tol < stepsize` is meaningless.
**Adaptive solvers (`scipy_dop853`) avoid this**.

## Using CCT as a batch filter

CCT itself is a top-level mode, but you can also use it the other way around — **only accept scenarios in batch mode whose CCT exceeds a threshold**. That's an advanced pattern: write a custom filter that internally runs a CCT sub-procedure. See [the custom-filter how-to](../how-to/add-new-filter.md).

## Next steps

- [Small-signal stability analysis](05-small-signal.md) — CCT covers large-disturbance stability; small-signal covers local linearised stability. Complementary.
- [Visualization tutorial](04-visualization.md) — turn CCT sweeps into publication-quality plots.
- [API: pylectra.run.run()](../reference/api/run.md) — full programmatic signature.
