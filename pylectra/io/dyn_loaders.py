"""Native dynamic-case data loaders.

Drop-in replacement for the legacy ``PowerFlow.Load{dyn,gen,exc,gov,pss,events}``
free functions. Each loader accepts the same three input shapes:

1. ``dict`` — already-loaded case dict with the canonical keys.
2. ``callable`` — zero-arg function returning the canonical tuple.
3. ``str`` — name of a Python module on ``sys.path`` exposing a function of
   the same name returning the canonical tuple.

Return shapes are bit-identical to the legacy loaders (same dtype, same
column count, same orientation) — they are validated by the parity tests
in ``tests/numerical/test_dyn_loaders_parity.py``.
"""
from __future__ import annotations

import importlib
from typing import Any

import numpy as np

# Search roots for string-named cases, mirrors the legacy resolver so the
# native loaders can import the existing case modules during the migration.
_PKGS: tuple[str, ...] = (
    "PowerFlow",
    "Cases.Powerflow",
    "Cases.Dynamic",
    "Cases.Events",
    "pylectra.data.cases",
)


def _resolve_dyn(casefile_dyn: Any) -> tuple:
    """Return the canonical 7-tuple ``(gen, exc, pss, gov, freq, step, stop)``.

    Accepts a dict, a callable, or a string module name. Synthesises an
    empty PSS matrix when the underlying case returns a 6-tuple.
    """
    if isinstance(casefile_dyn, dict):
        return (
            casefile_dyn.get("gen"),
            casefile_dyn.get("exc"),
            casefile_dyn.get("pss", np.zeros((0, 0))),
            casefile_dyn.get("gov"),
            casefile_dyn["freq"],
            casefile_dyn["stepsize"],
            casefile_dyn["stoptime"],
        )

    if callable(casefile_dyn):
        fn = casefile_dyn
    else:
        name = str(casefile_dyn)
        for ext in (".m", ".py"):
            if name.endswith(ext):
                name = name[: -len(ext)]
        fn = None
        last_err: Exception | None = None
        for pkg in _PKGS:
            try:
                mod = importlib.import_module(f"{pkg}.{name}")
                fn = getattr(mod, name)
                break
            except (ImportError, AttributeError) as e:
                last_err = e
        if fn is None:
            try:
                mod = importlib.import_module(name)
                fn = getattr(mod, name)
            except Exception:
                raise ImportError(
                    f"Could not load dynamic case {casefile_dyn!r}: {last_err}"
                )

    out = fn()
    if not isinstance(out, tuple):
        raise TypeError(f"Dynamic case {casefile_dyn!r} did not return a tuple")

    if len(out) == 7:
        gen, exc, pss, gov, freq, stepsize, stoptime = out
    elif len(out) == 6:
        gen, exc, gov, freq, stepsize, stoptime = out
        pss = np.zeros((0, 0))
    else:
        raise ValueError(
            f"Dynamic case {casefile_dyn!r} returned {len(out)} values; expected 6 or 7"
        )
    return gen, exc, pss, gov, freq, stepsize, stoptime


def loaddyn(casefile_dyn: Any) -> tuple[float, float, float]:
    """Return ``(freq, stepsize, stoptime)``."""
    if isinstance(casefile_dyn, dict):
        return (casefile_dyn["freq"],
                casefile_dyn["stepsize"],
                casefile_dyn["stoptime"])
    _, _, _, _, freq, stepsize, stoptime = _resolve_dyn(casefile_dyn)
    return freq, stepsize, stoptime


def loadgen(casefile_dyn: Any, output: int = 0) -> np.ndarray:
    """Return generator parameter matrix as float ``ndarray``."""
    if isinstance(casefile_dyn, dict):
        gen = casefile_dyn["gen"]
    else:
        gen, _, _, _, _, _, _ = _resolve_dyn(casefile_dyn)
    return np.asarray(gen, dtype=float)


def loadexc(casefile_dyn: Any) -> np.ndarray:
    if isinstance(casefile_dyn, dict):
        exc = casefile_dyn["exc"]
    else:
        _, exc, _, _, _, _, _ = _resolve_dyn(casefile_dyn)
    return np.asarray(exc, dtype=float)


def loadgov(casefile_dyn: Any) -> np.ndarray:
    if isinstance(casefile_dyn, dict):
        gov = casefile_dyn["gov"]
    else:
        _, _, _, gov, _, _, _ = _resolve_dyn(casefile_dyn)
    return np.asarray(gov, dtype=float)


def loadpss(casefile_dyn: Any) -> np.ndarray:
    if isinstance(casefile_dyn, dict):
        pss = casefile_dyn.get("pss", np.zeros((0, 0)))
    else:
        _, _, pss, _, _, _, _ = _resolve_dyn(casefile_dyn)
    return np.asarray(pss, dtype=float)


# ----------------------------------------------------------------------- events

_EV_PKGS: tuple[str, ...] = _PKGS


def _resolve_event(casefile_ev: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if isinstance(casefile_ev, dict):
        return (np.asarray(casefile_ev["event"], dtype=float),
                np.asarray(casefile_ev["buschange"], dtype=float),
                np.asarray(casefile_ev["linechange"], dtype=float))
    if callable(casefile_ev):
        fn = casefile_ev
    else:
        name = str(casefile_ev)
        for ext in (".m", ".py"):
            if name.endswith(ext):
                name = name[: -len(ext)]
        fn = None
        last_err: Exception | None = None
        for pkg in _EV_PKGS:
            try:
                mod = importlib.import_module(f"{pkg}.{name}")
                fn = getattr(mod, name)
                break
            except (ImportError, AttributeError) as e:
                last_err = e
        if fn is None:
            raise ImportError(
                f"Could not load event case {casefile_ev!r}: {last_err}"
            )
    event, type1, type2 = fn()
    return (np.asarray(event, dtype=float),
            np.asarray(type1, dtype=float),
            np.asarray(type2, dtype=float))


def loadevents(casefile_ev: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(event, buschange, linechange)`` per legacy convention.

    Rows of ``buschange`` / ``linechange`` are zero-filled when the
    corresponding ``event`` row is of the other kind.
    """
    event, type1, type2 = _resolve_event(casefile_ev)
    n = event.shape[0]
    buschange = np.zeros((n, 4))
    linechange = np.zeros((n, 4))

    type1 = np.atleast_2d(type1) if type1.size else type1.reshape(0, 4)
    type2 = np.atleast_2d(type2) if type2.size else type2.reshape(0, 4)

    i1 = 0
    i2 = 0
    for i in range(n):
        kind = int(event[i, 1])
        if kind == 1:
            buschange[i, :] = type1[i1, :]
            i1 += 1
        elif kind == 2:
            linechange[i, :] = type2[i2, :]
            i2 += 1
    return event, buschange, linechange


__all__ = [
    "loaddyn", "loadgen", "loadexc", "loadgov", "loadpss", "loadevents",
]
