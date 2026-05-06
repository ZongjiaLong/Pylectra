# `pylectra.interfaces` 抽象基类

_参考资料_

**前置阅读：** [pylectra.registry](registry.md)

每个插件类别对应一个 ABC，定义"必须实现什么方法"。本页只列签名；详细使用例见对应的 how-to。

## `GeneratorModel`

`pylectra/interfaces/generator.py`

```python
class GeneratorModel(ABC):
    type_id: int = 0           # 类型 id（多机分配时用）
    n_states: int = 4          # 每机状态数（统一 4 列布局）

    @abstractmethod
    def init(self, Pgen_rows, U_rows, gen_rows, baseMVA) -> tuple[np.ndarray, np.ndarray]:
        """从潮流解 + 多机参数算稳态。返回 (Efd0 [n,], Xgen0 [n,4])。"""

    @abstractmethod
    def derivative(self, Xgen_rows, Xexc_rows, Xgov_rows,
                   Pgen_rows, Vgen_rows, freq) -> np.ndarray:
        """dXgen/dt，形状 (n, 4)。"""

    @abstractmethod
    def currents(self, Xgen_rows, Pgen_rows, Ubus_rows) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """从状态 + 母线电压算 (Id, Iq, Pe)。"""
```

## `ExciterModel`

```python
class ExciterModel(ABC):
    type_id: int = 0
    n_states: int = 1

    @abstractmethod
    def init(self, Efd0_rows, Xgen0_rows, Pexc_rows, Vexc_rows) -> tuple[np.ndarray, np.ndarray]:
        """返回 (Xexc0 [n, n_states], Pexc0 [n, ≥7])。"""

    @abstractmethod
    def derivative(self, Xexc_rows, Xgen_rows, Pexc_rows, Vexc_rows, Vpss_rows) -> np.ndarray:
        """dXexc/dt，形状 (n, n_states)。"""
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
        """返回成功标记 + 解后的 case。"""
```

## `FaultEvent`

```python
class FaultEvent(ABC):
    @abstractmethod
    def build_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """返回 (event, buschange, linechange)。"""

    def to_loadevents_dict(self) -> dict:
        """便利：用 dict 形式返回。默认实现已有。"""
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

详见 [pylectra.small_signal](small_signal.md)。

## `PlotPlugin`

```python
class PlotPlugin(ABC):
    name: str
    input_kind: str       # "single" | "batch" | "case" | "sweep" | "small_signal"

    @abstractmethod
    def render(self, data, ax=None, **kwargs):
        """画图，返回 Figure / Axes。"""

    def expected_inputs(self) -> dict:
        """可选：声明期望的 kwargs。默认返回空 dict。"""
```

## 接下来读什么

- [添加新发电机](../../how-to/add-new-generator.md) — 实操 GeneratorModel
- [插件清单](../plugins-catalog.md) — 内置实现
