"""``pylectra`` — Pythonic power-system dynamic-simulation framework.

Plugin registry, abstract base classes for every extension point, three
run modes (single / batch / CCT), YAML-driven configuration and
HDF5/Parquet sample storage.

See ``examples/*.yaml`` for typical configurations and the README for
guides on adding new generator models, ODE solvers and sample filters.
"""
from . import registry  # re-export so ``from pylectra import registry`` works

# Eagerly import every plugin sub-package so the registry is populated on
# ``import pylectra``.  Order matters only insofar as decorators must run before any
# lookup; data dependencies between plugins are resolved at *call* time.
from . import interfaces    # noqa: F401  (defines ABCs)
from . import models        # noqa: F401  (registers generators / exciters / governors / pss)
from . import solvers       # noqa: F401  (registers ODE solvers)
from . import powerflow     # noqa: F401  (registers Newton PF)
from . import faults        # noqa: F401  (registers BusFault)
from . import scenarios     # noqa: F401  (registers builtin scenarios)
from . import filters       # noqa: F401  (registers builtin filters + small_signal_stable)
from . import small_signal  # noqa: F401  (registers finite_difference + modal analyzers)

# Auto-discover any additional plugin modules (e.g. pylectra.cases, pylectra.plotting,
# third-party entry points) that aren't in the explicit list above.
from . import plugin_loader as _plugin_loader  # noqa: E402

_plugin_loader.discover()

from .run import run  # noqa: F401  (programmatic entry point)

from ._version import __version__  # noqa: E402

__all__ = ["registry", "interfaces", "run", "__version__"]
