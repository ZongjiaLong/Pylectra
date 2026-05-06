"""Core building blocks of the ``pylectra`` package.

* :class:`pylectra.core.case.NetworkCase` — friendly wrapper around the legacy
  ``mpc`` dict (``baseMVA``, ``bus``, ``gen``, ``branch``).
* :class:`pylectra.core.system.DynamicSystem` — owns one network case + its
  dynamic data; replaces the giant argument list of :func:`rundyn`.
* :class:`pylectra.core.result.SimulationResult` — typed bundle of the time
  series returned by a simulation run.
"""

from .case import NetworkCase
from .system import DynamicSystem
from .result import SimulationResult

__all__ = ["NetworkCase", "DynamicSystem", "SimulationResult"]
