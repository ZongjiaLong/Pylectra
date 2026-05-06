# Add a new sample filter

_Advanced_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md), [Batch dataset generation](../tutorials/02-batch-generation.md)

## Goal

Write a sample-acceptance plugin usable as `kind: my_filter` in batch / CCT mode.

## The interface

```python
from pylectra.interfaces.filter import SampleFilter, FilterDecision

class SampleFilter(ABC):
    name: str
    @abstractmethod
    def judge(self, result: SimulationResult, scenario, case) -> FilterDecision:
        """Decide whether this simulation passes.

        Returns
        -------
        FilterDecision(passed: bool, reason: str, metric: float | None)
        """
```

All three `FilterDecision` fields land in the Parquet metadata:

- `passed` → drives the global `passed` column (any rejection ⇒ `False`).
- `reason` → recorded in `rejected_reason` / `rejected_by` for the first reject.
- `metric` → a single float written to `filter_<name>_metric`.

## Working example: frequency deviation criterion

```python
# pylectra/filters/frequency_deviation.py
"""Stability criterion: post-fault frequency deviation stays within a band."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from pylectra.interfaces.filter import SampleFilter, FilterDecision
from pylectra.registry import register


@register("filter", "frequency_deviation")
@dataclass
class FrequencyDeviationFilter(SampleFilter):
    name: str = "frequency_deviation"
    max_dev_hz: float = 0.5             # max allowed |Δf| [Hz]
    after_seconds: float = 0.5          # ignore everything before this time

    def judge(self, result, scenario, case):
        if not result.pf_success:
            return FilterDecision(False, "PF failed", metric=float("nan"))

        # Speeds is omega/(2π·f₀) p.u.; deviation = (Speeds - 1) × f₀ Hz
        f0 = 60.0          # assumes 60 Hz; you can read it from case.dyn freq
        delta_f = (result.Speeds - 1.0) * f0    # (T, n_gen)

        # Skip the fault window
        t = result.Time
        mask = t > self.after_seconds
        if not mask.any():
            return FilterDecision(False, "trajectory too short")

        max_dev = float(np.max(np.abs(delta_f[mask])))
        passed = max_dev <= self.max_dev_hz
        reason = f"max |Δf| = {max_dev:.3f} Hz" + ("" if passed else f" > {self.max_dev_hz}")
        return FilterDecision(passed=passed, reason=reason, metric=max_dev)
```

YAML:

```yaml
filters:
  - kind: pf_converged
  - kind: frequency_deviation
    params:
      max_dev_hz: 0.3
      after_seconds: 0.5
```

After the batch:

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")

# Distribution of the new filter's metric
print(meta["filter_frequency_deviation_metric"].describe())

# Samples rejected only by the new filter
rejected = meta[~meta["passed"] & (meta["rejected_by"] == "frequency_deviation")]
print(f"Rejected by frequency deviation: {len(rejected)}")
```

## Composite criteria

Only one `stability_filter` is allowed in CCT, but you can compose multiple:

```python
@register("filter", "angle_and_freq")
@dataclass
class AngleAndFreqFilter(SampleFilter):
    name: str = "angle_and_freq"
    max_dev_deg: float = 180.0
    max_dev_hz: float = 0.5

    def judge(self, result, scenario, case):
        from pylectra.registry import get
        d_ang = get("filter", "angle_stability")(max_dev_deg=self.max_dev_deg).judge(result, scenario, case)
        d_frq = get("filter", "frequency_deviation")(max_dev_hz=self.max_dev_hz).judge(result, scenario, case)
        if not d_ang.passed:
            return d_ang
        if not d_frq.passed:
            return d_frq
        return FilterDecision(passed=True, reason="ok",
                              metric=max(d_ang.metric or 0, d_frq.metric or 0))
```

## "Heavy" filters: inline small-signal

To enforce small-signal stability in batch, use the built-in `small_signal_stable` filter — but it requires `small_signal` to be enabled in the batch YAML so `result.small_signal` is populated:

```yaml
mode: batch
small_signal: {kind: finite_difference}      # compute eigenvalues per sample
filters:
  - kind: pf_converged
  - kind: angle_stability
  - kind: small_signal_stable
    params: {margin_max: -0.05}              # max Re(λ) ≤ -0.05
```

## Test

```python
# tests/unit/test_my_filter.py
import math
from pylectra.registry import get

class _StubResult:
    def __init__(self, ok):
        self.pf_success = ok
        # Simplified — build a result-like stub for your test

def test_frequency_filter_pf_failed_rejects():
    f = get("filter", "frequency_deviation")()
    d = f.judge(_StubResult(ok=False), None, None)
    assert d.passed is False
    assert "PF failed" in d.reason
    assert math.isnan(d.metric)
```

## Practical tips

| Need | Pattern |
|---|---|
| Only check the post-fault window | mask via `result.Time` (e.g. `after_seconds`) |
| Worst-case across machines | `np.max(np.abs(...), axis=0)` then `max` again |
| Multiple checks | compose via a wrapper filter, or write a single combined filter |
| Custom metadata columns | `metric` is one float; for multiple values, emit them through scenario metadata instead |

## Troubleshooting

### `metric` ends up NaN

Usually the power flow failed → result arrays are empty → `np.max()` raises on the empty array. **Always test `result.pf_success` first.**

### Metric column appears in Parquet but is all NaN

The `name` field isn't set. pylectra builds the column key from `name`: `filter_<name>_metric`.

## Next steps

- [Add a new plot type](add-new-plot.md) — visualise your batch results.
- [Batch tutorial](../tutorials/02-batch-generation.md) — refresher on the filter chain.
