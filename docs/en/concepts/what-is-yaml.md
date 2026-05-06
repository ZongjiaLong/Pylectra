# 5-minute YAML guide

_Beginner_

YAML ("YAML Ain't Markup Language") is pylectra's **configuration file format** — you write a `.yaml` file describing what simulation to run and pylectra executes it.

Analogy: in MATLAB you might write a `.m` script setting parameters like `tf=0.2; fb=16;` then call functions. In pylectra those parameters live in YAML instead — better for version control and reproducibility.

## A minimal example

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

Reading rules:

- Each line is a **key: value** pair; the colon must be followed by a space.
- **Indentation** marks hierarchy (convention: **2 spaces**; never tabs).
- Numbers, strings, and booleans (`true`/`false`/`null`) are auto-detected.

The above YAML is equivalent to this Python dict:

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

## Three data types

### 1. Scalars (numbers, strings, booleans)

```yaml
count: 100              # int
sigma_pct: 5.0          # float
seed: 42
name: case39            # string (quotes optional)
filename: "my file.txt" # quotes required when value contains spaces
verbose: true           # boolean
plot: false
empty: null             # None / null
```

> ⚠️ **Scientific-notation pitfall**: in YAML 1.1, `1e-6` is parsed as a *string*, not a number. **Write `1.0e-6`** (with a decimal point) to get a float.

### 2. Mappings (nested levels, by indentation)

```yaml
solver:
  kind: scipy_lsoda
  options:
    rtol: 1.0e-6
    atol: 1.0e-8
```

`solver` is a mapping with `kind` and `options`; `options` is itself a mapping.

### 3. Lists (use `-` for each item)

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

`filters` is a 3-element list; each element is itself a mapping.

You can also use the inline form (compact but less readable; only good for short lists):

```yaml
filters: [pf_converged, voltage_range, angle_stability]
```

## Comments

```yaml
# A whole-line comment
solver:
  kind: scipy_lsoda    # End-of-line is fine too
```

## Common pitfalls

### Pitfall 1 — using tabs

```
ScannerError: while scanning for the next token
found character '\t' that cannot start any token
```

**Use spaces only.** VS Code (and most editors) can show whitespace and convert tabs to spaces automatically.

### Pitfall 2 — inconsistent indentation

```yaml
solver:
  kind: scipy_lsoda
   options:           # one extra space → parse error
```

Siblings must share the exact same indentation depth.

### Pitfall 3 — missing space after colon

```yaml
solver:kind:scipy_lsoda      # WRONG — colon must be followed by a space
```

### Pitfall 4 — booleans masquerading as strings

```yaml
plot: false                  # boolean
plot: "false"                # string (note quotes)
```

YAML treats `yes`, `no`, `on`, `off`, `true`, `false` (case-insensitive) as booleans. Quote them if you really want the literal string.

### Pitfall 5 — version numbers turning into floats

```yaml
version: 1.0     # float 1.0
version: "1.0"   # string "1.0"
version: 1.0.0   # string (more than one dot defeats the number rule)
```

## Read it from Python yourself

```python
import yaml
with open("examples/single_case39.yaml") as f:
    cfg = yaml.safe_load(f)
print(cfg["fault"]["params"]["bus"])             # 16
print(type(cfg["fault"]["params"]["t_fault"]))   # <class 'float'>
```

If your YAML is malformed, `yaml.safe_load` raises `yaml.YAMLError` with a line number.

## Next steps

- [Your first simulation](../getting-started/04-first-simulation.md) — apply this syntax to an actual case39 run.
