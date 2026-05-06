"""Phase 6 unit tests: ``pylectra.hardware.torch_device`` routing logic.

Runs without torch installed — uses ``monkeypatch`` to fake the
``cuda_available`` / ``mps_available`` probes so every branch of the
auto-router is exercised on any host (no GPU required).
"""
from __future__ import annotations

import pytest

import pylectra  # noqa: F401
from pylectra import hardware


# ---------------------------------------------------------------- explicit prefer
def test_prefer_cpu_always_returns_cpu(monkeypatch):
    monkeypatch.setattr(hardware, "cuda_available", lambda: True)
    monkeypatch.setattr(hardware, "mps_available", lambda: True)
    # Pretend torch is importable.
    import sys, types
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.ModuleType("torch")
    assert hardware.torch_device("cpu") == "cpu"


def test_prefer_cuda_without_gpu_raises(monkeypatch):
    monkeypatch.setattr(hardware, "cuda_available", lambda: False)
    import sys, types
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.ModuleType("torch")
    with pytest.raises(RuntimeError, match="CUDA not available"):
        hardware.torch_device("cuda")


def test_prefer_mps_without_mps_raises(monkeypatch):
    monkeypatch.setattr(hardware, "mps_available", lambda: False)
    import sys, types
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.ModuleType("torch")
    with pytest.raises(RuntimeError, match="MPS not available"):
        hardware.torch_device("mps")


def test_prefer_mps_with_float64_raises(monkeypatch):
    monkeypatch.setattr(hardware, "mps_available", lambda: True)
    import sys, types
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.ModuleType("torch")
    with pytest.raises(RuntimeError, match="float64"):
        hardware.torch_device("mps", dtype="float64")


# ----------------------------------------------------------------- auto routing
@pytest.mark.parametrize(
    "cuda,mps,dtype,want",
    [
        (True,  True,  "float64", "cuda"),  # cuda wins regardless of mps
        (True,  False, "float64", "cuda"),
        (False, True,  "float64", "cpu"),   # mps + float64 → cpu (mps no-double)
        (False, True,  "float32", "mps"),   # mps + float32 → mps
        (False, False, "float64", "cpu"),
        (False, False, "float32", "cpu"),
    ],
)
def test_auto_routing_branches(monkeypatch, cuda, mps, dtype, want):
    monkeypatch.setattr(hardware, "cuda_available", lambda: cuda)
    monkeypatch.setattr(hardware, "mps_available", lambda: mps)
    import sys, types
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.ModuleType("torch")
    assert hardware.torch_device("auto", dtype=dtype) == want


def test_auto_returns_none_when_torch_missing(monkeypatch):
    """If ``import torch`` fails, ``torch_device`` returns ``None``."""
    import sys, builtins

    real_import = builtins.__import__

    def _no_torch(name, *a, **k):
        if name == "torch":
            raise ImportError("simulated: torch missing")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_torch)
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    assert hardware.torch_device("auto") is None


def test_unknown_prefer_raises():
    with pytest.raises(ValueError, match="unknown prefer"):
        hardware.torch_device("xpu")
