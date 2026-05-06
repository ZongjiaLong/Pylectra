"""Per-sample HDF5 / NPZ writers for time-series outputs.

Each sample is stored as a single file inside ``output.directory``.  Writers
append a trailing index counter so callers can produce many samples without
collisions.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from pylectra.core.result import SimulationResult
    from pylectra.runners._pf_snapshot import PowerFlowSnapshot


_DATASETS = (
    "Time",
    "Voltages_real",
    "Voltages_imag",
    "Angles",
    "Speeds",
    "Eq_trs",
    "Ed_trs",
    "Efds",
    "Tes",
    "TM",
    "Vss",
    "Stepsize",
    "Errest",
)


def _as_numpy(result: "SimulationResult") -> dict:
    return {
        "Time": np.asarray(result.Time, dtype=float),
        "Voltages_real": np.asarray(result.Voltages.real, dtype=float),
        "Voltages_imag": np.asarray(result.Voltages.imag, dtype=float),
        "Angles": np.asarray(result.Angles, dtype=float),
        "Speeds": np.asarray(result.Speeds, dtype=float),
        "Eq_trs": np.asarray(result.Eq_trs, dtype=float),
        "Ed_trs": np.asarray(result.Ed_trs, dtype=float),
        "Efds": np.asarray(result.Efds, dtype=float),
        "Tes": np.asarray(result.Tes, dtype=float),
        "TM": np.asarray(result.TM, dtype=float),
        "Vss": np.asarray(result.Vss, dtype=float),
        "Stepsize": np.asarray(result.Stepsize, dtype=float),
        "Errest": np.asarray(result.Errest, dtype=float),
    }


class HDF5SampleWriter:
    """Write each sample as a separate ``.h5`` file under ``directory``.

    Uses ``h5py`` if available, otherwise raises ImportError.  Each dataset is
    gzip-compressed by default to keep batch outputs small.
    """

    def __init__(self, directory: Union[str, Path], compression: str | None = "gzip"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.compression = compression
        try:
            import h5py  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError("HDF5SampleWriter requires the 'h5py' package") from e

    def write(self, sample_id: str, result: "SimulationResult") -> Path:
        import h5py

        path = self.directory / f"{sample_id}.h5"
        data = _as_numpy(result)
        with h5py.File(path, "w") as f:
            for name, arr in data.items():
                if arr.size:
                    f.create_dataset(name, data=arr, compression=self.compression)
                else:
                    f.create_dataset(name, data=arr)
            f.attrs["simulation_time"] = float(result.simulation_time)
            f.attrs["pf_success"] = bool(result.pf_success)
            f.attrs["n_bus"] = int(result.n_bus)
            f.attrs["n_gen"] = int(result.n_gen)
            f.attrs["n_steps"] = int(result.n_steps)
            for k, v in result.metadata.items():
                # only persist scalar / string attrs at the top level
                if isinstance(v, (int, float, str, bool)):
                    f.attrs[f"meta:{k}"] = v
        return path


class NPZSampleWriter:
    """Write each sample as a separate ``.npz`` file (no h5py dependency)."""

    def __init__(self, directory: Union[str, Path]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write(self, sample_id: str, result: "SimulationResult") -> Path:
        path = self.directory / f"{sample_id}.npz"
        data = _as_numpy(result)
        data["simulation_time"] = np.array([result.simulation_time])
        data["pf_success"] = np.array([result.pf_success])
        np.savez_compressed(path, **data)
        return path


# ---------------------------------------------------------------------------
# Power-flow-only snapshot writers (used by ``batch_pf`` mode).
# ---------------------------------------------------------------------------

# MATPOWER column indices: bus VM/VA are columns 7/8 (0-based), gen PG/QG are
# columns 1/2, branch PF/QF/PT/QT are columns 13/14/15/16.  We resolve them
# lazily inside :func:`_pf_as_numpy` to keep the import cheap.

def _pf_as_numpy(snap: "PowerFlowSnapshot") -> dict:
    from pylectra.core.idx import idx_brch, idx_bus, idx_gen

    VM, VA = idx_bus()[11], idx_bus()[12]
    PG, QG = idx_gen()[1], idx_gen()[2]
    ib = idx_brch()
    PF, QF, PT, QT = ib[11], ib[12], ib[13], ib[14]
    return {
        "Bus_VM": np.asarray(snap.bus[:, VM], dtype=float),
        "Bus_VA": np.asarray(snap.bus[:, VA], dtype=float),
        "Gen_PG": np.asarray(snap.gen[:, PG], dtype=float),
        "Gen_QG": np.asarray(snap.gen[:, QG], dtype=float),
        "Branch_PF": np.asarray(snap.branch[:, PF], dtype=float),
        "Branch_QF": np.asarray(snap.branch[:, QF], dtype=float),
        "Branch_PT": np.asarray(snap.branch[:, PT], dtype=float),
        "Branch_QT": np.asarray(snap.branch[:, QT], dtype=float),
    }


class HDF5PFSnapshotWriter:
    """Write each PF snapshot as a separate ``.h5`` file under ``directory``."""

    def __init__(self, directory: Union[str, Path], compression: str | None = "gzip"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.compression = compression
        try:
            import h5py  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError("HDF5PFSnapshotWriter requires the 'h5py' package") from e

    def write(self, sample_id: str, snap: "PowerFlowSnapshot") -> Path:
        import h5py

        path = self.directory / f"{sample_id}.h5"
        data = _pf_as_numpy(snap)
        with h5py.File(path, "w") as f:
            for name, arr in data.items():
                if arr.size:
                    f.create_dataset(name, data=arr, compression=self.compression)
                else:
                    f.create_dataset(name, data=arr)
            f.attrs["pf_success"] = bool(snap.success)
            f.attrs["n_bus"] = int(snap.n_bus)
            f.attrs["n_gen"] = int(snap.n_gen)
            f.attrs["baseMVA"] = float(snap.baseMVA)
            f.attrs["et"] = float(snap.et)
            for k, v in snap.metadata.items():
                if isinstance(v, (int, float, str, bool)):
                    f.attrs[f"meta:{k}"] = v
        return path


class NPZPFSnapshotWriter:
    """Write each PF snapshot as a separate ``.npz`` file."""

    def __init__(self, directory: Union[str, Path]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write(self, sample_id: str, snap: "PowerFlowSnapshot") -> Path:
        path = self.directory / f"{sample_id}.npz"
        data = _pf_as_numpy(snap)
        data["pf_success"] = np.array([snap.success])
        data["baseMVA"] = np.array([snap.baseMVA])
        data["et"] = np.array([snap.et])
        np.savez_compressed(path, **data)
        return path
