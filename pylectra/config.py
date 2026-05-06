"""YAML-backed configuration for ``pylectra`` runs.

A configuration file describes one experiment.  The top-level fields are::

    mode: single | batch | cct
    case_pf: case39                # name (string) or path
    case_dyn: case39dyn
    fault: { kind: bus_fault, params: { bus: 16, t_fault: 0.2, duration: 0.05 } }
    solver: { kind: modified_euler, options: { method: 1 } }
    power_flow: { kind: newton, options: {} }
    scenarios:
      count: 100
      seed: 42
      generators:
        - { kind: load_perturb, params: { sigma_pct: 5.0 } }
        - { kind: line_outage, params: { n_outages: 1, prob: 0.5 } }
    filters:
      - { kind: pf_converged }
      - { kind: voltage_range, params: { vmin: 0.85, vmax: 1.15 } }
      - { kind: angle_stability, params: { max_dev_deg: 180 } }
    output:
      directory: ./samples
      format: hdf5            # or 'npz'
      metadata: parquet       # or 'csv'
    cct:
      bus: 16
      t_fault: 0.2
      low: 0.0
      high: 0.5
      tol: 0.005

Sub-trees that don't apply to the chosen mode are simply ignored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# --------------------------------------------------------------------- typed leaf nodes

@dataclass
class PluginSpec:
    """Reference to a registered plugin (``kind``) plus its constructor params."""

    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_obj(cls, obj: Any) -> "PluginSpec":
        if obj is None:
            raise ValueError("plugin spec missing")
        if isinstance(obj, str):
            return cls(kind=obj)
        if not isinstance(obj, dict):
            raise TypeError(f"plugin spec must be a string or dict, got {type(obj)}")
        return cls(
            kind=str(obj["kind"]),
            params=dict(obj.get("params") or {}),
            options=dict(obj.get("options") or {}),
        )


@dataclass
class ScenariosConfig:
    count: int = 1
    seed: int = 0
    generators: List[PluginSpec] = field(default_factory=list)


@dataclass
class ParallelConfig:
    """Process-level parallelism settings (joblib backend)."""

    n_jobs: int = 1               # 1 = serial, -1 = all CPUs, "auto" → recommend
    backend: str = "loky"         # "loky" / "multiprocessing" / "threading"
    batch_size: int = 1           # joblib batch_size; 1 keeps things simple


@dataclass
class OutputConfig:
    directory: Path = Path("./samples")
    format: str = "hdf5"           # 'hdf5' or 'npz'
    metadata: str = "parquet"      # 'parquet' or 'csv'
    keep_failed: bool = False      # also persist filter-rejected samples
    parallel: ParallelConfig = field(default_factory=ParallelConfig)


@dataclass
class CCTConfig:
    """Critical clearing time bisection settings."""

    bus: int = 1
    t_fault: float = 0.2
    low: float = 0.0
    high: float = 0.5
    tol: float = 0.005
    max_iter: int = 25
    stability_filter: PluginSpec = field(
        default_factory=lambda: PluginSpec(
            kind="angle_stability",
            params={"max_dev_deg": 180.0},
        )
    )


@dataclass
class ExperimentConfig:
    """Top-level experiment configuration."""

    mode: str = "single"           # 'single' | 'batch' | 'batch_pf' | 'cct'
    case_pf: str = "case39"
    case_dyn: str = "case39dyn"
    fault: Optional[PluginSpec] = None
    solver: PluginSpec = field(
        default_factory=lambda: PluginSpec(kind="modified_euler")
    )
    power_flow: PluginSpec = field(default_factory=lambda: PluginSpec(kind="newton"))
    scenarios: ScenariosConfig = field(default_factory=ScenariosConfig)
    filters: List[PluginSpec] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
    cct: CCTConfig = field(default_factory=CCTConfig)
    verbose: int = 1
    plot: bool = True              # passed to legacy rundyn (skip on batch by default)
    # Optional small-signal stability analysis (runs after power flow / equilibrium init).
    # Set to a PluginSpec to enable; None means skip.
    small_signal: Optional[PluginSpec] = None
    # When True, skip time-domain ODE integration after the optional small-signal step.
    skip_integration: bool = False

    # ----------------------------- loaders ---------------------------------

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExperimentConfig":
        cfg = cls(
            mode=str(d.get("mode", "single")),
            case_pf=str(d.get("case_pf", "case39")),
            case_dyn=str(d.get("case_dyn", "case39dyn")),
            verbose=int(d.get("verbose", 1)),
            plot=bool(d.get("plot", d.get("mode", "single") == "single")),
        )
        if "fault" in d and d["fault"] is not None:
            cfg.fault = PluginSpec.from_obj(d["fault"])
        if "solver" in d and d["solver"] is not None:
            cfg.solver = PluginSpec.from_obj(d["solver"])
        if "power_flow" in d and d["power_flow"] is not None:
            cfg.power_flow = PluginSpec.from_obj(d["power_flow"])
        if "scenarios" in d and d["scenarios"] is not None:
            sc = d["scenarios"]
            cfg.scenarios = ScenariosConfig(
                count=int(sc.get("count", 1)),
                seed=int(sc.get("seed", 0)),
                generators=[PluginSpec.from_obj(g) for g in (sc.get("generators") or [])],
            )
        if "filters" in d and d["filters"] is not None:
            cfg.filters = [PluginSpec.from_obj(f) for f in d["filters"]]
        if "output" in d and d["output"] is not None:
            o = d["output"]
            par = o.get("parallel") or {}
            n_jobs_raw = par.get("n_jobs", 1)
            if isinstance(n_jobs_raw, str) and n_jobs_raw.lower() == "auto":
                from pylectra.hardware import recommend_n_jobs
                n_jobs_val = int(recommend_n_jobs("batch"))
            else:
                n_jobs_val = int(n_jobs_raw)
            cfg.output = OutputConfig(
                directory=Path(o.get("directory", "./samples")),
                format=str(o.get("format", "hdf5")),
                metadata=str(o.get("metadata", "parquet")),
                keep_failed=bool(o.get("keep_failed", False)),
                parallel=ParallelConfig(
                    n_jobs=n_jobs_val,
                    backend=str(par.get("backend", "loky")),
                    batch_size=int(par.get("batch_size", 1)),
                ),
            )
        if "cct" in d and d["cct"] is not None:
            c = d["cct"]
            cfg.cct = CCTConfig(
                bus=int(c.get("bus", 1)),
                t_fault=float(c.get("t_fault", 0.2)),
                low=float(c.get("low", 0.0)),
                high=float(c.get("high", 0.5)),
                tol=float(c.get("tol", 0.005)),
                max_iter=int(c.get("max_iter", 25)),
                stability_filter=PluginSpec.from_obj(
                    c.get("stability_filter")
                    or {"kind": "angle_stability", "params": {"max_dev_deg": 180.0}}
                ),
            )
        if "small_signal" in d and d["small_signal"] is not None:
            cfg.small_signal = PluginSpec.from_obj(d["small_signal"])
        cfg.skip_integration = bool(d.get("skip_integration", False))
        return cfg

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise TypeError(f"YAML config must be a mapping at top level, got {type(data)}")
        return cls.from_dict(data)
