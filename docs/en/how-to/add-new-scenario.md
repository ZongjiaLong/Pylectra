# Add a new scenario generator

_Advanced_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md), [Batch dataset generation](../tutorials/02-batch-generation.md)

## Goal

Write a perturbation plugin you can reference inside the `scenarios.generators` chain as `kind: my_scenario`.

## The interface

```python
from pylectra.interfaces.scenario import ScenarioGenerator, Scenario

class ScenarioGenerator(ABC):
    @abstractmethod
    def generate(self, base_case: NetworkCase, rng: np.random.Generator) -> Scenario:
        """Produce a perturbed Scenario from base_case.

        Returns
        -------
        Scenario
            A wrapper around the perturbed case + metadata describing the perturbation.
        """
```

Key rules:

- **Don't mutate `base_case`** — pylectra has already deep-copied for you.
- Use the supplied `rng` (do **not** call `np.random.*`) so batch determinism is preserved.
- Anything in `Scenario.metadata` is written into the Parquet metadata automatically (with `meta:` prefix).

## Working example: generator dispatch perturbation

```python
# pylectra/scenarios/gen_dispatch_perturb.py
"""Random per-generator active-power perturbation."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.registry import register
from pylectra.core.idx import PG          # gen matrix PG column (1-based col 2)


@register("scenario", "gen_dispatch")
@dataclass
class GenDispatchPerturb(ScenarioGenerator):
    sigma_pct: float = 5.0          # Gaussian sigma in percent
    clip_pct: float = 20.0          # clip to ±clip_pct%

    def generate(self, base_case, rng):
        case = base_case.copy()
        gen = case.gen
        n = gen.shape[0]

        factors = rng.normal(loc=1.0, scale=self.sigma_pct / 100.0, size=n)
        clip_lo = 1.0 - self.clip_pct / 100.0
        clip_hi = 1.0 + self.clip_pct / 100.0
        factors = np.clip(factors, clip_lo, clip_hi)

        gen[:, PG] *= factors

        return Scenario(
            case=case,
            metadata={
                "gen_dispatch_sigma_pct": self.sigma_pct,
                "gen_dispatch_factor_min": float(factors.min()),
                "gen_dispatch_factor_max": float(factors.max()),
            },
        )
```

Use it in YAML:

```yaml
scenarios:
  count: 100
  seed: 42
  generators:
    - kind: load_perturb
      params: {sigma_pct: 5.0}
    - kind: gen_dispatch                # ← new plugin
      params: {sigma_pct: 8.0, clip_pct: 25.0}
```

The Parquet metadata will gain `meta:gen_dispatch_factor_min` and `meta:gen_dispatch_factor_max` columns.

## Execution order of multiple generators

Generators in `scenarios.generators` execute in declaration order:

```
base_case
   │
   ▼
load_perturb         ──► case_v1
   │
   ▼
gen_dispatch         ──► case_v2
   │
   ▼
line_outage          ──► case_v3  ──► run simulation
```

**Each step sees what the previous step produced**, so order matters.

## Probabilistic perturbations

Make a perturbation fire only **with some probability** — sample `rng.random()`:

```python
@register("scenario", "occasional_step")
@dataclass
class OccasionalStep(ScenarioGenerator):
    bus: int = 1
    delta_pd: float = 100.0
    prob: float = 0.3                   # 30 % of samples get this perturbation

    def generate(self, base_case, rng):
        case = base_case.copy()
        applied = rng.random() < self.prob
        if applied:
            from pylectra.core.idx import PD
            case.bus[self.bus - 1, PD] += self.delta_pd
        return Scenario(
            case=case,
            metadata={"occasional_step_applied": int(applied)},
        )
```

After the batch, group by metadata:

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")
print(meta.groupby("meta:occasional_step_applied")["passed"].mean())
# 0    0.81     ← acceptance without the perturbation
# 1    0.62     ← acceptance with the perturbation
```

## Test

```python
# tests/unit/test_my_scenario.py
import numpy as np
from pylectra.core.case import NetworkCase
from pylectra.registry import get

def test_gen_dispatch_seed_determinism():
    """Same seed → identical result."""
    cls = get("scenario", "gen_dispatch")
    s = cls(sigma_pct=5.0, clip_pct=20.0)

    bus = np.zeros((3, 13))
    gen = np.array([[1, 100.0, 0, 0, 0, 1, 100, 1, 200, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]])
    case = NetworkCase({"baseMVA": 100.0, "bus": bus, "gen": gen,
                        "branch": np.zeros((1, 13))})

    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    out_a = s.generate(case, rng_a)
    out_b = s.generate(case, rng_b)
    np.testing.assert_array_equal(out_a.case.gen[:, 1], out_b.case.gen[:, 1])
```

## Troubleshooting

### `metadata` doesn't show up in the Parquet

- You returned something other than a `Scenario` object.
- `metadata` isn't a dict.
- The batch writer drops non-serialisable values (numpy arrays, complex numbers — convert to plain Python types first).

### Different runs produce different output

You called `np.random.*` instead of using the supplied `rng`. **Always use `rng`** — worker processes do not share the global RNG.

## Next steps

- [Add a new sample filter](add-new-filter.md) — same pattern.
- [load_perturb source](https://github.com/pylectra/pylectra/blob/main/pylectra/scenarios/perturb.py) — the built-in for reference.
