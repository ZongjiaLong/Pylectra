# Contributing to pylectra

Welcome! The project is **plugin-first**: every extension point — generator
model, exciter, governor, PSS, ODE solver, fault type, scenario generator,
sample filter, small-signal analyser, case loader, plot renderer — is a
named entry in a global registry.  Adding new behaviour means **creating
one file and decorating one class**.  No `__init__.py` edits.  No core
patches.

## Dev setup

```bash
git clone <this-repo> && cd gridforge-py-main
pip install -e ".[dev]"            # core + pytest + ruff
pip install -e ".[dev,torch,viz]"  # plus GPU + interactive viz
pytest -q                          # fast suite (~12 s)
pytest -q -m slow                  # batch / CCT / parity / torch (~5 min)
```

The `slow` marker gates the integration regressions (`tests/integration/`).
Pre-merge CI runs both.

## Authoring a plugin (5-minute tour)

The pattern is identical for every category.  Example: a new ODE solver.

1. Create `pylectra/solvers/my_solver.py`:

   ```python
   from pylectra.interfaces.ode_solver import ODESolver
   from pylectra.registry import register

   @register("ode_solver", "my_solver")
   class MyAwesomeSolver(ODESolver):
       engine_kind = "scipy"           # or "torch"
       legacy_method_id = None          # legacy fixed-step solvers only
       uses_native_engine = True

       def integrate(self, rhs, t_span, y0, events, options):
           ...                          # return SimulationResult
   ```

2. Reference it in YAML:

   ```yaml
   solver:
     kind: my_solver
     options: {rtol: 1.0e-6}
   ```

3. Run.  No more steps.  `import pylectra` walks `pylectra/solvers/` via
   `pylectra.plugin_loader.discover()`, which triggers the decorator and
   populates the registry.

The same workflow applies to:

| Folder | Category | ABC |
|---|---|---|
| `pylectra/models/generators/` | `generator` | `pylectra.interfaces.GeneratorModel` |
| `pylectra/models/exciters/`   | `exciter`   | `pylectra.interfaces.ExciterModel` |
| `pylectra/models/governors/`  | `governor`  | `pylectra.interfaces.GovernorModel` |
| `pylectra/models/pss/`        | `pss`       | `pylectra.interfaces.PSSModel` |
| `pylectra/faults/`            | `fault`     | `pylectra.interfaces.FaultEvent` |
| `pylectra/scenarios/`         | `scenario`  | `pylectra.interfaces.ScenarioGenerator` |
| `pylectra/filters/`           | `filter`    | `pylectra.interfaces.SampleFilter` |
| `pylectra/cases/`             | `case`      | `pylectra.interfaces.CaseLoader` |
| `pylectra/small_signal/`      | `small_signal` | `pylectra.interfaces.SmallSignalAnalyzer` |
| `pylectra/plotting/`          | `plot`      | `pylectra.interfaces.PlotPlugin` |
| `pylectra/powerflow/`         | `power_flow` | `pylectra.interfaces.PowerFlowSolver` |

Third parties can also publish plugins via the `pylectra.plugins`
[entry-point group](https://packaging.python.org/en/latest/specifications/entry-points/) —
`pylectra.plugin_loader.discover()` picks them up automatically.

## Test expectations

- **Unit-test** every new plugin's pure logic (no simulation needed) in
  `tests/unit/`.
- **Numerical-test** any new model / solver against an analytic
  reference in `tests/numerical/` if one exists; otherwise against an
  existing implementation at `rtol=1e-12` (see
  `tests/numerical/test_two_axis_native.py` as a template).
- **Integration regressions** for changes that touch the simulation
  loop: re-run `tests/integration/test_batch_golden.py` and
  `test_cct_golden.py` and confirm the existing golden baselines still
  match.

## Import hygiene

`tests/unit/test_forbidden_imports.py` enforces that the public `pylectra/`
tree (everything outside `pylectra/_legacy/`) contains **zero** imports
from the seven retired top-level packages (`PowerFlow`, `Models`,
`Auxiliary`, `Solvers`, `Cases`, `rundyn`, `TimedomainSim`).  New code
must use `pylectra.X` modules; the legacy MATLAB-port helpers are private
to `pylectra/_legacy/` and only the vendored code itself is allowed to
cross-import them via the un-prefixed names.

## Code style

- 4-space indentation, type hints encouraged but not required.
- `ruff check pylectra/ tests/` for linting (rules in `pyproject.toml`).
- Docstrings: numpy-style; keep them tight on the *why*, not the *what*.

## Pull requests

- One topic per PR.  Plugin additions are usually one file + one test.
- Mention which categories you registered into in the PR description so
  reviewers can sanity-check `pylectra list-plugins` output.
- Slow tests must remain green; if a refactor changes the engine, run
  `pytest -m slow` locally before requesting review.
