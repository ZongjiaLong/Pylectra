"""Governor dynamic models.

Reference implementations:

* :mod:`pylectra.models.governors.constant_power` — ``dPm/dt = 0``, name
  ``"constant_power"``.
* :mod:`pylectra.models.governors.ieee_g` — 4-state IEEE turbine-governor,
  name ``"ieee_g"``.
"""
from . import constant_power   # noqa: F401
from . import ieee_g           # noqa: F401
