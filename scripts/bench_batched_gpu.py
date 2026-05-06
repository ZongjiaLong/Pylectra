"""Phase 6 benchmark — batched GPU torch vs joblib scipy native.

Sweeps batch size B and reports samples/sec for two engines:

* ``batched-torch``  — one B-sample pass via
  :class:`pylectra.engine.torch_engine_batched.BatchedTorchIntegrationLoop`.
* ``scipy-joblib``   — B independent scipy_dop853 runs across joblib
  worker processes (the existing :class:`pylectra.runners.batch.BatchRunner`
  default path).

Usage
-----
    python scripts/bench_batched_gpu.py --batches 1,16,64,256,1024
    python scripts/bench_batched_gpu.py --device cpu --skip-scipy
    python scripts/bench_batched_gpu.py --device cuda --batches 64,256,1024

The script exercises the pylectra examples ``case39`` + bus-16 fault.
Per-sample perturbation = 3% load_perturb (seeded reproducibly).
"""
from __future__ import annotations

import argparse
import os
import time
from typing import List

import numpy as np

import pylectra  # noqa: F401  — populates plugin registry
from pylectra.core.case import NetworkCase
from pylectra.core.idx import PD, QD
from pylectra.faults.bus_fault import BusFault


SEED = 4242


def _make_perturbed_cases(n: int, sigma: float = 0.03) -> List[NetworkCase]:
    base = NetworkCase.load("case39")
    rng = np.random.default_rng(SEED)
    cases = []
    for _ in range(n):
        c = base.copy()
        f = np.clip(1.0 + rng.normal(0.0, sigma, c.bus.shape[0]),
                    1.0 - 3 * sigma, 1.0 + 3 * sigma)
        c.bus[:, PD] *= f
        c.bus[:, QD] *= f
        cases.append(c)
    return cases


def bench_batched_torch(B: int, *, device: str, dtype: str,
                        fixed_step: float, dense_n: int) -> float:
    """Returns wall-time seconds for one B-sample batched torch run."""
    from pylectra.engine.torch_engine_batched import (
        BatchedRunSpec, BatchedTorchIntegrationLoop)

    cases = _make_perturbed_cases(B)
    fault = BusFault(bus=16, t_fault=0.2, duration=0.05)
    ev_arg = fault.to_loadevents_dict()

    spec = BatchedRunSpec(
        batch_size=B, fixed_step=fixed_step, dense_n=dense_n,
        device_pref=device, torch_dtype=dtype,
    )
    loop = BatchedTorchIntegrationLoop(
        casefile_pf=cases[0].mpc, casefile_dyn="case39dyn",
        casefile_ev=ev_arg, spec=spec, output=0,
    )
    # Optional CUDA warmup so the first kernel launch isn't billed.
    if device == "cuda":
        try:
            import torch as _t
            _t.cuda.synchronize()
        except Exception:
            pass

    t0 = time.time()
    results = loop.run_perturbed(cases)
    if device == "cuda":
        try:
            import torch as _t
            _t.cuda.synchronize()
        except Exception:
            pass
    dt = time.time() - t0
    n_ok = sum(1 for r in results if r.success)
    if n_ok != B:
        print(f"  WARN: only {n_ok}/{B} batched runs succeeded")
    return dt


def bench_scipy_joblib(B: int, *, n_jobs: int) -> float:
    """Returns wall-time seconds for B sample-by-sample scipy_dop853 runs."""
    from pylectra.engine.loop import IntegrationLoop
    from pylectra import registry
    from joblib import Parallel, delayed

    cls = registry.get("ode_solver", "scipy_dop853")
    factory = cls.make_stepper

    fault = BusFault(bus=16, t_fault=0.2, duration=0.05)
    ev_arg = fault.to_loadevents_dict()
    cases = _make_perturbed_cases(B)
    mpcs = [c.mpc for c in cases]

    def _one(mpc):
        loop = IntegrationLoop(
            casefile_pf=mpc, casefile_dyn="case39dyn", casefile_ev=ev_arg,
            solver_factory=factory,
            solver_options={"rtol": 1e-7, "atol": 1e-9},
            output=0,
        )
        return loop.run().success

    t0 = time.time()
    if n_jobs == 1:
        oks = [_one(m) for m in mpcs]
    else:
        oks = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_one)(m) for m in mpcs
        )
    dt = time.time() - t0
    n_ok = sum(bool(x) for x in oks)
    if n_ok != B:
        print(f"  WARN: only {n_ok}/{B} scipy runs succeeded")
    return dt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batches", default="1,16,64,256",
                   help="comma-separated list of batch sizes")
    p.add_argument("--device", default="auto",
                   help="torch device preference (auto/cpu/cuda)")
    p.add_argument("--dtype", default="float64", choices=["float32", "float64"])
    p.add_argument("--step", type=float, default=1e-3, help="RK4 fixed step")
    p.add_argument("--dense-n", type=int, default=200)
    p.add_argument("--n-jobs", type=int, default=os.cpu_count() or 1,
                   help="joblib n_jobs for the scipy baseline")
    p.add_argument("--skip-scipy", action="store_true",
                   help="skip the joblib-scipy baseline (e.g. when "
                        "ranking torch alone)")
    args = p.parse_args()

    Bs = [int(x) for x in args.batches.split(",") if x.strip()]
    print(f"# batched-vs-scipy benchmark — case39 + bus16 fault")
    print(f"# device={args.device} dtype={args.dtype} step={args.step} "
          f"dense_n={args.dense_n} n_jobs={args.n_jobs}")
    print(f"# {'B':>6} {'torch[s]':>10} {'torch sps':>10} "
          f"{'scipy[s]':>10} {'scipy sps':>10} {'speedup':>8}")
    for B in Bs:
        t_torch = bench_batched_torch(B, device=args.device, dtype=args.dtype,
                                      fixed_step=args.step,
                                      dense_n=args.dense_n)
        sps_torch = B / t_torch
        if args.skip_scipy:
            print(f"  {B:>6} {t_torch:>10.2f} {sps_torch:>10.2f} "
                  f"{'-':>10} {'-':>10} {'-':>8}")
            continue
        t_scipy = bench_scipy_joblib(B, n_jobs=args.n_jobs)
        sps_scipy = B / t_scipy
        speedup = t_scipy / t_torch
        print(f"  {B:>6} {t_torch:>10.2f} {sps_torch:>10.2f} "
              f"{t_scipy:>10.2f} {sps_scipy:>10.2f} {speedup:>7.2f}x")


if __name__ == "__main__":
    main()
