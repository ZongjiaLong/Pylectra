"""ABC for visualization plugins.

Every plot in ``pylectra`` — time-series, batch statistics, topology, animations
— is a :class:`PlotPlugin`. The CLI (``pylectra plot --kind <name>``) and the
Python helper :func:`pylectra.plotting.render` both look up plugins via the
registry under category ``"plot"``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlotPlugin(ABC):
    """Base class for renderable visualizations."""

    #: registry name (set via ``@register("plot", "<name>")``)
    name: str = ""

    #: which kind of object :meth:`render` expects as ``data``.
    #: One of ``"single"`` | ``"batch"`` | ``"case"`` | ``"sweep"`` |
    #: ``"small_signal"``.
    input_kind: str = "single"

    @abstractmethod
    def render(self, data: Any, ax=None, **kwargs):
        """Render the plot.

        Parameters
        ----------
        data
            Object whose type matches :attr:`input_kind`.
        ax
            Optional ``matplotlib.axes.Axes``; if ``None`` a new figure is
            created.  Plugins that need multi-panel layouts may ignore *ax*
            and create their own ``Figure``.
        **kwargs
            Plot-specific keyword arguments (e.g. ``gens``, ``metric``,
            ``save``).

        Returns
        -------
        matplotlib.figure.Figure | matplotlib.axes.Axes
            The figure or axes the plugin drew on, so callers can further
            customize or save it.
        """
        raise NotImplementedError

    def expected_inputs(self) -> dict[str, Any]:
        """Describe accepted kwargs (used by CLI ``--help`` and validation).

        Default: empty dict.  Override to return ``{"param": (type, default,
        description), ...}``.
        """
        return {}
