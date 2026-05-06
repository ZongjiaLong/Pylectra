"""Generator dynamic models.

Reference implementations:

* :mod:`pylectra.models.generators.classical` — 2nd-order swing equation
  (constant flux behind transient reactance), name ``"classical"``.
* :mod:`pylectra.models.generators.two_axis` — 4th-order two-axis model
  with d/q transient EMFs, name ``"two_axis"``.
"""
from . import two_axis    # noqa: F401  (registers "two_axis")
from . import classical   # noqa: F401  (registers "classical")
