"""Flat-vector pack/unpack for the dynamic state ``y = (Xgen, Xexc, Xgov)``.

PSS type-3 has no states (verified in :mod:`Models.PSS.PSSInit`) so it is
omitted from the state vector entirely.  Vpss is fixed to zero in the RHS.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class StateLayout:
    """Layout descriptor for the flat state vector ``y``.

    Order: ``[Xgen.ravel(), Xexc.ravel(), Xgov.ravel()]`` — generator block
    first to match the legacy ``rundyn`` save order.
    """

    ngen: int
    n_xgen: int = 4
    n_xexc: int = 1
    n_xgov: int = 4

    def __post_init__(self) -> None:
        self._xg_end = self.ngen * self.n_xgen
        self._xe_end = self._xg_end + self.ngen * self.n_xexc
        self.size = self._xe_end + self.ngen * self.n_xgov

    def pack(self, Xgen: np.ndarray, Xexc: np.ndarray, Xgov: np.ndarray) -> np.ndarray:
        return np.concatenate([
            np.asarray(Xgen, dtype=float).ravel(),
            np.asarray(Xexc, dtype=float).ravel(),
            np.asarray(Xgov, dtype=float).ravel(),
        ])

    def unpack(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        y = np.asarray(y, dtype=float).ravel()
        Xgen = y[:self._xg_end].reshape(self.ngen, self.n_xgen)
        Xexc = y[self._xg_end:self._xe_end].reshape(self.ngen, self.n_xexc)
        Xgov = y[self._xe_end:].reshape(self.ngen, self.n_xgov)
        return Xgen, Xexc, Xgov

    # ------------------------------------------------------------------
    # Batched torch helpers — Phase 1 of the GPU-batched engine.
    # ``y`` is expected to be a torch.Tensor of shape ``(B, S)`` where
    # ``S == self.size``.  Returned views share storage with ``y`` so
    # the RK4 driver can update state without extra copies.
    # ------------------------------------------------------------------
    def unpack_torch_batched(self, y):
        Xgen = y[:, :self._xg_end].view(-1, self.ngen, self.n_xgen)
        Xexc = y[:, self._xg_end:self._xe_end].view(-1, self.ngen, self.n_xexc)
        Xgov = y[:, self._xe_end:].view(-1, self.ngen, self.n_xgov)
        return Xgen, Xexc, Xgov

    def pack_torch_batched(self, Xgen, Xexc, Xgov):
        import torch
        B = Xgen.shape[0]
        return torch.cat([
            Xgen.reshape(B, -1),
            Xexc.reshape(B, -1),
            Xgov.reshape(B, -1),
        ], dim=1)
