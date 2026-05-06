# 5 分钟读懂 YAML

_初学者_

YAML（"亚目"或"亚墨"，YAML Ain't Markup Language）是 pylectra 的**配置文件格式**——你写一个 `.yaml` 文件描述"想跑什么仿真"，pylectra 读完就执行。

类比：MATLAB 里你可能写一个 `.m` 脚本设置参数 `tf=0.2; fb=16;`，再调函数。在 pylectra 里，这些参数全部写在 YAML 里，更适合**版本管理**和**别人复现**。

## 一个最小 YAML 例子

```yaml
mode: single
case_pf: case39

solver:
  kind: scipy_lsoda
  options:
    rtol: 1.0e-6

fault:
  kind: bus_fault
  params:
    bus: 16
    t_fault: 0.2
    duration: 0.05
```

读法：

- 每行是一个**键值对**（key: value），冒号后**必须有空格**
- **缩进**表示层级（约定 **2 个空格**，**不能用 Tab**）
- 数字、字符串、布尔（`true`/`false`/`null`）都自动识别

上面的 YAML 等价于这个 Python 字典：

```python
{
    "mode": "single",
    "case_pf": "case39",
    "solver": {
        "kind": "scipy_lsoda",
        "options": {"rtol": 1e-6},
    },
    "fault": {
        "kind": "bus_fault",
        "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05},
    },
}
```

## 三种数据类型

### 1. 标量（数字、字符串、布尔）

```yaml
count: 100              # 整数
sigma_pct: 5.0          # 浮点数
seed: 42
name: case39            # 字符串（引号可省）
filename: "my file.txt" # 含空格时必须加引号
verbose: true           # 布尔
plot: false
empty: null             # 空值
```

> ⚠️ **科学记数法陷阱**：YAML 1.1 里 `1e-6` 会被当成字符串而不是数字。**写 `1.0e-6`**（带小数点）就会被识别为浮点。

### 2. 字典（嵌套层级，用缩进）

```yaml
solver:
  kind: scipy_lsoda
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
```

`solver` 是一个字典，里面有 `kind` 和 `options`，`options` 又是一个字典。

### 3. 列表（用 `-` 表示项）

```yaml
filters:
  - kind: pf_converged
  - kind: voltage_range
    params:
      vmin: 0.85
      vmax: 1.15
  - kind: angle_stability
    params:
      max_dev_deg: 180.0
```

`filters` 是一个 3 元素列表，每个元素本身是字典。

也可以写成"行内"形式（紧凑但可读性差，仅适合短列表）：

```yaml
filters: [pf_converged, voltage_range, angle_stability]
```

## 注释

```yaml
# 这是一行注释
solver:
  kind: scipy_lsoda    # 行尾也可以
```

## 常见坑

### 坑 1：用了 Tab

```
ScannerError: while scanning for the next token
found character '\t' that cannot start any token
```

**全部用空格**。VS Code 等编辑器都能设置"显示空格 / Tab"+"自动转换 Tab 为 4 空格"。

### 坑 2：缩进不一致

```yaml
solver:
  kind: scipy_lsoda
   options:           # 多了一个空格 → 解析报错
```

**同级元素必须用同样数量的空格**。

### 坑 3：忘了空格

```yaml
solver:kind:scipy_lsoda      # 错！冒号后必须空格
```

### 坑 4：把布尔当字符串

```yaml
plot: false                  # 布尔
plot: "false"                # 字符串（注意引号）
```

YAML 默认会把 `yes`、`no`、`on`、`off`、`true`、`false`（不区分大小写）识别为布尔。如果你确实要存字符串 `"yes"`，加引号。

### 坑 5：版本号被当成数字

```yaml
version: 1.0     # 浮点 1.0
version: "1.0"   # 字符串 "1.0"
version: 1.0.0   # 字符串（多于一个点不会被识别为数字）
```

## 用 Python 自己读一遍

```python
import yaml
with open("examples/single_case39.yaml") as f:
    cfg = yaml.safe_load(f)
print(cfg["fault"]["params"]["bus"])     # 16
print(type(cfg["fault"]["params"]["t_fault"]))  # <class 'float'>
```

如果你的 YAML 写错了，`yaml.safe_load` 会抛 `yaml.YAMLError` 并指出行号。

## 接下来读什么

- [你的第一次仿真](../getting-started/04-first-simulation.md) — 把刚才学到的语法用起来，跑一个真实的 case39 仿真
