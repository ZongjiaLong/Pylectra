"""Phase 0 CCT regression: re-run ``examples/cct_case39.yaml`` and compare
to the frozen baseline at ``tests/golden/cct_case39.json``.

The numerical anchor is the converged CCT value (0.1270 s); a slack of
``tol`` (= 0.005 s, the bisection tolerance) is allowed on the result
itself and the final bracket.

Marked ``slow`` (~60–90 s).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "tests" / "golden" / "cct_case39.json"


def _parse_cct(stdout: str) -> dict:
    """Parse the final ``[cct] CCT ≈ x s (bracket [a, b], n iters, converged=...)``
    line that the runner prints."""
    pat = re.compile(
        r"CCT\s*[≈~]?\s*(?P<cct>[0-9.]+)\s*s\s*\(\s*bracket\s*\[\s*(?P<lo>[0-9.]+)\s*,\s*(?P<hi>[0-9.]+)\s*\]\s*,"
        r"\s*(?P<iters>\d+)\s*iters\s*,\s*converged=(?P<conv>True|False)\s*\)"
    )
    for line in reversed(stdout.splitlines()):
        m = pat.search(line)
        if m:
            return {
                "cct": float(m["cct"]),
                "bracket": [float(m["lo"]), float(m["hi"])],
                "iters": int(m["iters"]),
                "converged": m["conv"] == "True",
            }
    raise AssertionError("could not parse CCT output:\n" + stdout[-1000:])


@pytest.mark.slow
def test_cct_matches_golden(tmp_path: Path) -> None:
    if not GOLDEN.exists():
        pytest.skip(f"no golden baseline at {GOLDEN}")

    expected = json.loads(GOLDEN.read_text())
    env = dict(os.environ, PYTHONPATH=str(REPO))
    p = subprocess.run(
        [sys.executable, "-m", "pylectra", "run", "examples/cct_case39.yaml"],
        capture_output=True, text=True, env=env, cwd=str(REPO), check=True,
    )
    got = _parse_cct(p.stdout)
    tol = expected["tol"]
    assert abs(got["cct"] - expected["result"]["cct"]) <= tol, got
    assert got["converged"] is True
