"""Native MATPOWER-style case loader (drop-in replacement for legacy ``loadcase``).

Resolves a string case name by importing a Python module from one of the
configured packages (``pylectra.data.cases`` first, then the legacy MATLAB-port
locations for backwards compatibility) and calling the same-named function.
Returns the resulting ``mpc`` dict (deep-copied if a dict was passed).
"""
from __future__ import annotations

import importlib
from copy import deepcopy
from typing import Any


_CASE_PACKAGES: tuple[str, ...] = (
    "pylectra.data.cases",
    "PowerFlow",
    "Cases.Powerflow",
    "Cases.Dynamic",
    "Cases.Events",
)


def loadcase(casefile: Any) -> dict:
    """Return the ``mpc`` dict for ``casefile``.

    ``casefile`` is either a dict (returned as a deep copy) or a string
    naming a Python case module on the search path.
    """
    if isinstance(casefile, dict):
        mpc = deepcopy(casefile)
    elif isinstance(casefile, str):
        name = casefile
        for ext in (".m", ".py"):
            if name.endswith(ext):
                name = name[: -len(ext)]
        mod = None
        last_err: Exception | None = None
        for pkg in _CASE_PACKAGES:
            try:
                mod = importlib.import_module(f"{pkg}.{name}")
                break
            except ImportError as e:
                last_err = e
                continue
        if mod is None:
            raise IOError(
                f"loadcase: case module {name!r} not found in {_CASE_PACKAGES}: {last_err}"
            )
        if not hasattr(mod, name):
            raise AttributeError(
                f"loadcase: module {mod.__name__!r} has no attribute {name!r}"
            )
        mpc = getattr(mod, name)()
        if not isinstance(mpc, dict):
            raise TypeError(f"loadcase: case function {name!r} must return a dict")
    else:
        raise TypeError(
            "loadcase: input arg must be a dict or a string containing a case name"
        )

    for f in ("baseMVA", "bus", "gen", "branch"):
        if f not in mpc:
            raise KeyError(f"loadcase: case missing required field {f!r}")

    if "version" not in mpc:
        mpc["version"] = "2" if mpc["gen"].shape[1] >= 21 else "1"

    return mpc


__all__ = ["loadcase"]
