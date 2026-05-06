# Glossary (power-system + Python terms, EN/CN)

_Reference_

The shared vocabulary for power-systems engineers and Python developers using pylectra.

## Power-system terms

| English | 中文 | Meaning |
|---|---|---|
| bus | 母线 | A node in the grid |
| branch / line | 支路 / 线路 | Transmission line between buses |
| slack / swing / reference bus | 平衡机 / 参考母线 | The bus that absorbs the power-flow imbalance |
| PQ / PV / REF bus | PQ / PV / REF 母线 | Three bus types in power-flow |
| power flow | 潮流 | Steady-state voltage / current / power distribution |
| rotor angle (δ) | 转子角 | Internal-emf angle of a synchronous machine vs. reference |
| rotor speed (ω) | 转子转速 | Angular frequency, ~1 p.u. nominally |
| synchronous machine / generator | 同步机 | Dominant generator type |
| exciter / Automatic Voltage Regulator (AVR) | 励磁机 / AVR | Regulates terminal voltage |
| governor | 调速器 | Regulates mechanical power / frequency |
| Power System Stabilizer (PSS) | 电力系统稳定器 | Adds damping signal to the AVR |
| transient | 暂态 | Short-term system response after a disturbance |
| transient stability | 暂态稳定 | Whether synchronism is preserved after a large disturbance |
| Critical Clearing Time (CCT) | 临界切除时间 | Maximum fault duration the system can survive |
| small-signal | 小信号 | Linearised analysis around an equilibrium |
| damping ratio (ζ) | 阻尼比 | How fast a mode decays; engineering target ≥ 5 % |
| inter-area oscillation | 区域间振荡 | 0.2–1 Hz oscillations between large grid regions |
| Y-bus / admittance matrix | 导纳矩阵 | Network-equation matrix Y; V·Y = I |
| MATPOWER / pandapower | — | Mainstream power-flow tools (MATLAB / Python) |
| MatDyn | — | MATPOWER's transient extension; pylectra is a Python rewrite |
| fault | 故障 | Short-circuit, line trip, generator outage, etc. |
| three-phase fault | 三相短路 | Most common symmetric fault |
| N-1 / N-2 contingency | N-1 / N-2 故障 | Single / double element outage |

## Python / software terms

| English | 中文 | Meaning |
|---|---|---|
| package | 包 | Code installable with one command |
| module | 模块 | A `.py` file / sub-package |
| import | 导入 | Load a module into memory |
| decorator | 装饰器 | `@xxx` syntax that augments a function or class |
| registry | 注册表 | pylectra's name → class mapping |
| plugin | 插件 | A class registered via `@register` |
| Abstract Base Class (ABC) | 抽象基类 | Contract listing required methods |
| virtual environment | 虚拟环境 | Per-project dependency isolation |
| pip / conda | — | Two Python package managers |
| dict | 字典 | `{"key": "value"}` mapping |
| list | 列表 | `[1, 2, 3]` ordered collection |
| tuple | 元组 | `(1, 2, 3)` immutable ordered collection |
| array (numpy) | 数组 | Multi-dimensional numeric container |
| complex number | 复数 | Python / numpy use `j` for the imaginary part (not `i`) |
| slice | 切片 | `x[1:5]` — half-open subset access |
| absolute / relative path | 绝对 / 相对路径 | File location notation |
| YAML | — | Human-readable config format (pylectra uses it) |
| HDF5 | — | Efficient binary scientific data format |
| Parquet | — | Columnar dataframe format; pandas-friendly |
| command line / terminal / shell | 命令行 / 终端 | cmd / Bash / PowerShell, etc. |
| environment variable | 环境变量 | OS-level global setting |

## pylectra-specific terms

| Name | Meaning |
|---|---|
| `mode` | Top-level YAML field: `single` / `batch` / `cct` |
| `case_pf` / `case_dyn` | Power-flow case / dynamics-parameter file |
| `kind` | Plugin name (used everywhere a plugin is referenced) |
| `Scenario` | Perturbed case + metadata for a single batch sample |
| `SimulationResult` | Full time-series object from one simulation |
| `BatchResult` | Aggregate statistics + output directory for a batch |
| `CCTResult` | Bisection result + convergence info |
| `FilterDecision` | `(passed, reason, metric)` triple |
| `chunk_seconds` | torch ODE memory option (window size) |
| `dense_n` | Output points per leg (torch backend) |
| `tail_fraction` | `voltage_range` filter checks only this trailing fraction |
| `legacy` | Vendored MATLAB-port code under `pylectra/_legacy/` |

## Acronyms

| Acronym | Full form |
|---|---|
| ABC | Abstract Base Class |
| API | Application Programming Interface |
| AVR | Automatic Voltage Regulator |
| BLAS | Basic Linear Algebra Subprograms |
| CCT | Critical Clearing Time |
| CLI | Command-Line Interface |
| COI | Centre Of Inertia |
| GPU | Graphics Processing Unit |
| HDF5 | Hierarchical Data Format v5 |
| IDE | Integrated Development Environment |
| ODE | Ordinary Differential Equation |
| PF | Power Flow |
| PSS | Power System Stabilizer |
| RHS | Right-Hand Side (of an ODE) |
| RK | Runge-Kutta |
| YAML | YAML Ain't Markup Language |

## Next steps

- [Concepts](../concepts/what-is-python-package.md) — deeper explanations of Python concepts.
- [Python for MATLAB users](../concepts/python-vs-matlab.md) — MATLAB ↔ Python translation tables.
