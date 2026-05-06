"""Abstract base classes — every extension point in ``pylectra``.

Each ABC pins the contract that plugins must satisfy.  All ABCs are kept small
on purpose: implementing one rarely takes more than a dozen lines, and the
plugin can delegate to the existing legacy code.
"""

from .generator import GeneratorModel
from .exciter import ExciterModel
from .governor import GovernorModel
from .pss import PSSModel
from .ode_solver import ODESolver, StepResult
from .power_flow import PowerFlowSolver
from .fault import FaultEvent, FaultSpec
from .scenario import ScenarioGenerator, Scenario
from .filter import SampleFilter, FilterDecision
from .small_signal import SmallSignalAnalyzer, SmallSignalResult
from .case_loader import CaseLoader
from .plot import PlotPlugin

__all__ = [
    "GeneratorModel",
    "ExciterModel",
    "GovernorModel",
    "PSSModel",
    "ODESolver",
    "StepResult",
    "PowerFlowSolver",
    "FaultEvent",
    "FaultSpec",
    "ScenarioGenerator",
    "Scenario",
    "SampleFilter",
    "FilterDecision",
    "SmallSignalAnalyzer",
    "SmallSignalResult",
    "CaseLoader",
    "PlotPlugin",
]
