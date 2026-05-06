# `pylectra.run` 模块

_参考资料_

`pylectra.run` 是顶层编程式入口。用 Python 而非 CLI 调用 pylectra 时从这里开始。

## `run(config, **overrides)`

```python
def run(config: str | Path | dict | NetworkCase, **overrides) -> RunOutput
```

**参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `config` | `str` / `Path` / `dict` | YAML 路径、已解析的 dict |
| `**overrides` | 任意 | 深合并进 config 的关键字（如 `solver={"kind": "scipy_dop853"}`） |

**返回**

| 字段 | 类型 | 仅在...返回 |
|---|---|---|
| `out.result` | `SimulationResult` / `BatchResult` / `CCTResult` | 全部模式 |
| `out.case` | `NetworkCase` | single / cct |
| `out.scenario` | `Scenario` 或 None | single（如果有扰动） |

**示例**

```python
from pylectra.run import run

# YAML 路径
out = run("examples/single_case39.yaml")

# dict
out = run({"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
           "fault": {"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05}}})

# 覆盖一个字段
out = run("examples/single_case39.yaml",
          solver={"kind": "scipy_dop853", "options": {"rtol": 1e-8}})
```

## `run_many(configs, **shared_overrides)`

```python
def run_many(configs: Iterable[ConfigLike], **shared_overrides) -> list
```

串行依次跑每个 config，返回 `RunOutput` 列表。

```python
configs = [
    {"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
     "fault": {"kind": "bus_fault",
               "params": {"bus": b, "t_fault": 0.2, "duration": 0.05}}}
    for b in [4, 16, 23]
]
results = run_many(configs)
for cfg, out in zip(configs, results):
    print(cfg["fault"]["params"]["bus"], out.result.max_angle_deviation_deg)
```

> **并行**版需要自己用 joblib 包一层。`run_many` 故意保持串行，以保证对象不可序列化时也能用。

## SimulationResult 字段（single 模式）

```python
out = run("examples/single_case39.yaml", plot=False)
res = out.result

# 数值时序
res.Time          # (N,)         [s]
res.Voltages      # (N, n_bus)   complex
res.Angles        # (N, n_gen)   [度]
res.Speeds        # (N, n_gen)   [p.u.]
res.Eq_trs        # (N, n_gen)
res.Ed_trs        # (N, n_gen)
res.Efds          # (N, n_gen)
res.Tes           # (N, n_gen)   电磁转矩
res.TM            # (N, n_gen)   机械转矩
res.Vss           # (N, n_gen)   PSS 输出
res.Stepsize      # (N,)
res.Errest        # (N,)         （仅自适应求解器）

# 元数据
res.simulation_time              # [s] 墙钟
res.pf_success                   # bool
res.metadata                     # dict
res.small_signal                 # SmallSignalResult 或 None

# 便利属性
res.n_steps
res.n_bus
res.n_gen
res.voltage_magnitude            # |Voltages|
res.max_angle_deviation_deg      # 与 COI 偏差
```

## BatchResult 字段（batch 模式）

```python
out = run("examples/batch_case39.yaml")
br = out.result

br.n_total       # 提交的样本总数
br.n_accepted    # 通过过滤的样本数
br.n_rejected
br.n_pf_failed
br.duration      # 总墙钟 [s]
br.directory     # 输出目录
br.metadata_path # parquet 路径
```

`SimulationResult` 列表不在 BatchResult 里——读 `directory/sample_*.h5`。

## CCTResult 字段（cct 模式）

```python
out = run("examples/cct_case39.yaml")
cct = out.result

cct.cct          # 临界切除时间 [s]
cct.iterations   # 二分迭代轮数
cct.bracket_low  # 收敛后 bracket
cct.bracket_high
cct.converged    # bool
cct.note         # 描述（如果未收敛）
```

## 失败时的输出

潮流不收敛或求解器失败：

- single 模式：`res.pf_success = False`，时序数组形状为 `(0, ...)`
- batch 模式：该样本在 metadata 里 `passed=False, rejected_by="pf_converged"`，但**整批继续跑**
- cct 模式：bracket 检查失败 → `cct.converged = False`，note 字段写明原因

## 接下来读什么

- [pylectra.registry](registry.md) — 注册表 API
- [pylectra.interfaces](interfaces.md) — 各类别 ABC
