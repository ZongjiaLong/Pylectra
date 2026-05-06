# What is a plugin (in pylectra)?

_Intermediate_

**Prerequisites:** [What is a Python package](what-is-python-package.md)

## Analogy: a power strip

Power-systems engineers know power strips intimately. Imagine one:

- The strip itself defines a **standard socket interface** (voltage, current, plug shape).
- Any appliance that respects that interface plugs in and just works.
- You don't modify the strip to add a new appliance.

pylectra is exactly that kind of "strip". It defines a fixed set of **socket categories**:

| Socket category | What plugs in | Examples |
|---|---|---|
| `generator` | Generator dynamic models | `two_axis` (4th-order), `classical` (2nd-order swing) |
| `exciter` | Excitation systems | `simple_avr`, `constant` |
| `governor` | Turbine-governors | `ieee_g`, `constant_power` |
| `pss` | Power-system stabilisers | `none` |
| `ode_solver` | ODE solvers | `scipy_dop853`, `torch_dopri5` |
| `power_flow` | Power-flow solvers | `pandapower`, `newton` |
| `fault` | Faults / events | `bus_fault`, `line_trip`, `load_step` |
| `case` | Case loaders | `case39`, `case118` |
| `scenario` | Scenario perturbers | `load_perturb`, `line_outage` |
| `filter` | Sample filters | `voltage_range`, `angle_stability` |
| `small_signal` | Small-signal analysers | `finite_difference`, `modal` |
| `plot` | Visualisations | `rotor_angles`, `topology`, `heatmap` |

Whichever name you put in YAML is the plugin pylectra uses:

```yaml
solver: {kind: scipy_dop853}    # ← the "scipy_dop853" plugin under the "ode_solver" category
```

## The mechanism: registry + decorator

Internally pylectra keeps a single **registry** — just a table:

```
"ode_solver" → {
    "scipy_rk45":    <class ScipyRK45>,
    "scipy_dop853":  <class ScipyDOP853>,
    "torch_dopri5":  <class TorchDOPRI5>,
    ...
}
```

A new plugin is added by a one-line Python decorator:

```python
from pylectra.interfaces.ode_solver import ODESolver
from pylectra.registry import register

@register("ode_solver", "my_solver")
class MyAwesomeSolver(ODESolver):
    def integrate(self, rhs, t_span, y0, events, options):
        ...
```

What does `@register("ode_solver", "my_solver")` do?
It is equivalent to:

```python
class MyAwesomeSolver(ODESolver):
    ...

# Insert into registry["ode_solver"]["my_solver"]
registry.register("ode_solver", "my_solver")(MyAwesomeSolver)
```

As long as Python imports the file once, the plugin is registered.

## Automatic discovery

`import pylectra` automatically:

1. Walks every sub-module of `pylectra/` with `pkgutil.walk_packages`.
2. Imports each one — triggering every `@register` decorator inside.
3. Fills the registry.

So **adding one `.py` file is enough** — no `__init__.py` edits, no framework patches.

Third-party packages can publish plugins via the `pylectra.plugins`
entry-point group:

```toml
# pyproject.toml of a third-party package
[project.entry-points."pylectra.plugins"]
my_pack = "my_package.plugins"
```

`pylectra.plugin_loader.discover()` picks them up automatically.

## Abstract base classes (ABCs)

Each plugin category has a corresponding **abstract base class** that lists the methods every plugin must implement. For example `ODESolver`:

```python
class ODESolver(ABC):
    engine_kind: str           # "scipy" or "torch"

    @abstractmethod
    def integrate(self, rhs, t_span, y0, events, options):
        """Must return a SimulationResult."""
```

Inheriting from it forces you to implement `integrate`; otherwise Python refuses to instantiate the class. The ABC is the **contract**: as long as you honour it, the framework can use your plugin.

Analogy: lab "standard-interface" instruments — any oscilloscope that speaks GPIB/SCPI plugs into an automated test system, regardless of brand.

## List every registered plugin

```bash
python -m pylectra info
```

Sample output:

```
generator    : ['classical', 'two_axis']
exciter      : ['constant', 'simple_avr']
governor     : ['constant_power', 'ieee_g']
ode_solver   : ['scipy_rk45', 'scipy_dop853', 'torch_dopri5', ...]
fault        : ['bus_fault', 'line_trip', 'load_step', 'composite']
...
```

Or from Python:

```python
import pylectra
from pylectra import registry
print(registry.list_plugins("fault"))
# {'fault': ['bus_fault', 'composite', 'line_trip', 'load_step']}
```

## Why this design

Power-systems research diverges quickly — different groups have their own generator models, fault types, filtering criteria. The traditional approach — "fork the simulator and patch sources" — splits you from upstream the moment they release a new version.

The plugin model lets:

- Your extension live as a **single `.py` file**, untouched by the framework.
- A pylectra major upgrade leave your extensions alone.
- One YAML config combine **built-in plugins + your local plugins + plugins from third-party packages** simultaneously.

## Next steps

- [How to add a new generator model](../how-to/add-new-generator.md) — write a generator plugin from scratch.
- [Pylectra architecture overview](architecture.md) — how the registry, engine, and runners cooperate.
