"""Command-line interface for ``pylectra``.

Usage::

    python -m pylectra run <config.yaml>            # dispatch to single/batch/cct mode
    python -m pylectra info                         # list registered plugins
    python -m pylectra info --category generator
    python -m pylectra plot <yaml-or-h5-or-dir>     # Nature-grade plots (Phase 2b)
        --type rotor_angles --output rotor.pdf
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pylectra import registry


def _cmd_run(args: argparse.Namespace) -> int:
    from pylectra.config import ExperimentConfig

    cfg = ExperimentConfig.from_yaml(args.config)
    if args.verbose is not None:
        cfg.verbose = args.verbose
    if args.no_plot:
        cfg.plot = False

    mode = cfg.mode
    if mode == "single":
        from pylectra.runners.single import SingleRunner
        runner = SingleRunner(cfg)
        out = runner.run()
        res = out.result
        print(
            f"[single] mode complete: pf_success={res.pf_success} "
            f"n_steps={res.n_steps} simulation_time={res.simulation_time:.2f}s"
        )
        if res.small_signal is not None:
            import math
            ss = res.small_signal
            verdict = "stable" if ss.is_stable else "UNSTABLE"
            margin_str = f"{ss.stability_margin:.4g}"
            # Find least-damped ratio (ignoring NaN).
            valid_zeta = [z for z in ss.damping_ratios if not math.isnan(z)]
            zeta_str = f"{min(valid_zeta):.3f}" if valid_zeta else "n/a"
            print(f"  small-signal: {verdict}  margin={margin_str}  "
                  f"least-damped ζ={zeta_str}")
        return 0 if res.pf_success else 2

    if mode == "batch":
        from pylectra.runners.batch import BatchRunner
        runner = BatchRunner(cfg)
        stats = runner.run()
        print(
            f"[batch] {stats.accepted}/{stats.total} accepted "
            f"({stats.rejected} rejected, {stats.pf_failed} PF-failed) in "
            f"{stats.elapsed_sec:.1f}s"
        )
        return 0 if stats.accepted > 0 else 3

    if mode == "batch_pf":
        from pylectra.runners.batch_pf import BatchPFRunner
        runner = BatchPFRunner(cfg)
        stats = runner.run()
        print(
            f"[batch_pf] {stats.accepted}/{stats.total} accepted "
            f"({stats.rejected} rejected, {stats.pf_failed} PF-failed) in "
            f"{stats.elapsed_sec:.2f}s"
        )
        return 0 if stats.accepted > 0 else 3

    if mode == "cct":
        from pylectra.runners.cct import CCTRunner
        runner = CCTRunner(cfg)
        result = runner.run()
        print(
            f"[cct] CCT ≈ {result.cct:.4f} s "
            f"(bracket [{result.bracket_low:.4f}, {result.bracket_high:.4f}], "
            f"{result.iterations} iters, "
            f"converged={result.converged}{', note=' + result.note if result.note else ''})"
        )
        return 0 if result.converged else 4

    print(f"unknown mode: {mode!r}", file=sys.stderr)
    return 1


def _cmd_info(args: argparse.Namespace) -> int:
    if args.hardware:
        from pylectra.hardware import format_summary

        print(format_summary())
        if args.category is None:
            return 0
    plugins = registry.list_plugins(args.category)
    for cat, names in plugins.items():
        print(f"{cat}:")
        for n in names:
            cls = registry.get(cat, n)
            doc = (cls.__doc__ or "").splitlines()[0] if cls.__doc__ else ""
            print(f"  - {n:<30}  {doc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Importing pylectra populates the registry.
    import pylectra  # noqa: F401

    parser = argparse.ArgumentParser(prog="pylectra", description="Power Dynamic Simulator (refactored)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run an experiment from a YAML config")
    p_run.add_argument("config", type=Path, help="path to YAML config file")
    p_run.add_argument("-v", "--verbose", type=int, default=None, help="override verbosity (0–2)")
    p_run.add_argument("--no-plot", action="store_true", help="disable end-of-run plotting")
    p_run.set_defaults(func=_cmd_run)

    p_info = sub.add_parser("info", help="list registered plugins")
    p_info.add_argument("--category", default=None, help="restrict to one category")
    p_info.add_argument("--hardware", action="store_true",
                        help="also print hardware summary (CPU, CUDA, recommended n_jobs)")
    p_info.set_defaults(func=_cmd_info)

    # ---- plot subcommand (Phase 2b) -----------------------------------
    from pylectra.plotting import list_plot_kinds  # lazy import for fast startup

    p_plot = sub.add_parser(
        "plot",
        help="render Highest-grade plots from a yaml config, sample file or batch dir",
    )
    p_plot.add_argument("source", type=Path,
                        help="YAML config / .h5 / .npz sample / batch sample dir")
    p_plot.add_argument("--type", "-t", required=True,
                        choices=list_plot_kinds(),
                        help="which plot to produce")
    p_plot.add_argument("--output", "-o", required=True, type=Path,
                        help="output figure path (extension picks format)")
    p_plot.add_argument("--format", default=None,
                        help="comma-separated extra formats, e.g. 'pdf,svg'")
    p_plot.add_argument("--option", "-O", action="append", default=[],
                        metavar="KEY=VAL",
                        help=("extra plot kwargs as KEY=VAL pairs "
                              "(repeatable; values JSON-decoded if possible)"))
    p_plot.set_defaults(func=_cmd_plot)

    args = parser.parse_args(argv)
    return int(args.func(args))


def _parse_kv_options(items: list[str]) -> dict:
    out: dict = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--option must be KEY=VAL, got {item!r}")
        k, _, v = item.partition("=")
        try:
            out[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            out[k.strip()] = v
    return out


def _cmd_plot(args: argparse.Namespace) -> int:
    from pylectra.plotting import render_plot

    formats = None
    if args.format:
        formats = [f.strip().lstrip(".") for f in args.format.split(",") if f.strip()]
    plot_kwargs = _parse_kv_options(args.option)

    saved = render_plot(
        kind=args.type,
        source=args.source,
        output=args.output,
        formats=formats,
        plot_kwargs=plot_kwargs,
    )
    for p in saved:
        print(f"[plot] wrote {p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
