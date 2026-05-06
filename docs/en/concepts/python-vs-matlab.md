# Python for MATLAB users

_Beginner_

> Cheat-sheet style. Lists the MATLAB → Python differences power-systems engineers trip over most often.

## Mindset shift

Python isn't a MATLAB clone — it's a **general-purpose programming language**, with scientific computing as one of its uses. So:

- **No "workspace"**: variables live inside functions (unless you declare `global`); they don't persist after a function returns.
- **No built-in plot windows**: you must `import matplotlib.pyplot as plt`.
- **Arrays aren't a language primitive**: `import numpy as np`; matrix operations are on `np.array`.

In return:

- **First-class package management**: `pip install pandapower` Just Works.
- **Huge ecosystem**: from machine learning to web servers.
- **Free**: no licence to buy.

## Indices start at 0 (the biggest gotcha)

| MATLAB | Python (numpy) |
|---|---|
| `x(1)` first | `x[0]` first |
| `x(end)` last | `x[-1]` last |
| `x(1:5)` first 5 | `x[0:5]` or `x[:5]` first 5 (**5 excluded**) |
| `x(end-2:end)` last 3 | `x[-3:]` last 3 |

**Python slices `[a:b]` are half-open**: `x[2:5]` returns positions 2, 3, 4 (three elements). One reason: the length is exactly `5 - 2 = 3`, which makes loop arithmetic cleaner.

## Matrix operations

```matlab
% MATLAB
A = [1 2 3; 4 5 6];
b = A(:, 2);          % second column
c = A * A';           % matrix product
d = A .* A;           % element-wise product
```

```python
# Python with numpy
import numpy as np
A = np.array([[1, 2, 3], [4, 5, 6]])
b = A[:, 1]           # second column (0-based)
c = A @ A.T           # matrix product (Python 3.5+ syntax)
d = A * A             # element-wise — `*` defaults to element-wise
```

**`*` is element-wise; `@` is matrix product** — opposite of MATLAB.

## Complex numbers

```matlab
z = 3 + 4i;
abs(z)        % 5
angle(z)      % 0.9273 (radians)
```

```python
z = 3 + 4j                    # Python uses j (i is typically a loop variable)
abs(z)                        # 5.0
import numpy as np
np.angle(z)                   # 0.9272952180016122
```

## Complex matrices / power-flow style

```python
import numpy as np
V = np.array([1.05 + 0.0j, 1.02 - 0.05j, 1.00 + 0.02j])
I = Y @ V                     # Y is a numpy complex matrix
S = V * np.conj(I)            # complex power
```

## Control flow

```python
# if / elif / else
if voltage > 1.10:
    print("over-voltage")
elif voltage > 1.05:
    print("warning")
else:
    print("ok")

# for (range is half-open)
for i in range(10):           # i = 0, 1, ..., 9
    print(i)

# while
t = 0.0
while t < 10.0:
    t += 0.01
```

A code block is **a colon followed by indentation**; there is **no `end`**. Indentation must be consistent — 4 spaces or 1 tab, pick one and stick to it within the same file.

## Functions

```matlab
function [y, dy] = my_func(x, a)
    y = a * sin(x);
    dy = a * cos(x);
end
```

```python
def my_func(x, a):
    y = a * np.sin(x)
    dy = a * np.cos(x)
    return y, dy

y, dy = my_func(0.5, 2.0)     # tuple-unpack the return value
```

In Python:

- Functions are defined with `def`.
- Return values are explicit (`return`); multiple values are a tuple.
- **No "filename == function name"** rule — one `.py` can hold any number of functions.

## Calling pylectra: MATLAB vs Python style

### MATLAB-style script (hypothetical)

```matlab
mpc = case39;
mpopt = mpoption('alg', 'NR');
results = runpf(mpc, mpopt);

events = [0.20 1; 0.25 1];
sol = rundyn(mpc, 'case39dyn', 'fault', mpopt);
plot(sol.Time, sol.Angles);
```

### Actual pylectra Python

```python
from pylectra.run import run

# All settings live in YAML — configuration is data, not code
out = run("examples/single_case39.yaml")
print(out.result.Time.shape, out.result.Angles.shape)

# A dict works too
out = run({"mode": "single", "case_pf": "case39",
           "fault": {"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": 0.05}}})

# Plotting
from pylectra.plotting import render
render("rotor_angles", out.result, save="angles.pdf")
```

## Common MATLAB → Python translation table

| MATLAB | Python (numpy etc.) |
|---|---|
| `length(x)` | `len(x)` |
| `size(A)` | `A.shape` (a tuple) |
| `zeros(3,4)` | `np.zeros((3, 4))` |
| `ones(3,4)` | `np.ones((3, 4))` |
| `linspace(0,1,11)` | `np.linspace(0, 1, 11)` |
| `eig(A)` | `np.linalg.eig(A)` |
| `inv(A)` | `np.linalg.inv(A)` (but prefer `np.linalg.solve`) |
| `A \ b` | `np.linalg.solve(A, b)` |
| `disp('hi')` | `print('hi')` |
| `figure; plot(t, x)` | `plt.figure(); plt.plot(t, x); plt.show()` |
| `save('out.mat', ...)` | `np.savez('out.npz', ...)` or HDF5 |
| `tic; ...; toc;` | `import time; t0=time.time(); ...; print(time.time()-t0)` |

## Pythonic conventions

- **Indentation is syntax**: 4 spaces start a block; one off → SyntaxError.
- **Naming**: `snake_case` for functions/variables (`my_func`), `CamelCase` for classes (`MyClass`).
- **Lists and dicts everywhere**: `my_list = [1, 2, 3]`, `my_dict = {"a": 1, "b": 2}`.
- **Formatted output**: `print(f"angle = {delta:.3f} deg")` — f-strings.

## Next steps

- [Your first simulation](../getting-started/04-first-simulation.md) — port MATLAB muscle-memory onto pylectra.
- [What is a Python package](what-is-python-package.md) — packages are toolboxes.
- [5-minute YAML guide](what-is-yaml.md) — pylectra's "config script".
