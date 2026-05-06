"""Model plugin wrappers around the legacy ``Models/`` procedural code.

These thin classes register themselves with :mod:`pylectra.registry` so they can be
referenced from YAML configurations.  In Phase 1 the legacy
:func:`rundyn`-driven inner loop continues to do the actual integration; the
classes here provide:

* a forward-compatible interface (Phase 2 will move the integration loop into
  ``pylectra`` and dispatch through these classes),
* a place for users to subclass and register *new* model types without
  touching the legacy code.

Adding a new model type today:

1. Subclass :class:`pylectra.interfaces.GeneratorModel`.
2. Decorate with ``@register("generator", "<name>")`` and set ``type_id`` to
   the integer that will appear in column 0 of ``Pgen``.
3. Implement ``init``, ``derivative``, ``currents``.

The new plugin will be live in Phase 2 once the native ODE loop ships.
"""

from . import generators
from . import exciters
from . import governors
from . import pss

__all__ = ["generators", "exciters", "governors", "pss"]
