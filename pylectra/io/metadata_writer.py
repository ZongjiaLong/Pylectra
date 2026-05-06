"""Per-batch metadata index — one row per produced sample.

Two backends:

* Parquet (default, requires ``pyarrow`` or ``pandas``).
* CSV (fallback, always available).

The metadata table records:

* ``sample_id``      — string identifier (matches the sample file basename).
* ``passed``         — overall filter decision.
* ``rejected_by``    — first filter to reject (empty if accepted).
* ``rejected_reason``— human-readable reason from that filter.
* ``simulation_time``— wallclock seconds of the run.
* ``pf_success``     — whether the steady-state power flow converged.
* ``n_steps``        — number of time-series points stored.
* one column per ``filter_<name>_metric`` — numeric metric for each filter.
* one column per ``meta:<key>`` from ``Scenario.metadata`` (scenario inputs).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd


class MetadataWriter:
    """Append-only metadata table."""

    def __init__(self, path: Union[str, Path], format: str = "parquet"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if format not in ("parquet", "csv"):
            raise ValueError(f"unknown metadata format {format!r}")
        self.format = format
        self._rows: List[Dict] = []

    def add(self, row: Dict) -> None:
        """Buffer one row.  Call :meth:`flush` to persist."""
        self._rows.append(row)

    def flush(self) -> Optional[Path]:
        """Persist all buffered rows to ``self.path``.  Returns the path."""
        if not self._rows:
            return None
        df = pd.DataFrame(self._rows)
        # If a previous file exists, concat-and-rewrite (small batches; we don't
        # bother with append-streaming for Phase 1).
        if self.path.exists():
            try:
                if self.format == "parquet":
                    prev = pd.read_parquet(self.path)
                else:
                    prev = pd.read_csv(self.path)
                df = pd.concat([prev, df], ignore_index=True)
            except Exception:
                pass  # corrupt / unreadable previous file — overwrite
        if self.format == "parquet":
            try:
                df.to_parquet(self.path, index=False)
            except Exception as e:
                # pyarrow missing? fall back to CSV with a friendly message.
                csv_path = self.path.with_suffix(".csv")
                df.to_csv(csv_path, index=False)
                self.path = csv_path
                self.format = "csv"
                print(f"[pylectra.io] parquet write failed ({e}); wrote CSV: {csv_path}")
        else:
            df.to_csv(self.path, index=False)
        self._rows.clear()
        return self.path
