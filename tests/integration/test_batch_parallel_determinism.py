"""Phase 4 acceptance: ``n_jobs=1`` ↔ ``n_jobs=-1`` produce identical batches.

Determinism with parallel execution is implemented by seeding each worker
with ``base_seed + i`` so the i-th sample sees the same RNG regardless of
which process runs it.  This test pins that contract.

Marked ``slow`` (~80 s on a 4-core box; longer on many-core systems where
joblib startup overhead dominates a tiny count=5 batch).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


def _run(cfg_path: Path, tmp_dir: Path) -> None:
    # Joblib's resource_tracker on Windows trips ASCII-only encoding when
    # the temp path contains non-ASCII chars; pytest's tmp_path is under
    # the user temp folder which itself may be non-ASCII, so redirect to
    # an ASCII path under the repo (which is on D:\ — guaranteed ASCII).
    jl_tmp = REPO / ".pytest_joblib_tmp"
    jl_tmp.mkdir(exist_ok=True)
    env = dict(os.environ,
               PYTHONPATH=str(REPO),
               JOBLIB_TEMP_FOLDER=str(jl_tmp))
    subprocess.run(
        [sys.executable, "-m", "pylectra", "run", str(cfg_path)],
        check=True, env=env, cwd=str(REPO),
    )


def _walk(g, prefix=""):
    for k, v in g.items():
        path = f"{prefix}/{k}" if prefix else k
        if isinstance(v, h5py.Group):
            yield from _walk(v, path)
        else:
            yield path, v[...]


def _compare_h5(a: Path, b: Path) -> None:
    with h5py.File(a, "r") as fa, h5py.File(b, "r") as fb:
        da = dict(_walk(fa))
        db = dict(_walk(fb))
    assert da.keys() == db.keys(), f"{a.name} key mismatch"
    for k in da:
        assert np.array_equal(da[k], db[k]), (
            f"{a.name}:{k} differs (max |Δ|={np.abs(da[k]-db[k]).max()})"
        )


@pytest.mark.slow
def test_serial_parallel_identical(tmp_path: Path) -> None:
    src = REPO / "examples" / "batch_case39.yaml"
    if not src.exists():
        pytest.skip("example yaml missing")
    base = yaml.safe_load(src.read_text())
    base["scenarios"]["count"] = 4   # small for CI; still exercises N-1 outage RNG
    base["scenarios"]["seed"] = 42

    out_serial = tmp_path / "serial"
    out_par = tmp_path / "parallel"
    cfg_a = dict(base); cfg_a["output"] = dict(base["output"]); cfg_a["output"]["directory"] = str(out_serial); cfg_a["output"]["parallel"] = {"n_jobs": 1, "backend": "loky"}
    cfg_b = dict(base); cfg_b["output"] = dict(base["output"]); cfg_b["output"]["directory"] = str(out_par);    cfg_b["output"]["parallel"] = {"n_jobs": -1, "backend": "loky"}

    p_a = tmp_path / "a.yaml"; p_a.write_text(yaml.safe_dump(cfg_a))
    p_b = tmp_path / "b.yaml"; p_b.write_text(yaml.safe_dump(cfg_b))
    _run(p_a, tmp_path)
    _run(p_b, tmp_path)

    files_a = sorted(out_serial.glob("sample_*.h5"))
    files_b = sorted(out_par.glob("sample_*.h5"))
    assert [f.name for f in files_a] == [f.name for f in files_b]
    for a, b in zip(files_a, files_b):
        _compare_h5(a, b)

    drop = ["simulation_time", "sample_path"]
    ma = pd.read_parquet(out_serial / "metadata.parquet").drop(columns=drop, errors="ignore")
    mb = pd.read_parquet(out_par / "metadata.parquet").drop(columns=drop, errors="ignore")
    # Joblib may complete samples out of order — sort to canonical form first.
    ma = ma.sort_values("sample_id").reset_index(drop=True)
    mb = mb.sort_values("sample_id").reset_index(drop=True)
    assert ma.equals(mb)
