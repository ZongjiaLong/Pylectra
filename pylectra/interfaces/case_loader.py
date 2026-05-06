"""ABC for case (network topology) loaders.

A :class:`CaseLoader` produces a :class:`pylectra.core.case.NetworkCase` from a
human-friendly identifier (``"case39"``) or a dict spec parsed from YAML.
This is the replacement for the legacy ``PowerFlow/case*.py`` MATPOWER-style
matrices: every topology now flows through this single contract, regardless
of whether it is a pandapower built-in, a MATPOWER ``.m`` file, or a custom
JSON dump.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CaseLoader(ABC):
    """Load a :class:`NetworkCase` from a name or YAML-style spec."""

    #: registry name; subclasses set this via ``@register("case", "<id>")``.
    name: str = ""

    @abstractmethod
    def load(self, identifier: str | dict[str, Any]):
        """Return a populated :class:`NetworkCase`.

        Parameters
        ----------
        identifier
            Either a string (e.g. ``"case39"``) or a dict spec from YAML
            (e.g. ``{"path": "data/my_grid.json"}``).

        Returns
        -------
        NetworkCase
            Wrapper around the underlying ``pandapowerNet``.
        """
        raise NotImplementedError
