"""Lint: ensure ``pylectra/`` and ``tests/`` are free of legacy imports.

After Phase 9 the vendored MATLAB-port directory ``pylectra/_legacy/`` has
been deleted entirely.  This lint enforces that:

1. ``pylectra/_legacy/`` does not exist on disk.
2. No file under ``pylectra/`` or ``tests/`` imports ``pylectra._legacy.X``
   or any un-prefixed legacy package name (``PowerFlow``, ``Models``,
   ``Auxiliary``, ``Solvers``, ``rundyn``, ``Cases``, ``TimedomainSim``).

Re-introducing legacy coupling fails this lint and blocks the PR.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PDS = REPO / "pylectra"
TESTS = REPO / "tests"

LEGACY_PKGS = (
    "PowerFlow", "Models", "Solvers", "Auxiliary",
    "Cases", "rundyn", "TimedomainSim",
)
_PATTERN = re.compile(
    rf"^\s*(?:from|import)\s+(?:{'|'.join(LEGACY_PKGS)})\b", re.MULTILINE
)
_LEGACY_DOTTED = re.compile(r"\bpylectra\._legacy\b")


# This lint module references ``pylectra._legacy`` and the legacy package
# names in its own pattern definitions, so skip itself when scanning.
_SELF = Path(__file__).resolve()


def _scan(root: Path) -> dict[str, list[str]]:
    """Return ``{relative-path: [reasons]}`` for files containing legacy refs."""
    out: dict[str, list[str]] = {}
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if p.resolve() == _SELF:
            continue
        text = p.read_text(encoding="utf-8")
        reasons: list[str] = []
        if _PATTERN.search(text):
            reasons.append("un-prefixed legacy import")
        if _LEGACY_DOTTED.search(text):
            reasons.append("pylectra._legacy reference")
        if reasons:
            out[str(p.relative_to(REPO)).replace("\\", "/")] = reasons
    return out


def test_legacy_directory_is_gone():
    """``pylectra/_legacy/`` must not exist after Phase 9."""
    assert not (PDS / "_legacy").exists(), (
        "pylectra/_legacy/ should have been removed in Phase 9 — found it on disk"
    )


def test_no_legacy_imports_in_pylectra():
    offenders = _scan(PDS)
    assert not offenders, (
        "Legacy imports found in pylectra/. Phase 9 lint expects zero "
        f"references:\n  {offenders}"
    )


def test_no_legacy_imports_in_tests():
    offenders = _scan(TESTS)
    assert not offenders, (
        "Legacy imports found in tests/. After Phase 9 the parity tests "
        f"should have been deleted or fixture-ised:\n  {offenders}"
    )
