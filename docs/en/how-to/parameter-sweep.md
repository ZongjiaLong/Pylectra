# Run a parameter sweep

_Intermediate_

**Prerequisites:** [Single deterministic simulation](../tutorials/01-single-run.md)

Studies often "sweep one parameter and look at the response" — faulted bus, load magnitude, inertia constant. Three paths from simple to powerful.

## Path A — Python loop (most direct)

```python
from pylectra.run import run
import pandas as pd

records = []
for bus in [4, 14, 16, 21, 23, 26, 29]:
    for duration in [0.05, 0.10, 0.15]:
        out = run("examples/single_case39.yaml",
                  fault={"kind": "bus_fault",
                         "params": {"bus": bus,
                                    "t_fault": 0.2,
                                    "duration": duration}},
                  verbose=0,
                  plot=False)
        records.append({
            "bus": bus,
            "duration": duration,
            "max_dev": out.result.max_angle_deviation_deg,
            "pf_ok":   out.result.pf_success,
        })

df = pd.DataFrame(records)
print(df)
```

**Pros**: transparent, flexible, easy to add print/debug.
**Cons**: serial — 21 sims × 5 s each = 105 s.

## Path B — joblib parallel

```python
from joblib import Parallel, delayed
from pylectra.run import run

def _run_one(bus, duration):
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              verbose=0, plot=False)
    return {"bus": bus, "duration": duration,
            "max_dev": out.result.max_angle_deviation_deg}

# 7 buses × 3 durations = 21 jobs
combos = [(b, d) for b in [4, 14, 16, 21, 23, 26, 29] for d in [0.05, 0.10, 0.15]]
records = Parallel(n_jobs=-1, backend="loky")(
    delayed(_run_one)(b, d) for b, d in combos
)
```

**4-core machine**: ~30 s (vs 105 s serial).

> On Windows with a non-ASCII username, joblib's `loky` backend may need `JOBLIB_TEMP_FOLDER` redirected to an ASCII path — same fix as in the [batch determinism section](../tutorials/02-batch-generation.md#determinism-reproducibility).

## Path C — use batch mode

If your "parameter sweep" really is "produce N cases", `mode: batch` already handles parallelism / I/O / metadata. **The catch**: write a **deterministic** scenario generator (no randomness) that maps sample index → parameter combo.

```python
# pylectra/scenarios/sweep_param.py
from dataclasses import dataclass, field
from typing import List
from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.registry import register


@register("scenario", "param_sweep")
@dataclass
class ParamSweep(ScenarioGenerator):
    """Enumerate (bus × duration) combos by sample order."""
    buses: List[int] = field(default_factory=lambda: [16])
    durations: List[float] = field(default_factory=lambda: [0.05])

    def generate(self, base_case, rng):
        idx = int(rng.integers(0, 10_000_000))
        bus = self.buses[idx % len(self.buses)]
        duration = self.durations[(idx // len(self.buses)) % len(self.durations)]

        case = base_case.copy()
        return Scenario(
            case=case,
            metadata={"sweep_bus": bus, "sweep_duration": duration},
        )
```

> Honestly batch mode is built for **random perturbation**, not strict grid sweeps. **For strict grids, Path A or B is cleaner.**

## Path D — `pylectra.run.run_many`

```python
from pylectra.run import run_many
import yaml

configs = []
for bus in [4, 14, 16]:
    cfg = dict(yaml.safe_load(open("examples/single_case39.yaml")))
    cfg["fault"]["params"]["bus"] = bus
    configs.append(cfg)

results = run_many(configs)            # serial; for parallel use Path B
for cfg, out in zip(configs, results):
    print(cfg["fault"]["params"]["bus"], out.result.max_angle_deviation_deg)
```

`run_many` is the list-flavour of `run` — **serial** by design.

## Bonus — 2D heatmap from a sweep

```python
import numpy as np
import matplotlib.pyplot as plt

buses = [4, 14, 16, 21, 23, 26, 29]
durations = [0.02, 0.05, 0.08, 0.12, 0.16, 0.20]

mat = np.zeros((len(buses), len(durations)))
for i, b in enumerate(buses):
    for j, d in enumerate(durations):
        out = run("examples/single_case39.yaml",
                  fault={"kind": "bus_fault",
                         "params": {"bus": b, "t_fault": 0.2, "duration": d}},
                  verbose=0, plot=False)
        mat[i, j] = out.result.max_angle_deviation_deg

fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(mat, cmap="viridis", aspect="auto")
ax.set_xticks(range(len(durations)))
ax.set_xticklabels([f"{d*1000:.0f}" for d in durations])
ax.set_yticks(range(len(buses)))
ax.set_yticklabels(buses)
ax.set_xlabel("fault duration [ms]")
ax.set_ylabel("faulted bus")
plt.colorbar(im, label="max angle deviation [°]")
plt.show()
```

## Cache intermediate results

A long sweep that crashes mid-way is painful — persist each result:

```python
import pickle, os

cache_dir = "./sweep_cache"
os.makedirs(cache_dir, exist_ok=True)

def cached_run(bus, duration):
    cache = f"{cache_dir}/bus{bus}_dur{duration:.3f}.pkl"
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              verbose=0, plot=False)
    with open(cache, "wb") as f:
        pickle.dump(out.result, f)
    return out.result
```

## Which path when?

| Situation | Path |
|---|---|
| < 50 sims, interactive tweaking | A (Python loop) |
| 50–500, want parallel | B (joblib) |
| 500+, want persistence + metadata | batch + custom scenario |
| Reproduce a sweep | A/B + caching |

## Next steps

- [Batch dataset generation](../tutorials/02-batch-generation.md) — Path C in full.
- [Parallel batch](parallel-batch.md) — joblib backend choices.
