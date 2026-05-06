"""Hardware auto-detection for the ``pylectra`` package.

Used by :class:`pylectra.runners.batch.BatchRunner` to choose a sensible default
``n_jobs`` and to guide users (``python -m pylectra info --hardware``).

Nothing in this module should *require* optional packages — every probe
silently degrades to a safe default if its dependency is missing.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass, field, asdict
from typing import Any


def cpu_count() -> int:
    """Logical CPU count, robust to containerized cgroup limits.

    Falls back to ``os.cpu_count()`` when ``len(os.sched_getaffinity(0))``
    is unavailable (macOS, Windows).
    """
    try:
        return len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def physical_cpu_count() -> int:
    """Physical-core count via ``psutil`` if available, else ``cpu_count()``."""
    try:
        import psutil  # type: ignore

        return psutil.cpu_count(logical=False) or cpu_count()
    except Exception:
        return cpu_count()


def total_memory_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        return None


def cuda_available() -> bool:
    """Return ``True`` iff a CUDA runtime + at least one device is visible.

    Probes (in order): ``torch.cuda.is_available``, ``cupy.cuda.is_available``,
    then ``nvidia-smi`` on PATH.  Never raises.
    """
    try:
        import torch  # type: ignore

        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            return True
    except Exception:
        pass
    try:
        import cupy  # type: ignore

        return cupy.cuda.is_available()
    except Exception:
        pass
    return shutil.which("nvidia-smi") is not None


def cuda_device_count() -> int:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return int(torch.cuda.device_count())
    except Exception:
        pass
    try:
        import cupy  # type: ignore

        return int(cupy.cuda.runtime.getDeviceCount())
    except Exception:
        pass
    return 0


def mps_available() -> bool:
    """Return True iff Apple Metal Performance Shaders backend is usable."""
    try:
        import torch  # type: ignore

        return bool(getattr(torch.backends, "mps", None)
                    and torch.backends.mps.is_available()
                    and torch.backends.mps.is_built())
    except Exception:
        return False


def torch_device(prefer: str = "auto", *,
                 dtype: str = "float64") -> str | None:
    """Pick a torch device name for the requested ``dtype``.

    Routing logic (when ``prefer == "auto"``):

    * ``cuda`` if available — supports both float32 and float64.
    * ``mps``  if available *and* ``dtype`` is float32 / complex64; otherwise
      skipped because MPS does not yet implement ``torch.linalg.solve`` for
      double-precision tensors.
    * ``cpu`` as the universal fallback.

    Returns ``None`` if torch is not importable.

    Pass ``prefer="cpu"`` / ``"cuda"`` / ``"mps"`` to force a specific
    device; an unsupported request raises :class:`RuntimeError`.
    """
    try:
        import torch  # type: ignore  # noqa: F401
    except Exception:
        return None

    p = prefer.lower()
    is_double = dtype.lower() in {"float64", "double", "complex128", "cdouble"}

    if p == "cuda":
        if not cuda_available():
            raise RuntimeError("torch_device(prefer='cuda') but CUDA not available")
        return "cuda"
    if p == "mps":
        if not mps_available():
            raise RuntimeError("torch_device(prefer='mps') but MPS not available")
        if is_double:
            raise RuntimeError(
                "torch_device(prefer='mps', dtype='float64'): MPS does not "
                "support double-precision linear algebra. Use dtype='float32'."
            )
        return "mps"
    if p == "cpu":
        return "cpu"
    if p != "auto":
        raise ValueError(f"unknown prefer={prefer!r}; want auto/cpu/cuda/mps")

    # auto
    if cuda_available():
        return "cuda"
    if mps_available() and not is_double:
        return "mps"
    return "cpu"


def recommend_n_jobs(target_workload: str = "batch") -> int:
    """Return a sensible ``n_jobs`` for joblib.

    * ``batch`` — leave one core for the OS / parent process; cap at 16
      (diminishing returns beyond that for our small models).
    * ``inner`` — single-sample inner-loop parallelism, currently always 1.
    """
    n = cpu_count()
    if target_workload == "inner":
        return 1
    return max(1, min(16, n - 1)) if n > 2 else max(1, n)


@dataclass
class HardwareSummary:
    os: str
    python: str
    logical_cpus: int
    physical_cpus: int
    memory_gb: float | None
    cuda: bool
    cuda_devices: int
    mps: bool
    torch_device: str | None
    recommended_n_jobs: int
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summary() -> HardwareSummary:
    try:
        td = torch_device("auto")
    except Exception:
        td = None
    return HardwareSummary(
        os=f"{platform.system()} {platform.release()} ({platform.machine()})",
        python=sys.version.split()[0],
        logical_cpus=cpu_count(),
        physical_cpus=physical_cpu_count(),
        memory_gb=total_memory_gb(),
        cuda=cuda_available(),
        cuda_devices=cuda_device_count(),
        mps=mps_available(),
        torch_device=td,
        recommended_n_jobs=recommend_n_jobs("batch"),
    )


def format_summary(s: HardwareSummary | None = None) -> str:
    s = s or summary()
    mem = f"{s.memory_gb:.1f} GB" if s.memory_gb else "?"
    cuda = f"yes ({s.cuda_devices} device{'s' if s.cuda_devices != 1 else ''})" if s.cuda else "no"
    mps = "yes" if s.mps else "no"
    td = s.torch_device or "n/a (torch not installed)"
    return (
        "Hardware:\n"
        f"  OS                : {s.os}\n"
        f"  Python            : {s.python}\n"
        f"  Logical CPUs      : {s.logical_cpus}\n"
        f"  Physical CPUs     : {s.physical_cpus}\n"
        f"  Memory            : {mem}\n"
        f"  CUDA              : {cuda}\n"
        f"  MPS (Apple)       : {mps}\n"
        f"  Torch device (auto): {td}\n"
        f"  Recommended n_jobs: {s.recommended_n_jobs}\n"
    )
