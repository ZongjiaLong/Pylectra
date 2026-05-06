# Pylectra

[![Docs](https://img.shields.io/badge/docs-online-blue?logo=readthedocs&logoColor=white)](https://zongjialong.github.io/Pylectra/)
[![Docs CN](https://img.shields.io/badge/中文文档-在线-blue)](https://zongjialong.github.io/Pylectra/zh/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#license--attribution)

A plugin-based Python framework for **power-system dynamic simulation** and large-scale **dataset generation**. Every component — generator model, exciter, governor, ODE solver, fault, scenario, sample filter, plot — is a registered plugin selectable by name from a YAML config file. Adding a new one means creating a single file and applying the `@register` decorator.

📖 **Read the docs online**: **[zongjialong.github.io/Pylectra](https://zongjialong.github.io/Pylectra/)** (English) · **[中文](https://zongjialong.github.io/Pylectra/zh/)**

The site has a searchable, themed view of everything in [`docs/`](docs/) (English and 中文) with light/dark mode and a language switcher. You can also build it locally with `mkdocs serve` — see the [Documentation](#documentation) section below.

---

## Highlights

- **Three run modes**, one schema:
  - `single` — deterministic transient simulation
  - `batch` — generate N perturbed scenarios → HDF5 + Parquet metadata
  - `cct` — bisection search for critical clearing time
- **Pluggable ODE solvers**: SciPy (`scipy_rk45`, `scipy_dop853`, `scipy_lsoda`, `scipy_bdf`, `scipy_radau`, …) plus optional GPU-accelerated `torchdiffeq` (`torch_dopri5`, `torch_dopri8`, `torch_rk4`) with automatic CUDA → MPS → CPU fallback.
- **Power-flow backends**: `pandapower` or built-in Newton.
- **Fault library**: bus three-phase fault, line trip / reclose, load step, composite cascading events.
- **Parallel batch execution** via `joblib` (loky / multiprocessing / threading).
- **Publication-quality plotting** in Nature style — rotor angles, phase portraits, network topology, batch result violins/heatmaps, CCT sweeps.
- **Refactored from MatDyn**, with the legacy fixed-step solvers and MATPOWER-style power flow vendored under `pylectra/_legacy/` for backward compatibility.

---

## Supported test systems

Out-of-the-box dynamic simulation is available for the following IEEE
benchmark systems. Each ships a power-flow loader (`case_pf`) and a dynamic
parameter file (`case_dyn`); see the YAML examples in [`examples/`](examples/).

| System    | Buses | Generators | PF source      | Dynamic data source                                     | Example YAML                             |
| --------- | ----- | ---------- | -------------- | ------------------------------------------------------- | ---------------------------------------- |
| IEEE 9    | 9     | 3          | pandapower     | Anderson-Fouad 2nd ed. (PSAT `d_009`)                   | [single_case9.yaml](examples/single_case9.yaml)     |
| IEEE 14   | 14    | 5          | pandapower     | PSAT `d_014_dyn` (Milano 2010)                          | [single_case14.yaml](examples/single_case14.yaml)   |
| IEEE 30   | 30    | 6          | pandapower     | Synthesised typical machine (Pai / PSAT `d_030`)        | [single_case30.yaml](examples/single_case30.yaml)   |
| IEEE 39   | 39    | 10         | native + pandapower | MatDyn `case39dyn` (translated)                    | [single_case39.yaml](examples/single_case39.yaml)   |
| IEEE 57   | 57    | 7          | pandapower     | Synthesised typical machine (Vittal-Bergen / PSAT `d_057`) | [single_case57.yaml](examples/single_case57.yaml)   |
| IEEE 68   | 68    | 16         | native         | MatDyn `case68dyn` (translated)                         | (no example yet)                         |
| IEEE 118  | 118   | 54         | pandapower     | Synthesised typical machine (PSAT `d_118` ranges)       | [single_case118.yaml](examples/single_case118.yaml) |

Cases marked **synthesised** use representative typical-machine values
(documented in each `caseNdyn.py` header) because the IEEE benchmark
specification provides power-flow data only. Override per machine when
working on production studies.

The pandapower-backed loaders (case 9 / 14 / 30 / 57 / 118) require the
``pandapower`` extra:

```bash
pip install -e ".[pandapower]"   # pandapower>=3.0,<4.0
```

The native MatDyn-translated cases (39 and 68) work without pandapower.

---

## Installation

> Pylectra is **not yet published to PyPI**. For now, install from source.

```bash
# 1. Clone the repository
git clone <this-repo-url> pylectra
cd pylectra

# 2. Create a clean environment (recommended)
conda create -n pylectra-env python=3.11 -y
conda activate pylectra-env

# 3. Editable install — pick the extras you need
pip install -e .                        # core
pip install -e ".[pandapower]"          # default power-flow backend
pip install -e ".[torch]"               # GPU/CPU torchdiffeq solvers
pip install -e ".[viz]"                 # interactive topology + animation export
pip install -e ".[dev]"                 # pytest + ruff
pip install -e ".[docs]"                # mkdocs documentation build
pip install -e ".[all]"                 # everything (~2 GB)
```

`-e .` (editable) means edits to source files take effect on the next
`import pylectra` — no reinstall needed.

Core runtime dependencies (always installed): `numpy`, `scipy`, `pandas`,
`matplotlib`, `networkx`, `PyYAML`, `h5py`, `pyarrow`, `joblib`, `tqdm`.

More detailed install notes (Conda tips, troubleshooting `h5py` /
`pandapower` builds, etc.) are in
[`docs/en/getting-started/03-install-pylectra.md`](docs/en/getting-started/03-install-pylectra.md).

---

## Quick start

### CLI

```bash
# single deterministic run — IEEE-39, 3-cycle bus-16 fault
python -m pylectra run examples/single_case39.yaml

# generate a batch of perturbed samples → HDF5 + Parquet metadata
python -m pylectra run examples/batch_case39.yaml

# compute critical clearing time on bus 16
python -m pylectra run examples/cct_case39.yaml

# list all registered plugins
python -m pylectra info
```

### Python API

```python
from pylectra.run import run

# single run from a YAML file
out = run("examples/single_case39.yaml")
print(out.result.Time.shape, out.result.max_angle_deviation_deg)

# override fields at call time (deep-merged into the YAML)
out = run("examples/single_case39.yaml", solver={"kind": "scipy_lsoda"})

# parameter sweep
configs = [
    {"mode": "single",
     "fault": {"kind": "bus_fault",
               "params": {"bus": b, "t_fault": 0.2, "duration": 0.05}}}
    for b in [5, 10, 16, 22]
]
results = run(configs)   # list of SimulationOutput
```

---

## YAML configuration

All three run modes share the same top-level schema:

```yaml
mode: single                # single | batch | cct

case_pf:  case39            # power-flow case name (pandapower loadcase)
case_dyn: case39dyn         # dynamic parameters file

power_flow:
  kind: pandapower          # pandapower | newton
  options:
    algorithm: nr
    tolerance_mva: 1.0e-8
    f_hz: 60

solver:
  kind: scipy_dop853        # see Solvers table below
  options:
    rtol: 1.0e-6
    atol: 1.0e-8

fault:
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05
```

### Batch mode

```yaml
mode: batch

scenarios:
  count: 100
  seed: 42
  generators:
    - { kind: load_perturb, params: { sigma_pct: 5.0, clip_pct: 15.0 } }
    - { kind: line_outage,  params: { n_outages: 1, prob: 0.3 } }

filters:
  - { kind: pf_converged }
  - { kind: voltage_range, params: { vmin: 0.7, vmax: 1.3 } }
  - { kind: angle_stability, params: { max_dev_deg: 180.0 } }
  - { kind: simulation_completed }

output:
  directory: ./out_batch
  format: hdf5              # hdf5 | npz
  metadata: parquet         # parquet | csv
  parallel:
    n_jobs: -1
    backend: loky           # loky | multiprocessing | threading
```

### CCT mode

```yaml
mode: cct

cct:
  bus: 16
  t_fault: 0.2
  low: 0.01
  high: 0.30
  tol: 0.005
  max_iter: 20
  stability_filter: { kind: angle_stability, params: { max_dev_deg: 180.0 } }
```

Full schema reference (defaults, ranges, every field):
[`docs/en/reference/yaml-schema.md`](docs/en/reference/yaml-schema.md).

---

## Solvers

| Name | Method | Adaptive | Notes |
|---|---|---|---|
| `scipy_rk45` | Dormand–Prince 4(5) | yes | good general-purpose default |
| `scipy_rk23` | Bogacki–Shampine 2(3) | yes | lower accuracy, faster |
| `scipy_dop853` | Dormand–Prince 8(7) | yes | high precision (recommended for serious numerics) |
| `scipy_lsoda` | LSODA (auto stiff) | yes | best default for batch generation |
| `scipy_bdf` | BDF | yes | stiff systems |
| `scipy_radau` | Radau IIA 5th order | yes | stiff, high accuracy |
| `torch_dopri5` | Dormand–Prince 5(4) | yes | GPU; requires `torch` |
| `torch_dopri8` | Dormand–Prince 8(7) | yes | GPU; requires `torch` |
| `torch_rk4` | Classical RK4 | no | fixed step; requires `torch` |
| `modified_euler` | legacy fixed-step | no | bit-comparable to original MatDyn |

All SciPy solvers accept `rtol`, `atol`, `max_step`, `first_step` under `options`.
Torch solvers additionally accept `device` (`auto` / `cuda` / `cpu` / `mps`),
`torch_dtype`, `chunk_seconds` (OOM relief for long horizons), and `dense_n`.

---

## GPU acceleration (optional)

```bash
pip install "pylectra[torch]"
```

```yaml
solver:
  kind: torch_dopri5
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
    chunk_seconds: 0.5      # OOM-relief: split each leg into 0.5 s windows
    torch_dtype: float64    # cuda default; mps must use float32
    device: auto            # auto → cuda → mps → cpu
```

`torch_device("auto")` probes CUDA → MPS → CPU and falls back transparently.
**No GPU is required at install time** — CUDA acceleration kicks in
automatically the first time you run on a CUDA-capable machine.

For long-horizon OOM relief see
[`docs/en/how-to/tune-memory.md`](docs/en/how-to/tune-memory.md).

---

## Plotting

```bash
# rotor angles from a single run
python -m pylectra plot examples/single_case39.yaml --type rotor_angles --output rotor.pdf

# 2×2 overview panel (angles, speeds, voltages, torques)
python -m pylectra plot examples/single_case39.yaml --type overview --output overview.pdf --format pdf,svg,png

# topology coloured by bus voltage magnitude
python -m pylectra plot examples/single_case39.yaml --type topology --output topo.pdf -O color_by='"vm"'

# batch-result violin plot
python -m pylectra plot ./out_batch --type violin --output vio.pdf \
    -O column='"simulation_time"' -O by='"scenario:fault_bus"'
```

`-O KEY=VAL` passes extra keyword arguments; values are JSON-decoded
(use `'"string"'` for strings).

### Built-in plot types

| Type | Input | Description |
|---|---|---|
| `rotor_angles` | single result | rotor angle trajectories |
| `speeds` | single result | per-generator rotor speed |
| `efds` | single result | field voltage trajectories |
| `voltages` | single result | bus voltage magnitude trajectories |
| `torques` | single result | electrical and mechanical torque |
| `overview` | single result | 2×2 panel: angles, speeds, voltages, torques |
| `phase_portrait` | single result | state-space trajectories (e.g. δ vs ω) |
| `power_spectrum` | single result | PSD of selected state variables |
| `topology` | case / YAML | network graph, colourable by voltage / type / loading |
| `histogram` | batch metadata | distribution of a scalar metric |
| `violin` | batch metadata | violin/box plot grouped by category |
| `heatmap` | batch metadata | 2-D metric matrix |
| `acceptance` | batch metadata | accepted vs rejected sample reasons |
| `cct_sweep` | list of CCT results | critical clearing time vs fault bus |

### Programmatic plotting

```python
from pylectra.plotting import set_nature_style, plot_rotor_angles, save_figure

set_nature_style(font_size=14)
fig = plot_rotor_angles("samples/sample_0042.h5", relative=True, title="Bus-16 fault")
save_figure(fig, "fig3a.pdf", formats=["pdf", "svg"], close=True)
```

Output style: Arial sans-serif, no top/right spines, vector PDF/SVG by default,
600 DPI raster when PNG/TIFF is requested.

---

## Extending Pylectra

Every plugin category has an abstract base class in `pylectra/interfaces/`.
Subclass it, call `@register`, and the new plugin is immediately available
by name in YAML.

### New generator model

```python
from pylectra.registry import register
from pylectra.interfaces.generator import GeneratorModel

@register("generator", "my_subtransient")
class MySubtransientGenerator(GeneratorModel):
    n_states = 6

    def derivatives(self, x, currents, params, t):
        ...

    def initialize(self, V, S, params):
        ...
```

### New sample filter

```python
from pylectra.registry import register
from pylectra.interfaces.filter import SampleFilter, FilterDecision

@register("filter", "frequency_nadir")
class FrequencyNadirFilter(SampleFilter):
    def __init__(self, fmin: float = 59.0):
        self.fmin = fmin

    def judge(self, result, scenario, case):
        f_hz = 60.0 * (1.0 + result.Speeds.min())
        if f_hz < self.fmin:
            return FilterDecision(False, f"nadir {f_hz:.2f} < {self.fmin}", metric=f_hz)
        return FilterDecision(True, metric=f_hz)
```

```yaml
filters:
  - { kind: frequency_nadir, params: { fmin: 59.3 } }
```

Step-by-step recipes for every plugin category live under [`docs/en/how-to/`](docs/en/how-to/):

- [Add a new generator](docs/en/how-to/add-new-generator.md)
- [Add a new fault](docs/en/how-to/add-new-fault.md)
- [Add a new scenario generator](docs/en/how-to/add-new-scenario.md)
- [Add a new sample filter](docs/en/how-to/add-new-filter.md)
- [Add a new plot](docs/en/how-to/add-new-plot.md)

---

## Documentation

📖 **Online site**: **<https://zongjialong.github.io/Pylectra/>** — searchable, light/dark themed, with English ↔ 中文 switcher. Auto-rebuilt on every push to `main`.

The source lives in the [`docs/`](docs/) folder, with parallel English and 中文 trees (`docs/en/` and `docs/zh/`):

| Section | Path | What it is |
|---|---|---|
| Getting started | [`docs/en/getting-started/`](docs/en/getting-started/) | Install Python, Git, Pylectra; run your first simulation; understand the output |
| Concepts | [`docs/en/concepts/`](docs/en/concepts/) | Background: Python packages, virtual envs, YAML, plugins, Python-vs-MATLAB, architecture |
| Tutorials | [`docs/en/tutorials/`](docs/en/tutorials/) | Single run, batch generation, CCT, visualization, small-signal analysis, GPU acceleration |
| How-to guides | [`docs/en/how-to/`](docs/en/how-to/) | Recipes for adding plugins, MATPOWER cases, parameter sweeps, parallelism, memory tuning, Jupyter |
| Reference | [`docs/en/reference/`](docs/en/reference/) | YAML schema, plugin catalog, CLI, Python API, glossary |
| FAQ | [`docs/en/faq.md`](docs/en/faq.md) | Common issues and answers |

You can read the markdown files directly on GitHub or in any editor. For a nicely rendered, searchable site (with light/dark theme and language switcher), build the docs locally:

```bash
pip install -e ".[docs]"
python -m mkdocs serve        # http://127.0.0.1:8000
```

Or build a static site for offline browsing:

```bash
python -m mkdocs build        # output goes to ./site
```

---

## Running the tests

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

`pytest -m "not slow"` skips the long-running batch / CCT / CLI integration
tests (~30–90 s each).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The typical PR is **one file plus one
test**: subclass an interface, register the plugin, and add a unit test.

---

## License & attribution

Released under the **MIT License**.

- Dynamic model structure based on **MatDyn** © 2009 Stijn Cole, KU Leuven (ESAT/ELECTA).
- Power-flow case data derived from **MATPOWER** © Ray Zimmerman, PSERC Cornell.
