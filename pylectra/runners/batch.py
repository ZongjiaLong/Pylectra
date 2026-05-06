"""Batch sample-generation runner.

The runner iterates ``cfg.scenarios.count`` times.  Each iteration:

1. Deep-copies the base case.
2. Applies each registered :class:`ScenarioGenerator` in declaration order.
3. Calls the :class:`SingleRunner` to simulate.
4. Runs the filter chain.
5. If accepted (or ``keep_failed=True``), writes the time series via the
   sample writer and appends a row to the metadata table.

Parallelism is controlled by ``cfg.output.parallel`` — set ``n_jobs > 1`` (or
``"auto"`` in YAML) to use ``joblib.Parallel`` for process-level batching.
Per-sample reproducibility is preserved: each sample ``i`` uses an RNG
seeded with ``cfg.scenarios.seed + i`` so the result is independent of
worker count and ordering.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Tuple

import numpy as np

from pylectra import registry
from pylectra.config import ExperimentConfig
from pylectra.core.case import NetworkCase
from pylectra.core.result import SimulationResult
from pylectra.interfaces.filter import FilterDecision, SampleFilter
from pylectra.interfaces.scenario import Scenario, ScenarioGenerator
from pylectra.io.hdf5_writer import HDF5SampleWriter, NPZSampleWriter
from pylectra.io.metadata_writer import MetadataWriter
from pylectra.runners.single import SingleRunner, _solver_class, _engine_kind, _build_fault


@dataclass
class BatchRunStats:
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    pf_failed: int = 0
    rejections_by_filter: dict = field(default_factory=dict)
    elapsed_sec: float = 0.0


def _build_scenario_generators(cfg: ExperimentConfig) -> List[ScenarioGenerator]:
    gens = []
    for spec in cfg.scenarios.generators:
        cls = registry.get("scenario", spec.kind)
        gens.append(cls(**spec.params))
    if not gens:
        # Default: a noop scenario so the loop still runs ``count`` times.
        cls = registry.get("scenario", "noop")
        gens.append(cls())
    return gens


def _build_filters(cfg: ExperimentConfig) -> List[SampleFilter]:
    out = []
    for spec in cfg.filters:
        cls = registry.get("filter", spec.kind)
        out.append(cls(**spec.params))
    return out


def _make_writer(cfg: ExperimentConfig):
    fmt = cfg.output.format.lower()
    if fmt == "hdf5":
        return HDF5SampleWriter(cfg.output.directory)
    if fmt == "npz":
        return NPZSampleWriter(cfg.output.directory)
    raise ValueError(f"unknown output.format {fmt!r}")


def _make_metadata_writer(cfg: ExperimentConfig) -> MetadataWriter:
    fmt = cfg.output.metadata.lower()
    suffix = ".parquet" if fmt == "parquet" else ".csv"
    return MetadataWriter(Path(cfg.output.directory) / f"metadata{suffix}", format=fmt)


def _apply_scenarios(
    base_case: NetworkCase,
    generators: List[ScenarioGenerator],
    rng: np.random.Generator,
) -> Scenario:
    """Compose all scenario generators on the same base case."""
    scen = generators[0].generate(base_case, rng)
    for g in generators[1:]:
        nxt = g.generate(scen.case, rng)
        # Carry forward earlier metadata.
        nxt.metadata = {**scen.metadata, **nxt.metadata}
        scen = nxt
    return scen


def _run_filters(
    filters: List[SampleFilter],
    result: SimulationResult,
    scenario: Scenario,
    case: NetworkCase,
):
    """Return (overall_pass, first_rejection_or_None, all_decisions)."""
    decisions = []
    rejection = None
    for f in filters:
        d = f.judge(result, scenario, case)
        decisions.append((f, d))
        if not d.passed and rejection is None:
            rejection = (f, d)
    return rejection is None, rejection, decisions


# --------------------------------------------------------------------------
# Worker function — executed in subprocesses by joblib.  Top-level so loky
# can pickle it; takes everything it needs by value.
# --------------------------------------------------------------------------
def _process_one_sample(
    i: int,
    cfg: ExperimentConfig,
    base_case_mpc: dict,
    seed: int,
    writer_dir: str,
    writer_format: str,
    keep_failed: bool,
) -> dict:
    """Run + filter + persist one sample.  Returns a metadata row + status."""
    # Each subprocess re-imports pylectra (registry is process-local).
    import pylectra  # noqa: F401  — populates plugin registry

    # Local imports keep the worker self-contained for pickling.
    from pylectra.core.case import NetworkCase as _NC
    from pylectra.runners.single import SingleRunner as _SR
    from pylectra.io.hdf5_writer import HDF5SampleWriter as _HW, NPZSampleWriter as _NW

    base_case = _NC(base_case_mpc)
    rng = np.random.default_rng(seed)
    sample_id = f"sample_{i:06d}"

    generators = _build_scenario_generators(cfg)
    filters = _build_filters(cfg)
    single = _SR(cfg)
    writer = _HW(writer_dir) if writer_format == "hdf5" else _NW(writer_dir)

    scenario = _apply_scenarios(base_case, generators, rng)
    run_out = single.run(scenario)
    res = run_out.result
    passed, rejection, decisions = _run_filters(
        filters, res, scenario, run_out.case
    )

    row = {
        "sample_id": sample_id,
        "passed": passed,
        "rejected_by": "" if passed else rejection[0].__plugin_name__,
        "rejected_reason": "" if passed else rejection[1].reason,
        "simulation_time": float(res.simulation_time),
        "pf_success": bool(res.pf_success),
        "n_steps": int(res.n_steps),
        "n_bus": int(res.n_bus),
        "n_gen": int(res.n_gen),
    }
    for f, d in decisions:
        if d.metric is not None:
            row[f"filter_{f.__plugin_name__}_metric"] = d.metric
    for k, v in (scenario.metadata or {}).items():
        row[f"meta:{k}"] = v if isinstance(v, (int, float, str, bool)) else repr(v)

    if passed or keep_failed:
        writer.write(sample_id, res)
        ext = "h5" if writer_format == "hdf5" else "npz"
        row["sample_path"] = str(Path(writer_dir) / f"{sample_id}.{ext}")
    else:
        row["sample_path"] = ""

    return {
        "i": i,
        "sample_id": sample_id,
        "passed": passed,
        "pf_success": bool(res.pf_success),
        "rejected_by": "" if passed else rejection[0].__plugin_name__,
        "rejected_reason": "" if passed else rejection[1].reason,
        "row": row,
    }


# --------------------------------------------------------------------------
# GPU fast-path
# --------------------------------------------------------------------------

def _run_batched_torch(
    cfg: ExperimentConfig,
    base_case: NetworkCase,
    count: int,
    seed_base: int,
    writer_dir: str,
    writer_format: str,
    keep_failed: bool,
    verbose: int,
) -> List[dict]:
    """Run ``count`` samples in one batched torch pass + filters/writers.

    Returns rows in the same shape as :func:`_process_one_sample`.
    """
    from pylectra.core.system import DynamicSystem
    from pylectra.core.result import SimulationResult
    from pylectra.engine.torch_engine_batched import (
        BatchedRunSpec, BatchedTorchIntegrationLoop)

    # 1) Build B per-sample scenarios on host (cheap, deterministic via
    #    per-sample seed).
    generators = _build_scenario_generators(cfg)
    filters = _build_filters(cfg)
    scenarios: List[Any] = []
    perturbed_cases: List[NetworkCase] = []
    for i in range(count):
        rng = np.random.default_rng(seed_base + i)
        scen = _apply_scenarios(base_case, generators, rng)
        scenarios.append(scen)
        perturbed_cases.append(scen.case)

    # 2) Resolve solver options + fault → events.
    fault = _build_fault(cfg)
    ev_arg = fault.to_loadevents_dict() if fault is not None else None
    solver_opts = dict(cfg.solver.options or {})

    # The DynamicSystem dyn-dict comes from the base case; per-sample
    # scenarios only mutate bus/branch (load + line outage), not machine
    # constants, so the same dyn-dict is correct for the whole batch.
    sys0 = DynamicSystem.from_legacy(base_case, cfg.case_dyn)
    dyn_dict = sys0.to_dyn_dict()

    # 3) Build BatchedRunSpec from solver options.
    spec = BatchedRunSpec(
        batch_size=count,
        fixed_step=float(solver_opts.get("step_size",
                          solver_opts.get("max_step", 1e-3))),
        dense_n=int(solver_opts.get("dense_n", 200)),
        device_pref=str(solver_opts.get("device", "auto")),
        torch_dtype=str(solver_opts.get("torch_dtype", "float64")),
    )

    if verbose:
        print(f"[batch] GPU fast-path: B={count}, device={spec.device_pref}, "
              f"dtype={spec.torch_dtype}, step={spec.fixed_step}")

    loop = BatchedTorchIntegrationLoop(
        casefile_pf=base_case.mpc,
        casefile_dyn=dyn_dict,
        casefile_ev=ev_arg,
        spec=spec,
        output=verbose,
    )
    eng_results = loop.run_perturbed(perturbed_cases)

    # 4) Run filters + writer on each sample.
    writer = (HDF5SampleWriter(writer_dir) if writer_format == "hdf5"
              else NPZSampleWriter(writer_dir))

    rows: List[dict] = []
    for i, (scen, eng_res) in enumerate(zip(scenarios, eng_results)):
        sample_id = f"sample_{i:06d}"
        if not eng_res.success:
            res = SimulationResult.failed_powerflow(
                n_bus=base_case.n_bus,
                n_gen=int(eng_res.n_gen if hasattr(eng_res, "n_gen") else 0),
                reason=str(getattr(eng_res, "message", "engine failure")),
            )
        else:
            res = SimulationResult.from_legacy_dict(eng_res.as_dict())

        passed, rejection, decisions = _run_filters(
            filters, res, scen, scen.case
        )

        row = {
            "sample_id": sample_id,
            "passed": passed,
            "rejected_by": "" if passed else rejection[0].__plugin_name__,
            "rejected_reason": "" if passed else rejection[1].reason,
            "simulation_time": float(res.simulation_time),
            "pf_success": bool(res.pf_success),
            "n_steps": int(res.n_steps),
            "n_bus": int(res.n_bus),
            "n_gen": int(res.n_gen),
        }
        for f, d in decisions:
            if d.metric is not None:
                row[f"filter_{f.__plugin_name__}_metric"] = d.metric
        for k, v in (scen.metadata or {}).items():
            row[f"meta:{k}"] = (v if isinstance(v, (int, float, str, bool))
                                else repr(v))

        if passed or keep_failed:
            writer.write(sample_id, res)
            ext = "h5" if writer_format == "hdf5" else "npz"
            row["sample_path"] = str(Path(writer_dir) / f"{sample_id}.{ext}")
        else:
            row["sample_path"] = ""

        rows.append({
            "i": i,
            "sample_id": sample_id,
            "passed": passed,
            "pf_success": bool(res.pf_success),
            "rejected_by": "" if passed else rejection[0].__plugin_name__,
            "rejected_reason": "" if passed else rejection[1].reason,
            "row": row,
        })
    return rows


# --------------------------------------------------------------------------


class BatchRunner:
    """Generate ``cfg.scenarios.count`` filtered samples (serial or parallel)."""

    def __init__(self, cfg: ExperimentConfig):
        self.cfg = cfg
        self.meta = _make_metadata_writer(cfg)

    # ------------------------------------------------------------------
    def run(self) -> BatchRunStats:
        cfg = self.cfg
        stats = BatchRunStats()
        base_case = NetworkCase.load(cfg.case_pf)

        n_jobs = int(cfg.output.parallel.n_jobs)
        backend = cfg.output.parallel.backend
        verbose = int(cfg.verbose)
        directory = str(cfg.output.directory)
        # Make sure the output directory exists before any worker writes to it.
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
        # ---- GPU fast path ------------------------------------------------
        # Engine = torch + count > 1 → run all samples in one batched GPU
        # pass.  Falls back transparently on any unexpected failure.
        gpu_results = None
        if count > 1:
            try:
                solver_cls = _solver_class(cfg)
                if _engine_kind(solver_cls) == "torch":
                    gpu_results = _run_batched_torch(
                        cfg, base_case, count, seed_base,
                        directory, fmt, keep_failed, verbose,
                    )
            except Exception as e:
                if verbose:
                    print(f"[batch] GPU fast-path unavailable, "
                          f"falling back to joblib: {e}")
                gpu_results = None

        if gpu_results is not None:
            results = gpu_results
        elif n_jobs == 1 or count == 1:
            results = [_process_one_sample(*a) for a in worker_args]
        else:
            from joblib import Parallel, delayed

            results = Parallel(n_jobs=n_jobs, backend=backend,
                               verbose=10 if verbose >= 2 else 0)(
                delayed(_process_one_sample)(*a) for a in worker_args
            )

        # Aggregate in deterministic order so metadata.parquet rows are stable.
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
                msg = (f"[batch] {r['sample_id']}: {tag}"
                       + ("" if r["passed"]
                          else f" by {r['rejected_by']} — {r['rejected_reason']}"))
                print(msg)

        meta_path = self.meta.flush()
        stats.elapsed_sec = time.time() - t0
        if verbose:
            print(
                f"[batch] done: {stats.accepted}/{stats.total} accepted "
                f"({stats.rejected} rejected, {stats.pf_failed} PF-failed) in "
                f"{stats.elapsed_sec:.1f}s, n_jobs={n_jobs}. metadata: {meta_path}"
            )
        return stats
