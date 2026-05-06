"""Tests for the ``batch_pf`` mode (batch power-flow only).

Covers:
* smoke (count=4 produces 4 .h5 files + metadata rows)
* voltage_range filter rejecting the bulk of samples
* keep_failed semantics
* serial vs joblib parallel determinism (metadata equivalence)
"""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest

import pylectra  # noqa: F401  — populates plugin registry
from pylectra.config import ExperimentConfig
from pylectra.runners.batch_pf import BatchPFRunner


def _base_cfg(tmp_path: Path, **overrides) -> ExperimentConfig:
    d = {
        "mode": "batch_pf",
        "case_pf": "case39",
        "power_flow": {"kind": "newton"},
        "scenarios": {
            "count": 4,
            "seed": 42,
            "generators": [
                {"kind": "load_perturb",
                 "params": {"sigma_pct": 5.0, "clip_pct": 20.0}},
            ],
        },
        "filters": [{"kind": "pf_converged"}],
        "output": {
            "directory": str(tmp_path / "samples_pf"),
            "format": "hdf5",
            "metadata": "csv",
            "keep_failed": False,
            "parallel": {"n_jobs": 1, "backend": "loky"},
        },
        "verbose": 0,
    }
    # shallow recursive merge for top-level overrides
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = v
    return ExperimentConfig.from_dict(d)


def test_batch_pf_smoke(tmp_path: Path) -> None:
    cfg = _base_cfg(tmp_path)
    stats = BatchPFRunner(cfg).run()
    assert stats.total == 4
    assert stats.accepted == 4
    assert stats.rejected == 0

    out = Path(cfg.output.directory)
    files = sorted(out.glob("sample_*.h5"))
    assert len(files) == 4
    meta = pd.read_csv(out / "metadata.csv")
    assert len(meta) == 4
    assert meta["passed"].all()
    assert (meta["pf_success"] == True).all()  # noqa: E712
    assert set(meta["sample_id"]) == {f"sample_{i:06d}" for i in range(4)}

    # Inspect one HDF5 file: contains the documented PF datasets.
    with h5py.File(files[0], "r") as f:
        for name in ("Bus_VM", "Bus_VA", "Gen_PG", "Gen_QG",
                     "Branch_PF", "Branch_QF", "Branch_PT", "Branch_QT"):
            assert name in f, f"missing dataset {name}"
        vm = f["Bus_VM"][...]
        assert vm.shape == (39,)
        assert ((vm > 0.5) & (vm < 1.5)).all()
        assert bool(f.attrs["pf_success"]) is True
        assert int(f.attrs["n_bus"]) == 39


def test_batch_pf_filter_voltage_rejects(tmp_path: Path) -> None:
    cfg = _base_cfg(
        tmp_path,
        filters=[
            {"kind": "pf_converged"},
            # Force-reject: vmin above realistic case39 voltages → all rejected.
            {"kind": "voltage_range",
             "params": {"vmin": 1.05, "vmax": 1.15}},
        ],
    )
    stats = BatchPFRunner(cfg).run()
    assert stats.total == 4
    assert stats.rejected >= 3  # almost certainly all rejected
    assert stats.accepted == stats.total - stats.rejected
    assert stats.rejections_by_filter.get("voltage_range", 0) >= 3

    out = Path(cfg.output.directory)
    # keep_failed=False → no sample files written for rejects
    assert len(list(out.glob("sample_*.h5"))) == stats.accepted
    meta = pd.read_csv(out / "metadata.csv")
    assert (meta.loc[~meta["passed"], "rejected_by"] == "voltage_range").all()


def test_batch_pf_keep_failed(tmp_path: Path) -> None:
    cfg = _base_cfg(
        tmp_path,
        filters=[
            {"kind": "pf_converged"},
            {"kind": "voltage_range",
             "params": {"vmin": 1.05, "vmax": 1.15}},
        ],
        output={"keep_failed": True},
    )
    stats = BatchPFRunner(cfg).run()
    out = Path(cfg.output.directory)
    # With keep_failed=True every PF-converged sample is on disk.
    files = sorted(out.glob("sample_*.h5"))
    assert len(files) == stats.total - stats.pf_failed


def test_batch_pf_parallel_metadata_matches_serial(tmp_path: Path, monkeypatch) -> None:
    # joblib's resource_tracker on Windows trips ASCII-only encoding when the
    # default temp folder contains non-ASCII chars; redirect to an ASCII path
    # under the repo (mirrors test_batch_parallel_determinism.py).
    repo = Path(__file__).resolve().parents[2]
    jl_tmp = repo / ".pytest_joblib_tmp"
    jl_tmp.mkdir(exist_ok=True)
    monkeypatch.setenv("JOBLIB_TEMP_FOLDER", str(jl_tmp))

    cfg_serial = _base_cfg(
        tmp_path / "serial",
        output={"directory": str(tmp_path / "serial")},
    )
    cfg_par = _base_cfg(
        tmp_path / "parallel",
        output={"directory": str(tmp_path / "parallel"),
                "parallel": {"n_jobs": 2, "backend": "loky"}},
    )
    BatchPFRunner(cfg_serial).run()
    BatchPFRunner(cfg_par).run()

    drop = ["simulation_time", "sample_path"]
    a = pd.read_csv(Path(cfg_serial.output.directory) / "metadata.csv")
    b = pd.read_csv(Path(cfg_par.output.directory) / "metadata.csv")
    a = a.drop(columns=drop, errors="ignore").sort_values("sample_id").reset_index(drop=True)
    b = b.drop(columns=drop, errors="ignore").sort_values("sample_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_batch_pf_unused_fields_ignored(tmp_path: Path) -> None:
    """``case_dyn`` / ``solver`` / ``fault`` must not be required in batch_pf."""
    cfg = _base_cfg(tmp_path)
    # Default solver is modified_euler — even if its dyn data path is broken
    # the runner must not load it.  We verify by simply running.
    stats = BatchPFRunner(cfg).run()
    assert stats.total == 4
