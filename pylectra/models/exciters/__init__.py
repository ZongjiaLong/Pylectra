"""Exciter dynamic models.

Reference implementations:

* :mod:`pylectra.models.exciters.simple_avr` — first-order AVR with terminal-voltage
  feedback, name ``"simple_avr"``.
* :mod:`pylectra.models.exciters.constant` — constant ``Efd``, name ``"constant"``.
"""
from . import simple_avr    # noqa: F401
from . import constant      # noqa: F401
