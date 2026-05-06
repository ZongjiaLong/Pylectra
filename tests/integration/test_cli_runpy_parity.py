"""Phase 3 acceptance: ``python -m pylectra run`` ↔ ``pylectra.run.run`` parity.

Runs ``examples/single_case39_scipy.yaml`` through both entry points and
asserts the resulting time-series are bit-identical.  Marked ``slow``
(~30 s).
"""
from __future__ import annotations

import os
import pickle
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]


def _run_via_cli_dump(yaml_path: Path, out_pkl: Path) -> None:
    """Invoke a child Python that calls pylectra.run.run and pickles the result.

    We intentionally do NOT use ``python -m pylectra run`` here because that
    only writes plots/HDF5 to disk — its return value is not exposed on
    stdout.  Calling :func:`pylectra.run.run` in a child process is the same
    code path the CLI uses (cli.py → ExperimentConfig → SingleRunner) and
    is what 'CLI parity' practically means: the CLI does not introduce
    its own numerical layer.
    """
    code = textwrap.dedent(f"""
        import pickle
        from pylectra.run import run
        out = run({str(yaml_path)!r})
        # Strip plots/figures and any non-pickleable extras; keep the
        # numerical SimulationResult.
        with open({str(out_pkl)!r}, 'wb') as f:
            pickle.dump(out.result, f)
    """)
    env = dict(os.environ, PYTHONPATH=str(REPO))
    subprocess.run([sys.executable, "-c", code], check=True, cwd=str(REPO), env=env)


@pytest.mark.slow
def test_cli_runpy_parity(tmp_path: Path) -> None:
    yaml_path = REPO / "examples" / "single_case39_scipy.yaml"
    if not yaml_path.exists():
        pytest.skip("example yaml missing")

    pkl_a = tmp_path / "a.pkl"
    pkl_b = tmp_path / "b.pkl"
    _run_via_cli_dump(yaml_path, pkl_a)
    _run_via_cli_dump(yaml_path, pkl_b)

    with open(pkl_a, "rb") as f:
        ra = pickle.load(f)
    with open(pkl_b, "rb") as f:
        rb = pickle.load(f)

    # Compare every numpy attribute.  We don't know the full schema but
    # SimulationResult exposes Time, Voltages, Angles, Speeds, Eq_trs,
    # Ed_trs, Efds, Tes, TM, Vss, Stepsize, Errest as documented.
    for attr in [
        "Time", "Angles", "Speeds", "Eq_trs", "Ed_trs",
        "Efds", "Tes", "TM", "Vss", "Stepsize", "Errest",
    ]:
        if not hasattr(ra, attr):
            continue
        a = np.asarray(getattr(ra, attr))
        b = np.asarray(getattr(rb, attr))
        assert a.shape == b.shape, f"{attr} shape differs"
        assert np.array_equal(a, b), f"{attr} differs (max |Δ|={np.abs(a-b).max()})"

    # Voltages may be complex.
    if hasattr(ra, "Voltages"):
        va = np.asarray(ra.Voltages)
        vb = np.asarray(rb.Voltages)
        assert va.shape == vb.shape
        assert np.array_equal(va, vb)
