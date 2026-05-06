"""System nominal frequency — pylectra-native shared global.

Canonical place where the system frequency is stored at runtime.  All
native plugins read ``pylectra.core.freq.freq`` (e.g.
:class:`TwoAxisGenerator.init` uses ``2π·freq`` to fill ``omega0``).

Usage
-----
::

    from pylectra.core import freq as _f
    omega0 = 2.0 * math.pi * _f.freq            # read

    from pylectra.core.freq import set_freq
    set_freq(50.0)                              # write
"""
from __future__ import annotations

#: Nominal system frequency [Hz].  60.0 by default; the engine rewrites
#: this from the dynamic-data file at runtime.
freq: float = 60.0


def set_freq(value: float) -> None:
    """Set the system frequency global."""
    global freq
    freq = float(value)
