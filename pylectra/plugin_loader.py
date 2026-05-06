"""Automatic plugin discovery.

Two mechanisms are layered:

1. **Built-in discovery** — every sub-package of ``pylectra`` is walked with
   :func:`pkgutil.walk_packages` and imported.  Importing a module that
   contains ``@register("category", "name")`` decorations is sufficient to
   populate the registry; this means new built-in plugins become available
   simply by dropping a ``.py`` file into ``pylectra/<category>/`` — no
   ``__init__.py`` edits required.

2. **Third-party discovery** — entry points published under the
   ``pylectra.plugins`` group are imported, letting external packages contribute
   plugins without forking ``pylectra``.

The whole system is intentionally idempotent so it is safe to call
:func:`discover` repeatedly (e.g. from tests).
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import Iterable

# Sub-packages that contain plugin implementations.  Sub-packages NOT in this
# list (e.g. ``pylectra.engine``, ``pylectra.core``) are framework infrastructure and
# are skipped to keep import time predictable.
_PLUGIN_SUBPACKAGES: tuple[str, ...] = (
    "models",
    "solvers",
    "powerflow",
    "faults",
    "scenarios",
    "filters",
    "small_signal",
    "cases",
    "plotting",
)

_DISCOVERED = False


def _walk(pkg_name: str) -> Iterable[str]:
    """Yield every importable sub-module of *pkg_name* (recursively)."""
    try:
        pkg = importlib.import_module(pkg_name)
    except ModuleNotFoundError:
        return
    if not hasattr(pkg, "__path__"):
        return
    for info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        yield info.name


def discover(force: bool = False) -> None:
    """Import every plugin module so decorators run.

    Parameters
    ----------
    force
        Re-run discovery even if it has already happened in this process.
        Useful in tests that call :func:`pylectra.registry.reset`.
    """
    global _DISCOVERED
    if _DISCOVERED and not force:
        return

    for sub in _PLUGIN_SUBPACKAGES:
        for mod_name in _walk(f"pylectra.{sub}"):
            try:
                importlib.import_module(mod_name)
            except Exception as exc:  # pragma: no cover - reported but non-fatal
                print(
                    f"[pylectra.plugin_loader] failed to import {mod_name}: {exc}",
                    file=sys.stderr,
                )

    # Third-party entry points.
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        # Python 3.10+ returns a SelectableGroups; fall back gracefully.
        group = (
            eps.select(group="pylectra.plugins")  # type: ignore[attr-defined]
            if hasattr(eps, "select")
            else eps.get("pylectra.plugins", [])
        )
        for ep in group:
            try:
                ep.load()
            except Exception as exc:  # pragma: no cover
                print(
                    f"[pylectra.plugin_loader] failed to load entry point {ep.name}: {exc}",
                    file=sys.stderr,
                )
    except Exception:  # pragma: no cover - importlib.metadata always present on >=3.8
        pass

    _DISCOVERED = True
