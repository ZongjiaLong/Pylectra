"""Plugin registry for the ``pylectra`` package.

Each extension category (``generator``, ``exciter``, ``governor``, ``pss``,
``ode_solver``, ``power_flow``, ``fault``, ``scenario``, ``filter``) maintains
its own name-keyed dict.  Plugins register themselves at import time via the
:func:`register` decorator and are looked up by name from the YAML
configuration.

Adding a new plugin is therefore a two-step process:

1. Subclass the appropriate ABC from :mod:`pylectra.interfaces`.
2. Decorate the subclass with ``@register("<category>", "<name>")``.

After import (e.g. through ``import pylectra``), the new plugin is available to all
runners simply by referencing ``"<name>"`` in the YAML config.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")

# category -> (plugin name -> class)
_REGISTRY: Dict[str, Dict[str, type]] = defaultdict(dict)

# Recognised categories (used purely for validation / introspection).
CATEGORIES = (
    "generator",
    "exciter",
    "governor",
    "pss",
    "ode_solver",
    "power_flow",
    "fault",
    "scenario",
    "filter",
    "small_signal",
    "case",
    "plot",
)


def register(category: str, name: str) -> Callable[[Type[T]], Type[T]]:
    """Class decorator: register *cls* under ``category/name``.

    Raises
    ------
    ValueError
        If *category* is not one of the recognised categories, or if *name* is
        already taken inside *category*.
    """
    if category not in CATEGORIES:
        raise ValueError(
            f"unknown plugin category {category!r}; expected one of {CATEGORIES}"
        )

    def _decorate(cls: Type[T]) -> Type[T]:
        if name in _REGISTRY[category]:
            existing = _REGISTRY[category][name]
            if existing is cls:
                # Re-import (e.g. reloaded module) — be silent.
                return cls
            raise ValueError(
                f"plugin name {name!r} already registered in {category!r} by "
                f"{existing.__module__}.{existing.__name__}"
            )
        _REGISTRY[category][name] = cls
        # Annotate the class so users can introspect.
        setattr(cls, "__plugin_category__", category)
        setattr(cls, "__plugin_name__", name)
        return cls

    return _decorate


def get(category: str, name: str) -> type:
    """Look up the plugin class registered under ``category/name``."""
    if category not in _REGISTRY or name not in _REGISTRY[category]:
        avail = ", ".join(sorted(_REGISTRY.get(category, {}))) or "<none>"
        raise KeyError(
            f"unknown plugin {name!r} in category {category!r}. "
            f"registered names: {avail}"
        )
    return _REGISTRY[category][name]


def list_plugins(category: Optional[str] = None) -> Dict[str, List[str]]:
    """Return ``{category: [plugin names ...]}`` (optionally filtered)."""
    if category is not None:
        return {category: sorted(_REGISTRY.get(category, {}))}
    return {c: sorted(p) for c, p in sorted(_REGISTRY.items())}


def categories() -> List[str]:
    """Return sorted list of categories that currently hold at least one plugin."""
    return sorted(_REGISTRY)


def reset() -> None:
    """Clear the registry — for tests only."""
    _REGISTRY.clear()
