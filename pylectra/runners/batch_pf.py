"""Batch power-flow-only runner.

Iterates ``cfg.scenarios.count`` times, applies the scenario generators,
runs *just* the power flow, optionally judges sample filters on the
post-PF snapshot, and persists the snapshot to disk.  No dynamic data,
no time-domain integration.

Per-sample reproducibility mirrors :class:`BatchRunner`: sample ``i``
uses an RNG seeded with ``cfg.scenarios.seed + i`` so results are
independent of worker count and ordering.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np

from pylectra import registry
from pylectra.config import ExperimentConfig
from pylectra.core.case import NetworkCase
from pylectra.io.hdf5_writer import HDF5PFSnapshotWriter, NPZPFSnapshotWriter
from pylectra.runners._pf_snapshot import (
    PowerFlowSnapshot, from_solved_case, to_simulation_result,
)
from pylectra.runners.batch import (
    _apply_scenarios,
    _build_filters,
    _build_scenario_generators,
    _make_metadata_writer,
    _run_filters,
)


@dataclass
class BatchPFRunStats:
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    pf_failed: int = 0
    rejections_by_filter: dict = field(default_factory=dict)
    elapsed_sec: float = 0.0


def _make_pf_writer(directory: str, fmt: str):
    fmt = fmt.lower()
    if fmt == "hdf5":
        return HDF5PFSnapshotWriter(directory)
    if fmt == "npz":
        return NPZPFSnapshotWriter(directory)
    raise ValueError(f"unknown output.format {fmt!r}")


def _solve_pf(cfg: ExperimentConfig, case: NetworkCase) -> tuple[NetworkCase, float]:
    """Run the configured PF solver on ``case`` (mutates and returns it)."""
    pf_cls = registry.get("power_flow", cfg.power_flow.kind)
    solver = pf_cls(**cfg.power_flow.params)
    t0 = time.perf_counter()
    case = solver.solve(case, dict(cfg.power_flow.options or {}))
    et = time.perf_counter() - t0
    return case, et


def _process_one_pf_sample(
    i: int,
    cfg: ExperimentConfig,
    base_case_mpc: dict,
    seed: int,
    writer_dir: str,
    writer_format: str,
    keep_failed: bool,
) -> dict:
    """Run + filter + persist one PF-only sample."""
    import pylectra  # noqa: F401  — populates plugin registry

    from pylectra.core.case import NetworkCase as _NC

    base_case = _NC(base_case_mpc)
    rng = np.random.default_rng(seed)
    sample_id = f"sample_{i:06d}"

    generators = _build_scenario_generators(cfg)
    filters = _build_filters(cfg)
    writer = _make_pf_writer(writer_dir, writer_format)

    scenario = _apply_scenarios(base_case, generators, rng)
    case, et = _solve_pf(cfg, scenario.case)
    snap = from_solved_case(case, et)
    res = to_simulation_result(snap)
    passed, rejection, decisions = _run_filters(filters, res, scenario, case)

    row = {
        "sample_id": sample_id,
        "passed": passed,
        "rejected_by": "" if passed else rejection[0].__plugin_name__,
        "rejected_reason": "" if passed else rejection[1].reason,
        "simulation_time": float(snap.et),
        "pf_success": bool(snap.success),
        "n_steps": 1 if snap.success else 0,
        "n_bus": int(snap.n_bus),
        "n_gen": int(snap.n_gen),
    }
    for f, d in decisions:
        if d.metric is not None:
            row[f"filter_{f.__plugin_name__}_metric"] = d.metric
    for k, v in (scenario.metadata or {}).items():
        row[f"meta:{k}"] = v if isinstance(v, (int, float, str, bool)) else repr(v)

    if (passed or keep_failed) and snap.success:
        writer.write(sample_id, snap)
        ext = "h5" if writer_format == "hdf5" else "npz"
        row["sample_path"] = str(Path(writer_dir) / f"{sample_id}.{ext}")
    elif (passed or keep_failed) and not snap.success:
        # PF didn't converge — still record but no file content to write.
        row["sample_path"] = ""
    else:
        row["sample_path"] = ""

    return {
        "i": i,
        "sample_id": sample_id,
        "passed": passed,
        "pf_success": bool(snap.success),
        "rejected_by": "" if passed else rejection[0].__plugin_name__,
        "rejected_reason": "" if passed else rejection[1].reason,
        "row": row,
    }


class BatchPFRunner:
    """Generate ``cfg.scenarios.count`` PF-only snapshots (serial or parallel)."""

    def __init__(self, cfg: ExperimentConfig):
        self.cfg = cfg
        self.meta = _make_metadata_writer(cfg)

    def run(self) -> BatchPFRunStats:
        cfg = self.cfg
        stats = BatchPFRunStats()
        base_case = NetworkCase.load(cfg.case_pf)

        n_jobs = int(cfg.output.parallel.n_jobs)
        backend = cfg.output.parallel.backend
        verbose = int(cfg.verbose)
        directory = str(cfg.output.directory)
        Path(directory).mkdir(parents=True, exist_ok=True)
        fmt = cfg.output.format.lower()
        keep_failed = bool(cfg.output.keep_failed)
        seed_base = int(cfg.scenarios.seed)
        count = int(cfg.scenarios.count)
        base_mpc = base_case.mpc

        worker_args = [
            (i, cfg, base_mpc, seed_base + i, directory, fmt, keep_failed)
            for i in range(count)
        ]

        t0 = time.time()
        if n_jobs == 1 or count == 1:
            results = [_process_one_pf_sample(*a) for a in worker_args]
        else:
            from joblib import Parallel, delayed

            results = Parallel(n_jobs=n_jobs, backend=backend,
                               verbose=10 if verbose >= 2 else 0)(
                delayed(_process_one_pf_sample)(*a) for a in worker_args
            )

        results.sort(key=lambda r: r["i"])
        for r in results:
            stats.total += 1
            if not r["pf_success"]:
                stats.pf_failed += 1
            if r["passed"]:
                stats.accepted += 1
            else:
                stats.rejected += 1
                rb = r["rejected_by"] or "unknown"
                stats.rejections_by_filter[rb] = (
                    stats.rejections_by_filter.get(rb, 0) + 1
                )
            self.meta.add(r["row"])
            if verbose:
                tag = "ACCEPT" if r["passed"] else "REJECT"
                msg = (f"[batch_pf] {r['sample_id']}: {tag}"
                       + ("" if r["passed"]
                          else f" by {r['rejected_by']} — {r['rejected_reason']}"))
                print(msg)

        meta_path = self.meta.flush()
        stats.elapsed_sec = time.time() - t0
        if verbose:
            print(
                f"[batch_pf] done: {stats.accepted}/{stats.total} accepted "
                f"({stats.rejected} rejected, {stats.pf_failed} PF-failed) in "
                f"{stats.elapsed_sec:.2f}s, n_jobs={n_jobs}. metadata: {meta_path}"
            )
        return stats
