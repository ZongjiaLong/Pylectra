# 术语对照表（电力 + Python，中英对照）

_参考资料_

电力工程师与 Python 用户共同的工作语言。

## 电力系统术语

| 中文 | English | 含义 |
|---|---|---|
| 母线 | bus | 电网中节点 |
| 支路 / 线路 | branch / line | 母线之间的传输线 |
| 平衡机 / 参考母线 | slack / swing / reference bus | 潮流计算中吸收功率不平衡的机组 |
| PQ / PV / REF 母线 | PQ / PV / REF bus | 潮流中三种母线类型 |
| 潮流 | power flow | 算稳态电压、电流、功率分布 |
| 转子角 | rotor angle (δ) | 同步机内部电势相对参考的角度 |
| 转子转速 | rotor speed (ω) | 角频率，p.u. 通常 ≈ 1 |
| 同步机 | synchronous machine / generator | 主流发电机类型 |
| 励磁机 / AVR | exciter / Automatic Voltage Regulator | 调发电机端电压 |
| 调速器 | governor | 调机械功率 / 频率 |
| 电力系统稳定器 PSS | Power System Stabilizer | 给励磁加阻尼信号 |
| 暂态 | transient | 故障 / 大扰动后系统短期响应 |
| 暂态稳定 | transient stability | 大扰动后能否保持同步 |
| 临界切除时间 CCT | Critical Clearing Time | 故障最长可持续多久不失稳 |
| 小信号 | small-signal | 平衡点附近的线性化分析 |
| 阻尼比 ζ | damping ratio | 模态衰减快慢，电力工程通常要 ≥ 5% |
| 区域间振荡 | inter-area oscillation | 0.2–1 Hz 大区电网间的低频振荡 |
| Y 矩阵 / 导纳矩阵 | Y-bus / admittance matrix | 网络方程 V = Z·I 的 Z⁻¹ |
| MATPOWER / pandapower | — | 主流潮流分析工具（MATLAB / Python） |
| MatDyn | — | MATPOWER 的暂态扩展（pylectra 是它的 Python 重构） |
| 故障 | fault | 短路、断线、跳机等扰动 |
| 三相短路 | three-phase fault | 最常见的对称性故障 |
| N-1 / N-2 故障 | N-1 / N-2 contingency | 单 / 双线退出运行 |

## Python / 软件术语

| 中文 | English | 含义 |
|---|---|---|
| 包 | package | 一组可以一条命令装好的 Python 代码 |
| 模块 | module | 一个 .py 文件 / 子包 |
| 导入 | import | Python 把模块加载到内存 |
| 装饰器 | decorator | `@xxx` 写在函数 / 类上面，自动改它的行为 |
| 注册表 | registry | pylectra 用 dict 存储 "名字 → 类" 的映射 |
| 插件 | plugin | 通过 `@register` 注册到注册表的类 |
| 抽象基类 | Abstract Base Class (ABC) | 定义"必须实现哪些方法"的契约 |
| 虚拟环境 | virtual environment | 隔离不同项目的依赖 |
| pip / conda | — | 两种 Python 包管理器 |
| 字典 | dict | `{"key": "value"}` 键值对结构 |
| 列表 | list | `[1, 2, 3]` 有序集合 |
| 元组 | tuple | `(1, 2, 3)` 不可变有序集合 |
| 数组 | array (numpy) | 多维数值容器，电力工程的主力 |
| 复数 | complex number | numpy / Python 用 `j` 表示虚部（不是 i） |
| 切片 | slice | `x[1:5]`，取子集，**左闭右开** |
| 绝对路径 / 相对路径 | absolute / relative path | 文件位置表示方式 |
| YAML | — | 人类可读配置格式（pylectra 用它） |
| HDF5 | — | 高效二进制科学数据格式 |
| Parquet | — | 列式数据格式，pandas 友好 |
| 命令行 / 终端 | command line / terminal / shell | cmd / Bash / PowerShell 等 |
| 环境变量 | environment variable | 操作系统层面的全局配置 |

## pylectra 专有术语

| 名字 | 含义 |
|---|---|
| `mode` | YAML 顶层字段：`single` / `batch` / `cct` |
| `case_pf` / `case_dyn` | 潮流算例 / 动力学参数文件 |
| `kind` | 插件名（YAML 里所有插件类别下都用） |
| `Scenario` | batch 模式下一次扰动后的算例 + 元数据 |
| `SimulationResult` | 单次仿真完整时序对象 |
| `BatchResult` | 批量仿真的统计 + 输出目录 |
| `CCTResult` | CCT 二分搜索的最终值 + 收敛信息 |
| `FilterDecision` | `(passed, reason, metric)` 三元组 |
| `chunk_seconds` | torch ODE 内存优化选项（窗口大小） |
| `dense_n` | 每 leg 输出点数（torch 后端） |
| `tail_fraction` | voltage_range 过滤器只看后多少比例的时段 |
| `legacy` | pylectra/_legacy/ 下的 vendored MATLAB 直译代码 |

## 缩写

| 缩写 | 全称 |
|---|---|
| ABC | Abstract Base Class |
| API | Application Programming Interface |
| AVR | Automatic Voltage Regulator |
| BLAS | Basic Linear Algebra Subprograms |
| CCT | Critical Clearing Time |
| CLI | Command-Line Interface |
| COI | Center Of Inertia |
| GPU | Graphics Processing Unit |
| HDF5 | Hierarchical Data Format v5 |
| IDE | Integrated Development Environment |
| ODE | Ordinary Differential Equation |
| PF | Power Flow |
| PSS | Power System Stabilizer |
| RHS | Right-Hand Side（ODE 方程的右端） |
| RK | Runge-Kutta |
| YAML | YAML Ain't Markup Language |

## 接下来读什么

- [概念背景](../concepts/what-is-python-package.md) — 详细解释 Python 概念
- [给 MATLAB 用户的 Python 入门](../concepts/python-vs-matlab.md) — MATLAB ↔ Python 函数对照
