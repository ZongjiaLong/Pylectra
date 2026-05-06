# Use pylectra inside Jupyter

_Intermediate_

**Prerequisites:** [Single deterministic simulation](../tutorials/01-single-run.md), [Visualization tutorial](../tutorials/04-visualization.md)

Jupyter Notebook (or JupyterLab) is ideal for **interactive exploration** with pylectra — tweak a parameter, rerun, see the figure immediately.

## Install + launch

In the same env:

```bash
conda activate pylectra-env
conda install -c conda-forge jupyterlab        # or pip install jupyterlab
```

Run:

```bash
jupyter lab
```

Browser auto-opens to `http://localhost:8888`. Create a new notebook (top-right `+`) → `Python 3 (ipykernel)`.

## First cell — import + run

```python
%matplotlib inline                  # show matplotlib figures inline

from pylectra.run import run
from pylectra.plotting import render

out = run("examples/single_case39.yaml", plot=False)
render("rotor_angles", out.result, gen_indices=[0, 1, 2, 3])
```

`Shift+Enter` runs the cell — the figure appears below it.

## Recipe 1 — parameter exploration loop

```python
# Cell 1 - one-time imports
from pylectra.run import run
from pylectra.plotting import render
import matplotlib.pyplot as plt

# Cell 2 - tweak this and Shift+Enter
fault_duration = 0.10              # change me
out = run("examples/single_case39.yaml",
          fault={"kind": "bus_fault",
                 "params": {"bus": 16, "t_fault": 0.2,
                            "duration": fault_duration}},
          plot=False, verbose=0)
print(f"max angle dev = {out.result.max_angle_deviation_deg:.2f}°")
render("rotor_angles", out.result)
plt.show()
```

Edit the first line of Cell 2 and rerun — far faster turnaround than the CLI.

## Recipe 2 — sweep + inline table

```python
import pandas as pd
from pylectra.run import run

records = []
for d in [0.02, 0.05, 0.08, 0.12, 0.16]:
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": 16, "t_fault": 0.2, "duration": d}},
              plot=False, verbose=0)
    records.append({"duration": d,
                    "max_dev": out.result.max_angle_deviation_deg,
                    "pf_ok":   out.result.pf_success})

pd.DataFrame(records).style.format({"max_dev": "{:.1f}°"})
```

Jupyter renders `pd.DataFrame.style` as a clean HTML table.

## Recipe 3 — interactive sliders

Install `ipywidgets`:

```bash
conda install -c conda-forge ipywidgets
```

```python
import ipywidgets as widgets
from IPython.display import display
from pylectra.run import run
from pylectra.plotting import render
import matplotlib.pyplot as plt

def show_run(bus=16, duration=0.05):
    out = run("examples/single_case39.yaml",
              fault={"kind": "bus_fault",
                     "params": {"bus": bus, "t_fault": 0.2, "duration": duration}},
              plot=False, verbose=0)
    fig = render("rotor_angles", out.result, gen_indices="all")
    plt.show()
    print(f"max dev = {out.result.max_angle_deviation_deg:.2f}°")

widgets.interact(show_run,
                 bus=widgets.IntSlider(min=1, max=39, step=1, value=16),
                 duration=widgets.FloatSlider(min=0.01, max=0.3, step=0.01,
                                              value=0.05))
```

Drag the sliders, see the simulation update — the most intuitive "which faulted bus is dangerous?" tool.

## Recipe 4 — cache simulation across runs

`pickle` for persistence:

```python
import pickle, os

cache = "out_cached.pkl"
if os.path.exists(cache):
    with open(cache, "rb") as f:
        out = pickle.load(f)
    print("loaded cached")
else:
    out = run("examples/batch_case39.yaml")     # long sim
    with open(cache, "wb") as f:
        pickle.dump(out, f)
    print("ran fresh")
```

`SimulationResult` is picklable (unless you've attached non-serialisable extras).

## Recipe 5 — `%timeit` performance comparison

```python
%timeit run("examples/single_case39.yaml", \
            solver={"kind": "modified_euler"}, plot=False, verbose=0)
# 1 loop, best of 5: 9.4 s per loop

%timeit run("examples/single_case39.yaml", \
            solver={"kind": "scipy_dop853"}, plot=False, verbose=0)
# 1 loop, best of 5: 5.1 s per loop
```

## Handling large outputs

`BatchResult` objects are heavy — `print`-ing them freezes the browser. **Only print key scalars**:

```python
out = run("examples/batch_case39.yaml")
print(f"accepted: {out.result.n_accepted}/{out.result.n_total}")
# Don't print(out) directly!
```

Inspect per-sample details via metadata.parquet:

```python
import pandas as pd
meta = pd.read_parquet("./out_batch/metadata.parquet")
meta.head()
```

## Jupyter on a remote server

SSH tunnel for browser access:

```bash
# Local terminal
ssh -L 8888:localhost:8888 user@server

# On the server
jupyter lab --no-browser --port 8888

# Local browser → http://localhost:8888
```

## FAQ

### Q: Figures don't display

Make sure the first cell ran `%matplotlib inline`. For zoom/pan, use `%matplotlib widget`:

```bash
conda install -c conda-forge ipympl
```

```python
%matplotlib widget
```

### Q: `No module named 'pylectra'`

Jupyter is using the wrong Python. Verify:

```python
import sys
print(sys.executable)
# Should be .../envs/pylectra-env/python.exe
```

If not, register your conda env as a Jupyter kernel:

```bash
conda activate pylectra-env
pip install ipykernel
python -m ipykernel install --user --name pylectra-env --display-name "Python (pylectra-env)"
```

Restart Jupyter and pick `Python (pylectra-env)` for new notebooks.

### Q: matplotlib CJK font glyphs garbled

```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
```

Run this in the first cell of the notebook.

## Next steps

- [Visualization tutorial](../tutorials/04-visualization.md) — save Jupyter figures as publication PDFs.
- [Parameter sweep](parameter-sweep.md) — automate the experiments you've been doing manually.
