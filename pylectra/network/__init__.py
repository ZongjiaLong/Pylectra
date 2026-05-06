"""Native network-math primitives.

Pure numpy / scipy.sparse port of the legacy ``Auxiliary.AugYbus``,
``Auxiliary.MachineCurrents``, ``Auxiliary.SolveNetwork`` and
``PowerFlow.makeYbus`` — bit-identical, validated by
``tests/numerical/test_network_parity.py``.
"""
from __future__ import annotations

from .ybus import make_ybus, aug_ybus
from .machine_currents import machine_currents
from .solve import solve_network

__all__ = ["make_ybus", "aug_ybus", "machine_currents", "solve_network"]
