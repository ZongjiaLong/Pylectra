"""Phase 0 batch regression test.

Re-runs ``examples/batch_case39.yaml`` with ``count=5, seed=42, n_jobs=1``
and asserts byte-identical HDF5 + parquet match against the frozen golden
baseline at ``tests/golden/batch_case39_seed42_count5/``.

This is the **load-bearing** test for Phase 4 of the refactor: when the
batch pipeline is rewritten on top of native plugins, this test must still
pass.

Marked ``slow`` (run with ``pytest -m slow``) because it takes ~50 s.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "tests" / "golden" / "batch_case39_seed42_count5"


@pytest.mark.slow
def test_batch_matches_golden(tmp_path: Path) -> None:
    if not GOLDEN.exists():
        pytest.skip(f"no golden baseline at {GOLDEN}")

    # Build a config that mirrors the frozen run.
    src_yaml = REPO / "examples" / "batch_case39.yaml"
    cfg = yaml.safe_load(src_yaml.read_text())
    out_dir = tmp_path / "samples"
    cfg["output"]["directory"] = str(out_dir)
    cfg["output"]["parallel"]["n_jobs"] = 1
    cfg["scenarios"]["count"] = 5

    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))

    env = dict(os.environ, PYTHONPATH=str(REPO))
    subprocess.run(
        [sys.executable, "-m", "pylectra", "run", str(cfg_path)],
        check=True, env=env, cwd=str(REPO),
    )

    # ---- compare HDF5 samples (bit identical) -----------------------
    new_files = sorted(out_dir.glob("sample_*.h5"))
    gold_files = sorted(GOLDEN.glob("sample_*.h5"))
    assert [f.name for f in new_files] == [f.name for f in gold_files]

    for n, g in zip(new_files, gold_files):
        with h5py.File(n, "r") as fn, h5py.File(g, "r") as fg:
            keys = set(fn.keys()) | set(fg.keys())
            for k in keys:
                an = fn[k][...] if k in fn else None
                ag = fg[k][...] if k in fg else None
                assert np.array_equal(an, ag), f"{n.name}:{k} differs"

    # ---- compare metadata.parquet (modulo wall-clock fields) --------
    drop = ["simulation_time", "sample_path"]
    m_new = pd.read_parquet(out_dir / "metadata.parquet").drop(columns=drop, errors="ignore")
    m_gold = pd.read_parquet(GOLDEN / "metadata.parquet").drop(columns=drop, errors="ignore")
    assert m_new.equals(m_gold)
