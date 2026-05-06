# `pylectra.registry`

_Reference_

**Prerequisites:** [What is a plugin](../../concepts/what-is-plugin.md)

The plugin registry + decorator.

## 12 whitelisted categories

```python
CATEGORIES = (
    "generator", "exciter", "governor", "pss",
    "ode_solver", "power_flow",
    "fault", "case", "scenario", "filter",
    "small_signal", "plot",
)
```

Category list is fixed — adding a new one requires a code change. Prevents plugin sprawl.

## `@register(category, name)`

Class decorator — inserts the class into `registry[category][name]`.

```python
from pylectra.registry import register
from pylectra.interfaces.fault import FaultEvent

@register("fault", "my_fault")
class MyFault(FaultEvent):
    def build_arrays(self):
        ...
```

**Raises**

- `ValueError` — `category` not in the whitelist.
- `ValueError` — `name` already registered (unless it's a re-import of the same class).

Registration also annotates the class:

- `cls.__plugin_category__ = category`
- `cls.__plugin_name__ = name`

## `get(category, name)`

```python
from pylectra.registry import get
cls = get("ode_solver", "scipy_dop853")
solver = cls()
```

Raises `KeyError` when missing; the error message lists every name currently registered in the category.

## `list_plugins(category=None)`

```python
from pylectra.registry import list_plugins

list_plugins("fault")
# {'fault': ['bus_fault', 'composite', 'line_trip', 'load_step']}

list_plugins()                          # all categories
# {'case': [...], 'exciter': [...], ...}
```

## `categories()`

```python
from pylectra.registry import categories
print(categories())
# ['case', 'exciter', 'fault', 'filter', 'generator',
#  'governor', 'ode_solver', 'plot', 'power_flow',
#  'pss', 'scenario', 'small_signal']
```

Returns only categories with **at least one** plugin (some whitelisted categories may be empty).

## `reset()`

```python
from pylectra.registry import reset
reset()                                 # clear everything
```

**Tests only.** Calling this in production code corrupts the import-time invariants.

## Auto-discovery

`import pylectra` triggers:

1. **Built-in** — `pylectra.plugin_loader.discover()` walks every sub-module of `pylectra` (excluding `_legacy`) with `pkgutil.walk_packages` and imports them.
2. **Third-party** — reads `importlib.metadata.entry_points(group="pylectra.plugins")` and imports the listed modules.

Third-party plugin packaging:

```toml
# In your pyproject.toml
[project.entry-points."pylectra.plugins"]
my_extension = "my_pkg.plugins"   # @register calls inside this module run
```

## Internal structure

```python
from pylectra.registry import _REGISTRY
# {category: {name: class}}
_REGISTRY["fault"]["bus_fault"]
# <class 'pylectra.faults.bus_fault.BusFault'>
```

> ⚠️ `_REGISTRY` is a private dict — **don't mutate it directly**. Doing so bypasses the duplicate-name check and corrupts the registry.

## Next steps

- [pylectra.interfaces](interfaces.md) — ABCs by category.
- [Plugins catalog](../plugins-catalog.md) — all built-ins.
