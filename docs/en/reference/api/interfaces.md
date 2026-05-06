# `pylectra.interfaces` (ABCs)

_Reference_

**Prerequisites:** [pylectra.registry](registry.md)

Each plugin category has an ABC declaring the methods plugins must implement. This page lists signatures only; usage examples live in the matching how-to pages.

## `GeneratorModel`

`pylectra/interfaces/generator.py`

```python
class GeneratorModel(ABC):
    type_id: int = 0           # type id (multi-machine dispatch)
    n_states: int = 4          # states per machine (uniform 4-column layout)

    @abstractmethod
    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA) -> tuple[np.ndarray, np.ndarray]:
        """Compute equilibrium from PF + machine params. Returns (Efd0 [n,], Xgen0 [n,4])."""

    @abstractmethod
    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq) -> np.ndarray:
        """dXgen/dt; shape (n, 4)."""

    @abstractmethod
    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (Id, Iq, Pe) from state + bus voltages."""
```

## `ExciterModel`

```python
class ExciterModel(ABC):
    type_id: int = 0
    n_states: int = 1

    @abstractmethod
    def init(self, Efd0_rows, Xgen0_rows, Pexc_rows, Vexc_rows) -> tuple[np.ndarray, np.ndarray]:
        """Return (Xexc0 [n, n_states], Pexc0 [n, ≥7])."""

    @abstractmethod
    def derivative(self, Xexc_rows, Xgen_rows, Pexc_rows, Vexc_rows, Vpss_rows) -> np.ndarray:
        """dXexc/dt; shape (n, n_states)."""
```

## `GovernorModel`

```python
class GovernorModel(ABC):
    type_id: int = 0
    n_states: int = 4

    @abstractmethod
    def init(self, Pm0_rows, Pgov_rows, omega0_rows) -> tuple[np.ndarray, np.ndarray]:
        ...

    @abstractmethod
    def derivative(self, Xgov_rows, Pgov_rows, Vgov_rows) -> np.ndarray:
        ...
```

## `PSSModel`

```python
class PSSModel(ABC):
    type_id: int = 0
    n_states: int = 0

    @abstractmethod
    def init(self, Ppss_rows) -> tuple[np.ndarray, np.ndarray]:
        ...

    @abstractmethod
    def derivative(self, Xpss_rows, Xgen_rows, Ppss_rows) -> np.ndarray:
        ...
```

## `ODESolver`

```python
class ODESolver(ABC):
    engine_kind: str               # "scipy" | "torch"
    legacy_method_id: int | None
    uses_native_engine: bool

    @abstractmethod
    def integrate(self, rhs, t_span, y0, events, options) -> SimulationResult:
        ...
```

## `PowerFlowSolver`

```python
class PowerFlowSolver(ABC):
    @abstractmethod
    def solve(self, case: NetworkCase, options: dict) -> NetworkCase:
        """Return the case with PF solution attached + success flag."""
```

## `FaultEvent`

```python
class FaultEvent(ABC):
    @abstractmethod
    def build_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (event, buschange, linechange)."""

    def to_loadevents_dict(self) -> dict:
        """Convenience wrapper. Default implementation provided."""
```

## `CaseLoader`

```python
class CaseLoader(ABC):
    name: str = ""

    @abstractmethod
    def load(self, identifier: str | dict) -> NetworkCase:
        ...
```

## `ScenarioGenerator`

```python
class ScenarioGenerator(ABC):
    @abstractmethod
    def generate(self, base_case: NetworkCase, rng: np.random.Generator) -> Scenario:
        ...

@dataclass
class Scenario:
    case: NetworkCase
    metadata: dict
```

## `SampleFilter`

```python
@dataclass
class FilterDecision:
    passed: bool
    reason: str = ""
    metric: float | None = None

class SampleFilter(ABC):
    name: str

    @abstractmethod
    def judge(self, result, scenario, case) -> FilterDecision:
        ...
```

## `SmallSignalAnalyzer`

```python
class SmallSignalAnalyzer(ABC):
    @abstractmethod
    def analyze(self, rhs, y0, layout, *, t0=0.0) -> SmallSignalResult:
        ...
```

See [pylectra.small_signal](small_signal.md) for `SmallSignalResult` fields.

## `PlotPlugin`

```python
class PlotPlugin(ABC):
    name: str
    input_kind: str       # "single" | "batch" | "case" | "sweep" | "small_signal"

    @abstractmethod
    def render(self, data, ax=None, **kwargs):
        """Plot and return a Figure / Axes."""

    def expected_inputs(self) -> dict:
        """Optional: declare expected kwargs. Default returns {}."""
```

## Next steps

- [Add a new generator](../../how-to/add-new-generator.md) — practice with `GeneratorModel`.
- [Plugins catalog](../plugins-catalog.md) — built-in implementations.
