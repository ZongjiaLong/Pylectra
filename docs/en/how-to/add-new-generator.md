# Add a new generator model

_Advanced_

**Prerequisites:** [What is a plugin](../concepts/what-is-plugin.md), [Pylectra architecture](../concepts/architecture.md)

## Goal

Write a **custom generator dynamic model** referenced from YAML as `kind: my_gen`.

## Four steps

### 1. Create the file

```
pylectra/models/generators/my_gen.py
```

The filename is up to you. Files under `pylectra/models/generators/` are auto-discovered at startup.

### 2. Inherit the ABC + decorator

```python
# pylectra/models/generators/my_gen.py
"""Three-state generator example (delta, omega, Eq')."""
from __future__ import annotations
import numpy as np
from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register


@register("generator", "my_gen")           # ← name used in YAML
class MyGenerator(GeneratorModel):
    type_id = 99                           # 1–99 typically; avoid 1/2 (built-in)
    n_states = 4                           # state vector length (use the 4-col layout; pad unused)

    # 1) Initialisation — equilibrium from PF + machine params
    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA):
        ...
        return Efd0, Xgen0     # Efd0 shape (n,), Xgen0 shape (n, 4)

    # 2) Derivatives — dy/dt = f(y)
    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq):
        F = np.zeros_like(Xgen_rows)
        ...
        return F               # (n, 4)

    # 3) Currents — (Id, Iq, Pe) from state + bus voltages
    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows):
        ...
        return Id, Iq, Pe      # each shape (n,)
```

### 3. Reference it from YAML

```yaml
mode: single
case_pf: case39
case_dyn: case39dyn
dynamics:
  defaults:
    generator: {kind: my_gen}
solver: {kind: scipy_dop853}
fault:
  kind: bus_fault
  params: {bus: 16, t_fault: 0.2, duration: 0.05}
```

### 4. Run

```bash
python -m pylectra info | grep generator        # should now list my_gen
python -m pylectra run my_config.yaml
```

## Working example: 3-state model

```python
# pylectra/models/generators/three_state.py
"""Third-order generator: drop the d-axis transient EMF (Ed' = 0).

State: [delta, omega, Eq', 0]
Equations:
    dδ/dt   = ω - ω_s
    dω/dt   = (π·f / H) · (Pm - Pe)
    dEq'/dt = (Efd - Eq' + (xd - xd')·Id) / Td0'
"""
import numpy as np
from pylectra.interfaces.generator import GeneratorModel
from pylectra.registry import register
from pylectra.core.idx import idx_gen
from pylectra.core import freq as _f


@register("generator", "three_state")
class ThreeStateGenerator(GeneratorModel):
    type_id = 99
    n_states = 4

    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA):
        (GEN_BUS, PG, QG, *_) = idx_gen()
        n = Pgen_rows.shape[0]
        Xgen0 = np.zeros((n, 4))
        Efd0 = np.zeros(n)
        if n == 0:
            return Efd0, Xgen0

        xd_tr = Pgen_rows[:, 8]
        xd    = Pgen_rows[:, 10]
        xq    = Pgen_rows[:, 11]

        omega0 = np.full(n, 2.0 * np.pi * float(_f.freq))
        Ia0 = (gen_rows[:, PG] - 1j * gen_rows[:, QG]) / np.conj(U_rows) / baseMVA
        phi0 = np.angle(Ia0)
        Eq0 = U_rows + 1j * xq * Ia0
        delta0 = np.angle(Eq0)
        Id0 = -np.abs(Ia0) * np.sin(delta0 - phi0)

        Efd0[:] = np.abs(Eq0) - (xd - xq) * Id0
        Eq_tr0 = Efd0 + (xd - xd_tr) * Id0

        Xgen0[:, 0] = delta0
        Xgen0[:, 1] = omega0
        Xgen0[:, 2] = Eq_tr0
        # col 3 (Ed') stays at 0
        return Efd0, Xgen0

    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq):
        omegas = 2.0 * np.pi * float(freq)
        omega = Xgen_rows[:, 1]
        Eq_tr = Xgen_rows[:, 2]

        H      = Pgen_rows[:, 6]
        xd_tr  = Pgen_rows[:, 8]
        xd     = Pgen_rows[:, 10]
        Td0_tr = Pgen_rows[:, 12]

        Id = Vgen_rows[:, 0]
        Pe = Vgen_rows[:, 2]
        Efd = Xexc_rows[:, 0]
        Pm  = Xgov_rows[:, 0]

        F = np.zeros_like(Xgen_rows)
        F[:, 0] = omega - omegas
        F[:, 1] = (np.pi * float(freq) / H) * (Pm - Pe)
        F[:, 2] = (Efd - Eq_tr + (xd - xd_tr) * Id) / Td0_tr
        # col 3 (Ed') unchanged
        return F

    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows):
        delta = Xgen_rows[:, 0]
        Eq_tr = Xgen_rows[:, 2]
        xd_tr = Pgen_rows[:, 8]
        xq_tr = Pgen_rows[:, 9]

        theta = np.angle(Ubus_rows)
        absU  = np.abs(Ubus_rows)
        vd = -absU * np.sin(delta - theta)
        vq =  absU * np.cos(delta - theta)

        Id = (vq - Eq_tr) / xd_tr
        Iq = -vd / xq_tr                      # Ed' = 0
        Pe = Eq_tr * Iq + (xd_tr - xq_tr) * Id * Iq
        return Id, Iq, Pe
```

## Add a test (recommended)

```python
# tests/numerical/test_three_state.py
import numpy as np
import pylectra
from pylectra.registry import get

def test_three_state_init_steady():
    """init should yield dδ/dt ≈ 0 — a steady state."""
    gen = get("generator", "three_state")()
    # ... build Pgen / U / gen inputs
    Efd0, Xgen0 = gen.init(Pgen, U, gen_rows, baseMVA=100.0)
    F = gen.derivative(Xgen0, Xexc0, Xgov0, Pgen, Vgen0, freq=60.0)
    assert np.max(np.abs(F)) < 1e-6           # steady state ≈ 0 derivative
```

## Troubleshooting

### "Plugin name 'my_gen' is already registered"

Pick a different name — the registry already has one.

### YAML `kind: my_gen` raises `KeyError`

`import pylectra` didn't pick up your file. Check:

- The file lives **inside `pylectra/models/generators/`** (not `pylectra/my_models/`).
- The filename **doesn't start with `_`** (`pkgutil.walk_packages` skips those).
- The decorator **uses category `"generator"` exactly**.

### `derivative` after `init` isn't ≈ 0

Initial conditions aren't truly stationary. Most often: wrong column indices in `Pgen_rows`. **Cross-check with `pylectra/models/generators/two_axis.py`** for the canonical layout.

## Publishing as a third-party package

Don't want to fork pylectra? Ship plugins via an entry point:

```toml
# my_package/pyproject.toml
[project.entry-points."pylectra.plugins"]
my_models = "my_package.generators"
```

`my_package/generators/__init__.py` should import every submodule it wants registered — `pylectra.plugin_loader.discover()` then picks them up automatically.

## Next steps

- [pylectra.interfaces ABC reference](../reference/api/interfaces.md) — full method signatures.
- [Add a new fault type](add-new-fault.md) — same pattern, different ABC.
- [Plugins catalog](../reference/plugins-catalog.md) — built-in generators for comparison.
