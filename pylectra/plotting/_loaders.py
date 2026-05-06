"""Helpers for loading simulation results from disk for plotting.

Supports the file formats written by :mod:`pylectra.io.hdf5_writer`:

* ``.h5``  — HDF5 sample, datasets named ``Time``, ``Voltages_real``,
  ``Voltages_imag``, ``Angles``, ``Speeds``, ``Eq_trs``, ``Ed_trs``,
  ``Efds``, ``Tes``, ``TM``, ``Vss``, ``Stepsize``, ``Errest`` and
  attributes ``simulation_time``, ``pf_success``, ``n_bus``, ``n_gen``,
  ``n_steps`` plus ``meta:*`` extras.
* ``.npz`` — NumPy zipped archive with the same array names plus
  ``simulation_time`` (length-1) and ``pf_success`` (length-1).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

import numpy as np

from pylectra.core.result import SimulationResult


PathLike = Union[str, Path]


def _load_h5(path: Path) -> SimulationResult:
    import h5py

    with h5py.File(path, "r") as f:
        def get(name: str, default=None) -> np.ndarray:
            if name in f:
                return np.asarray(f[name][()])
            return default if default is not None else np.zeros(0)

        time = get("Time")
        v_re = get("Voltages_real")
        v_im = get("Voltages_imag")
        if v_re.size and v_im.size:
            voltages = (v_re + 1j * v_im).astype(complex)
        else:
            voltages = np.zeros((0, 0), dtype=complex)

        meta: Dict[str, Any] = {}
        for k, v in f.attrs.items():
            if isinstance(k, bytes):
                k = k.decode()
            if k.startswith("meta:"):
                val = v.decode() if isinstance(v, bytes) else v
                meta[k[len("meta:"):]] = val

        return SimulationResult(
            Time=time,
            Voltages=voltages,
            Angles=get("Angles"),
            Speeds=get("Speeds"),
            Eq_trs=get("Eq_trs"),
            Ed_trs=get("Ed_trs"),
            Efds=get("Efds"),
            Tes=get("Tes"),
            TM=get("TM"),
            Vss=get("Vss"),
            Stepsize=get("Stepsize"),
            Errest=get("Errest"),
            simulation_time=float(f.attrs.get("simulation_time", 0.0)),
            pf_success=bool(f.attrs.get("pf_success", True)),
            metadata=meta,
        )


def _load_npz(path: Path) -> SimulationResult:
    arr = np.load(path)
    v_re = arr["Voltages_real"] if "Voltages_real" in arr.files else np.zeros(0)
    v_im = arr["Voltages_imag"] if "Voltages_imag" in arr.files else np.zeros(0)
    if v_re.size and v_im.size:
        voltages = (v_re + 1j * v_im).astype(complex)
    else:
        voltages = np.zeros((0, 0), dtype=complex)
    return SimulationResult(
        Time=np.asarray(arr["Time"]),
        Voltages=voltages,
        Angles=np.asarray(arr["Angles"]),
        Speeds=np.asarray(arr["Speeds"]),
        Eq_trs=np.asarray(arr["Eq_trs"]),
        Ed_trs=np.asarray(arr["Ed_trs"]),
        Efds=np.asarray(arr["Efds"]),
        Tes=np.asarray(arr["Tes"]),
        TM=np.asarray(arr["TM"]),
        Vss=np.asarray(arr["Vss"]),
        Stepsize=np.asarray(arr["Stepsize"]),
        Errest=np.asarray(arr["Errest"]),
        simulation_time=float(np.asarray(arr["simulation_time"]).item())
            if "simulation_time" in arr.files else 0.0,
        pf_success=bool(np.asarray(arr["pf_success"]).item())
            if "pf_success" in arr.files else True,
        metadata={},
    )


def load_result(source: Union[PathLike, SimulationResult]) -> SimulationResult:
    """Resolve ``source`` to a :class:`SimulationResult`.

    * Pass-through if ``source`` is already a result.
    * ``.h5`` path → :func:`_load_h5`.
    * ``.npz`` path → :func:`_load_npz`.
    """
    if isinstance(source, SimulationResult):
        return source
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(p)
    suf = p.suffix.lower()
    if suf == ".h5":
        return _load_h5(p)
    if suf == ".npz":
        return _load_npz(p)
    raise ValueError(
        f"unsupported result file extension {suf!r} (expected .h5 or .npz)"
    )


__all__ = ["load_result"]
