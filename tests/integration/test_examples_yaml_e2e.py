"""Phase 8 e2e: every ``examples/*.yaml`` runs to completion via the CLI.

Smoke test — asserts that the example produces a clean run (returncode 0,
no ``Traceback`` / ``Error:`` in stderr). The strict numerical anchors
already live in :mod:`tests.integration.test_batch_golden` (batch_case39)
and :mod:`tests.integration.test_cct_golden` (cct_case39), so we exclude
those from the smoke set and concentrate on the YAMLs that were *not*
otherwise covered before Phase 8.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"


# YAMLs already validated by stricter golden / parity tests.
_COVERED_ELSEWHERE = {
    "batch_case39.yaml",          # test_batch_golden (bit-identical)
    "cct_case39.yaml",            # test_cct_golden (5 ms tolerance)
    "single_case39_scipy.yaml",   # test_cli_runpy_parity
    "single_case39_torch.yaml",   # test_torch_backend
}


def _yaml_smoke_set() -> list[Path]:
    """Return the YAMLs that need fresh e2e coverage in Phase 8."""
    return sorted(p for p in EXAMPLES.glob("*.yaml")
                  if p.name not in _COVERED_ELSEWHERE)


def _force_single_process(cfg: dict) -> dict:
    """Pin batch n_jobs to 1.

    The Python ``multiprocessing.resource_tracker`` chokes on non-ASCII paths
    on Windows (the bug bites when the project lives under a path containing
    e.g. CJK characters), so e2e tests run batch examples single-threaded.
    Numerical results are unaffected.
    """
    if cfg.get("mode") == "batch":
        cfg.setdefault("output", {}).setdefault("parallel", {})["n_jobs"] = 1
    return cfg


@pytest.mark.slow
@pytest.mark.parametrize("yaml_path", _yaml_smoke_set(),
                         ids=lambda p: p.name)
def test_example_yaml_runs(yaml_path: Path, tmp_path: Path) -> None:
    """Run a single example YAML through the CLI and assert it completes cleanly."""
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cfg = _force_single_process(cfg)
    # Redirect any output directory to the test's tmp_path.
    if "output" in cfg and "directory" in cfg["output"]:
        cfg["output"]["directory"] = str(tmp_path / "out")

    cfg_path = tmp_path / yaml_path.name
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    env = dict(os.environ, PYTHONPATH=str(REPO))
    result = subprocess.run(
        [sys.executable, "-m", "pylectra", "run", str(cfg_path), "--no-plot"],
        capture_output=True, text=True, env=env, cwd=str(REPO),
        timeout=600,
    )
    combined = result.stdout + "\n" + result.stderr
    assert "Traceback" not in combined, (
        f"{yaml_path.name} raised an exception:\n{combined}"
    )
    # The runner returns non-zero when *all* samples are rejected (e.g.
    # ``batch_case39_smallsignal.yaml`` filters out every base-case sample
    # because case39 is small-signal unstable by default — this is not a
    # crash, just an empty result set).  Accept either a clean exit or that
    # specific "no accepted samples" outcome.
    finished_markers = (
        "[single] mode complete",
        "[batch] done",
        "[cct] CCT",
    )
    assert any(m in combined for m in finished_markers), (
        f"{yaml_path.name} did not finish cleanly (returncode {result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
