"""ODE solver plugins.

Two flavours coexist:

* **Legacy-backed** (Phase 1): wrap one of the four legacy integrators
  (Modified Euler, RK4, RKF45, RK Higham-Hall).  They expose
  ``legacy_method_id`` so :class:`pylectra.runners.single.SingleRunner` knows
  which value to put in ``mdopt[0]``.  The actual stepping is done inside
  :func:`rundyn.rundyn`.

* **Native-engine-backed** (Phase 2): wrap a :mod:`scipy.integrate`
  ``OdeSolver`` subclass and run inside :class:`pylectra.engine.IntegrationLoop`.
  They set ``uses_native_engine = True`` and provide a ``make_stepper``
  classmethod.
"""

from . import modified_euler  # noqa: F401
from . import runge_kutta     # noqa: F401
from . import rkf             # noqa: F401
from . import rkhh            # noqa: F401
from . import scipy_solvers   # noqa: F401
from . import torch_solvers   # noqa: F401  (no-op if torch missing)

__all__ = ["modified_euler", "runge_kutta", "rkf", "rkhh", "scipy_solvers",
           "torch_solvers"]
