"""Network case wrapper.

Wraps the legacy ``mpc`` dict produced by :func:`PowerFlow.loadcase.loadcase`
so callers can write ``case.bus``, ``case.gen``, ``case.branch`` instead of
``mpc['bus']`` etc., while keeping the underlying data layout intact for
downstream legacy code that still expects the dict.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

import numpy as np

# Legacy ``loadcase`` import deferred — see ``NetworkCase.load`` below.
# The pylectra-native ``case`` registry is consulted first so pandapower-backed
# names (case9 / case14 / case30 / case39 / case57 / case118) never touch
# the legacy package.


class NetworkCase:
    """Thin facade around the MATPOWER-style ``mpc`` dict.

    The dict itself is exposed as :attr:`mpc` so callers that interface with
    legacy code can keep using it directly.
    """

    __slots__ = ("mpc", "success", "iterations", "net")

    def __init__(self, mpc: Dict[str, Any], net: Any = None):
        self.mpc: Dict[str, Any] = mpc
        self.success: Optional[bool] = mpc.get("success")
        self.iterations: Optional[int] = None
        # Optional pandapowerNet (set when the case originated from a
        # pandapower-backed CaseLoader).  May be None for legacy cases.
        self.net = net

    # ---- factory helpers -------------------------------------------------

    @classmethod
    def load(cls, source) -> "NetworkCase":
        """Load a case by name, dict, or path.

        Resolution order:

        1. If *source* is a string and a ``case`` plugin is registered
           under that name (e.g. ``"case39"``), use the pandapower-backed
           loader — no legacy code is touched.
        2. Otherwise fall back to the legacy ``PowerFlow.loadcase`` for
           historical formats and dict mpc inputs.
        """
        if isinstance(source, str):
            try:
                from pylectra.registry import get as _registry_get
                loader_cls = _registry_get("case", source)
                return loader_cls().load(source)
            except (KeyError, ImportError):
                # KeyError: name not in case registry → try legacy.
                # ImportError: pandapower missing → fall back to legacy too.
                pass
        from pylectra.io.loadcase import loadcase as _native_loadcase
        return cls(_native_loadcase(source))

    def copy(self) -> "NetworkCase":
        """Deep-copy the underlying mpc dict (and pandapower net if present)."""
        new = NetworkCase(deepcopy(self.mpc), deepcopy(self.net) if self.net is not None else None)
        new.success = self.success
        new.iterations = self.iterations
        return new

    # ---- convenience accessors ------------------------------------------

    @property
    def baseMVA(self) -> float:
        return float(self.mpc["baseMVA"])

    @property
    def bus(self) -> np.ndarray:
        return self.mpc["bus"]

    @property
    def gen(self) -> np.ndarray:
        return self.mpc["gen"]

    @property
    def branch(self) -> np.ndarray:
        return self.mpc["branch"]

    @property
    def n_bus(self) -> int:
        return int(self.bus.shape[0])

    @property
    def n_gen(self) -> int:
        return int(self.gen.shape[0])

    @property
    def n_branch(self) -> int:
        return int(self.branch.shape[0])

    def __repr__(self) -> str:  # pragma: no cover — diagnostic
        return (
            f"<NetworkCase n_bus={self.n_bus} n_gen={self.n_gen} "
            f"n_branch={self.n_branch} success={self.success}>"
        )
