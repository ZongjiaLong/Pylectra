"""Pandapower-backed CaseLoader plugins for built-in IEEE test systems.

Each loader pulls a network from :mod:`pandapower.networks`, converts it to
the legacy MATPOWER ``mpc`` dict layout via ``pandapower.converter.to_mpc``,
and wraps both into a :class:`NetworkCase`. The conversion preserves the
``mpc`` interface required by the existing engine while exposing the rich
``pandapowerNet`` (``case.net``) for downstream pandapower-native code.
"""
from __future__ import annotations

from typing import Any

from ..interfaces.case_loader import CaseLoader
from ..core.case import NetworkCase
from ..registry import register


def _to_network_case(net) -> NetworkCase:
    """Convert a ``pandapowerNet`` to a :class:`NetworkCase`.

    Uses ``pandapower.converter.to_mpc`` to produce a MATPOWER-style dict so
    the existing legacy engine (which still expects ``case.mpc['bus']`` etc.)
    continues to work unchanged.
    """
    # Local imports so importing pylectra doesn't hard-fail when pandapower is
    # absent — the error is raised only when a pandapower-backed loader is
    # actually invoked.
    try:
        from pandapower.converter import to_mpc  # pandapower < 3.0
    except ImportError:
        from pandapower.converter.matpower.to_mpc import to_mpc  # pandapower >= 3.0

    # pandapower >= 3.0 requires explicit init='flat' when res_bus is empty;
    # older versions ignore the kwarg.
    try:
        raw = to_mpc(net, init="flat")
    except TypeError:
        raw = to_mpc(net)
    # ``to_mpc`` returns ``{"mpc": {...}}`` in some versions and a flat dict
    # in others; normalise.
    mpc = raw.get("mpc", raw) if isinstance(raw, dict) else raw
    return NetworkCase(mpc, net=net)


class _PandapowerBuiltin(CaseLoader):
    """Base class for ``pandapower.networks`` builtins."""

    builder_name: str = ""  # set by subclasses

    def load(self, identifier: str | dict[str, Any]) -> NetworkCase:
        import pandapower.networks as ppn

        builder = getattr(ppn, self.builder_name, None)
        if builder is None:
            raise RuntimeError(
                f"pandapower.networks has no builder named {self.builder_name!r}"
            )
        return _to_network_case(builder())


@register("case", "case9")
class Case9Loader(_PandapowerBuiltin):
    name = "case9"
    builder_name = "case9"


@register("case", "case14")
class Case14Loader(_PandapowerBuiltin):
    name = "case14"
    builder_name = "case14"


@register("case", "case30")
class Case30Loader(_PandapowerBuiltin):
    name = "case30"
    builder_name = "case_ieee30"


@register("case", "case39")
class Case39Loader(_PandapowerBuiltin):
    name = "case39"
    builder_name = "case39"


@register("case", "case57")
class Case57Loader(_PandapowerBuiltin):
    name = "case57"
    builder_name = "case57"


@register("case", "case118")
class Case118Loader(_PandapowerBuiltin):
    name = "case118"
    builder_name = "case118"
