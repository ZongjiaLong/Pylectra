"""Case loaders — produce :class:`pylectra.core.case.NetworkCase` objects.

Importing the package registers every built-in :class:`CaseLoader` under the
``"case"`` registry category.  Add a new topology by creating a module in
this package, subclassing :class:`pylectra.interfaces.CaseLoader` and decorating
with ``@register("case", "<id>")``.
"""

from . import pp_builtin  # noqa: F401  (registers pandapower-backed loaders)

__all__: list[str] = []
