"""Determinism check: compare two batch output directories byte-by-byte.

Usage::

    python tests/golden/compare_batches.py samples_run1 samples_run2

Walks every .h5 sample, checks all datasets for ``np.array_equal`` (bit
identical), then compares the parquet metadata via ``DataFrame.equals``.
Exits 0 on success, 1 on first mismatch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


def _walk_h5(g, prefix=""):
    for k, v in g.items():
        path = f"{prefix}/{k}" if prefix else k
        if isinstance(v, h5py.Group):
            yield from _walk_h5(v, path)
        else:
            yield path, v[...]


def compare_h5(a: Path, b: Path) -> bool:
    with h5py.File(a, "r") as fa, h5py.File(b, "r") as fb:
        da = dict(_walk_h5(fa))
        db = dict(_walk_h5(fb))
    if da.keys() != db.keys():
        print(f"[FAIL] {a.name}: dataset keys differ ({set(da)^set(db)})")
        return False
    for k in da:
        if not np.array_equal(da[k], db[k]):
            print(f"[FAIL] {a.name}:{k} arrays differ "
                  f"(max abs diff {np.abs(da[k]-db[k]).max()})")
            return False
    return True


def main(d1: str, d2: str) -> int:
    p1, p2 = Path(d1), Path(d2)
    files1 = sorted(p1.glob("sample_*.h5"))
    files2 = sorted(p2.glob("sample_*.h5"))
    if [f.name for f in files1] != [f.name for f in files2]:
        print(f"[FAIL] file lists differ")
        return 1
    ok = True
    for a, b in zip(files1, files2):
        if not compare_h5(a, b):
            ok = False
    m1 = pd.read_parquet(p1 / "metadata.parquet")
    m2 = pd.read_parquet(p2 / "metadata.parquet")
    # ``simulation_time`` and ``sample_path`` carry wall-clock and absolute
    # path info respectively — irrelevant for numerical determinism.
    drop = [c for c in ("simulation_time", "sample_path") if c in m1.columns]
    m1 = m1.drop(columns=drop)
    m2 = m2.drop(columns=drop)
    if not m1.equals(m2):
        diff_cols = [c for c in m1.columns if not m1[c].equals(m2[c])]
        print(f"[FAIL] metadata.parquet differs in cols: {diff_cols}")
        ok = False
    if ok:
        print(f"[OK] {len(files1)} samples + metadata identical")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
