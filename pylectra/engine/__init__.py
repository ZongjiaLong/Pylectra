"""Native ODE engine — Phase 2 replacement for the legacy ``rundyn`` loop.

Provides a generic ``IntegrationLoop`` that drives any
:class:`scipy.integrate.OdeSolver` instance through a power-system transient
simulation, with proper structural-event handling (faults switching in /
out, line trips, bus changes).

Phase 2a scope: PSS type-3 (= no PSS) only.  Mixing PSS dynamics with the
adaptive integrator requires the discrete ``PSSoutput`` update which the
legacy hand-coded solvers handle inside their substeps; that's deferred.
"""

from .state import StateLayout
from .rhs import DynamicsRHS, NetworkSolver
from .loop import IntegrationLoop, IntegrationResult
from .equilibrium import Equilibrium, compute_equilibrium

__all__ = [
    "StateLayout",
    "DynamicsRHS",
    "NetworkSolver",
    "IntegrationLoop",
    "IntegrationResult",
    "Equilibrium",
    "compute_equilibrium",
]
