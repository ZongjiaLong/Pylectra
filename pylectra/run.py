"""Programmatic entry point for pylectra experiments.

Use this when you want to run simulations from a Python script or Jupyter
notebook instead of the command line.

Examples
--------
Single run from a YAML file:

>>> from pylectra import run
>>> out = run("examples/single_case39.yaml")
>>> out.result.Time.shape

Override one field at call time (deep-merged into the YAML):

>>> out = run("examples/single_case39.yaml",
...           solver={"kind": "scipy_lsoda"},
...           verbose=2)

Pass a plain dict instead of a file path:

>>> out = run({"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
...            "power_flow": {"kind": "newton"},
...            "small_signal": {"kind": "finite_difference"},
...            "skip_integration": True})
>>> print(out.result.small_signal.is_stable)

Parameter sweep (list of configs):

>>> configs = [
...     {"mode": "single", "case_pf": "case39", "case_dyn": "case39dyn",
...      "fault": {"kind": "bus_fault",
...                "params": {"bus": b, "t_fault": 0.2, "duration": 0.05}}}
...     for b in (5, 10, 16, 22)
... ]
>>> results = run(configs)          # list of SingleRunResult
>>> for b, r in zip((5, 10, 16, 22), results):
...     print(b, r.result.max_angle_deviation_deg)
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Iterable, Union

import yaml

from pylectra.config import ExperimentConfig

ConfigLike = Union[str, Path, Dict[str, Any], ExperimentConfig]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_to_dict(config: ConfigLike) -> dict:
    """Convert any supported config form to a plain dict."""
    if isinstance(config, ExperimentConfig):
        from dataclasses import asdict
        return asdict(config)
    if isinstance(config, (str, Path)):
        with open(config, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(
                f"YAML root must be a mapping, got {type(data).__name__}"
            )
        return data
    if isinstance(config, dict):
        return copy.deepcopy(config)
    raise TypeError(
        f"config must be a str, Path, dict, or ExperimentConfig; "
        f"got {type(config).__name__}"
    )


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge *patch* into *base* (patch wins; dicts merged, not replaced).

    Lists in *patch* always replace the corresponding list in *base* entirely.
    """
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _dispatch(cfg: ExperimentConfig):
    """Route to the appropriate runner based on cfg.mode."""
    from pylectra.runners.single import SingleRunner
    from pylectra.runners.batch import BatchRunner
    from pylectra.runners.cct import CCTRunner

    if cfg.mode == "single":
        return SingleRunner(cfg).run()
    if cfg.mode == "batch":
        return BatchRunner(cfg).run()
    if cfg.mode == "batch_pf":
        from pylectra.runners.batch_pf import BatchPFRunner
        return BatchPFRunner(cfg).run()
    if cfg.mode == "cct":
        return CCTRunner(cfg).run()
    raise ValueError(
        f"unknown mode {cfg.mode!r}; expected 'single', 'batch', 'batch_pf', or 'cct'"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(config: Union[ConfigLike, Iterable[ConfigLike]], **overrides: Any):
    """Execute one or many pylectra experiments.

    Parameters
    ----------
    config :
        One of:

        * ``str`` or ``pathlib.Path`` — path to a YAML file.
        * ``dict`` — raw config mapping (same schema as YAML).
        * :class:`pylectra.config.ExperimentConfig` — pre-built config object.
        * ``list`` / ``tuple`` of any of the above — run each in sequence
          and return a list of results.

    **overrides :
        Top-level keys deep-merged into the loaded config dict *before* it
        is parsed.  Dict values are merged recursively; all other values
        replace the corresponding base value.

        Examples::

            # Replace a whole plugin spec
            run("config.yaml", solver={"kind": "scipy_lsoda"})

            # Merge into a nested dict (only options.rtol is changed)
            run("config.yaml", solver={"options": {"rtol": 1e-9}})

            # Add a small-signal stage to an existing config
            run("config.yaml",
                small_signal={"kind": "modal"},
                skip_integration=True)

            # Top-level scalar
            run("config.yaml", verbose=2)

    Returns
    -------
    SingleRunResult | BatchRunStats | CCTResult
        Depends on ``cfg.mode``.  When *config* is a list, returns a list
        of the corresponding result types.
    """
    # Sequence of configs → run each and collect.
    if isinstance(config, (list, tuple)):
        return [run(c, **overrides) for c in config]

    base = _load_to_dict(config)
    merged = _deep_merge(base, overrides) if overrides else base
    cfg = ExperimentConfig.from_dict(merged)
    return _dispatch(cfg)
