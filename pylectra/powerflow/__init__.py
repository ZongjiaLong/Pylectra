"""Power-flow plugins."""

from . import newton  # noqa: F401

# pandapower is an optional heavy dependency; importing the wrapper is cheap
# but pp itself is only loaded on first ``solve()`` call.  We still register
# the plugin eagerly so ``python -m pylectra info`` lists it.
try:
    from . import pp_backend  # noqa: F401
    _HAS_PP_BACKEND = True
except ImportError:  # pragma: no cover
    _HAS_PP_BACKEND = False

__all__ = ["newton", "pp_backend"]
