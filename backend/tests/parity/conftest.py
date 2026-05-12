"""Session-scoped parity fixtures + golden-baseline refresh tool.

Per RESEARCH §5.a: the full Iberia 868 pipeline takes ~45 s; running it once
per test keeps CI manageable. `tmp_path_factory.mktemp` returns a sandboxed
path under pytest's tmp tree, auto-cleaned at session end.

## Baseline refresh tool (Task 3b — Plan 01-03)

The golden fixtures at ``tests/fixtures/iberia_868/golden/`` are the parity
contract; they MUST only change via an explicit, reviewed commit (D-09 +
D-10). Two pytest CLI flags govern refresh:

* ``--refresh-baseline``  — replaces "assert equal" with "report a diff
  summary". Safe dry-run; never writes unless ``--confirm`` is also set.
* ``--confirm``  — required companion to ``--refresh-baseline``. Without
  it the tool only reports what *would* change. Prevents accidental
  clobbering of committed fixtures by a typo or stale shell history.

Determinism check: humans MUST verify by running the pipeline twice and
``diff -rq``-ing the outputs BEFORE invoking ``--refresh-baseline --confirm``.
The unit test ``backend/tests/unit/test_parity_refresh_tool.py`` exercises
the determinism contract on a tmpdir without touching the real golden.

Usage:

.. code-block:: bash

   # Dry-run (safe — no writes, just prints diff stats):
   py -3.14 -m pytest backend/tests/parity/ -m parity --refresh-baseline

   # Actually overwrite the golden fixtures (requires --confirm):
   py -3.14 -m pytest backend/tests/parity/ -m parity \
        --refresh-baseline --confirm

See ``tests/fixtures/iberia_868/golden/README.md`` and the D-09 waiver at
``.planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md``
for when refresh is appropriate.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import load_region

# backend/tests/parity/conftest.py -> repo root (parents[3])
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "iberia_868" / "golden"


# ---------------------------------------------------------------------------
# pytest CLI plugin
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("parity-refresh", "iberia_868 parity baseline refresh")
    group.addoption(
        "--refresh-baseline",
        action="store_true",
        default=False,
        help=(
            "Re-run the pipeline and refresh tests/fixtures/iberia_868/golden/ "
            "instead of asserting equality. Dry-run by default — pair with "
            "--confirm to actually overwrite."
        ),
    )
    group.addoption(
        "--confirm",
        action="store_true",
        default=False,
        help=(
            "Confirm a baseline refresh actually writes to disk. Required "
            "companion to --refresh-baseline; without it the tool only prints "
            "the diff summary."
        ),
    )


def _resolve_golden_dir(config: pytest.Config) -> Path:
    """Allow unit tests to override the golden dir via config attribute."""
    override = getattr(config, "_parity_golden_dir_override", None)
    return Path(override) if override else GOLDEN_DIR


@pytest.fixture(scope="session")
def pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the v3 pipeline once for the session and return its output dir."""
    out = tmp_path_factory.mktemp("iberia_868_actual")
    from dataclasses import replace
    cfg = replace(load_region("iberia_868"), output_dir=str(out))
    run_pipeline(cfg)
    return out


@pytest.fixture(scope="session")
def golden_dir(request: pytest.FixtureRequest) -> Path:
    """Path to the committed golden fixtures (override-able for unit tests)."""
    return _resolve_golden_dir(request.config)


# ---------------------------------------------------------------------------
# Baseline refresh: replaces test bodies when --refresh-baseline is set.
# ---------------------------------------------------------------------------
def _summarise_png_diff(actual: Path, golden: Path) -> str:
    if not golden.exists():
        return f"NEW (no prior golden) -> would write {actual.stat().st_size} B"
    a = np.array(Image.open(actual))
    g = np.array(Image.open(golden))
    if a.shape != g.shape:
        return f"SHAPE differs actual={a.shape} golden={g.shape}"
    if a.ndim == 3:
        mismatch = np.any(a != g, axis=-1)
    else:
        mismatch = a != g
    diff = int(mismatch.sum())
    total = mismatch.size
    pct = 100.0 * diff / total if total else 0.0
    if diff == 0:
        return "BYTE-EQUAL pixels (only PNG header may differ)"
    ys, xs = np.where(mismatch)
    return f"pixel-diff {diff:,}/{total:,} ({pct:.3f}%) bbox=x[{xs.min()}..{xs.max()}] y[{ys.min()}..{ys.max()}]"


def _summarise_json_diff(actual: Path, golden: Path) -> str:
    if not golden.exists():
        return f"NEW (no prior golden) -> would write {actual.stat().st_size} B"
    a = json.loads(actual.read_text(encoding="utf-8"))
    g = json.loads(golden.read_text(encoding="utf-8"))
    if a == g:
        return "deep-equal (whitespace may differ)"
    def count(obj):
        if isinstance(obj, list):
            return f"list[{len(obj)}]"
        if isinstance(obj, dict):
            return f"dict[{len(obj)} keys]"
        return type(obj).__name__
    return f"differs actual={count(a)} golden={count(g)}"


def _summarise(actual: Path, golden: Path) -> str:
    if actual.suffix == ".png":
        return _summarise_png_diff(actual, golden)
    if actual.suffix == ".json":
        return _summarise_json_diff(actual, golden)
    return "unknown filetype"


def _refresh_one(actual: Path, golden: Path, *, confirm: bool, sink) -> None:
    """Print summary; if confirm is set, copy actual->golden."""
    summary = _summarise(actual, golden)
    a_sha = hashlib.sha256(actual.read_bytes()).hexdigest()[:8].upper()
    g_sha = (
        hashlib.sha256(golden.read_bytes()).hexdigest()[:8].upper()
        if golden.exists()
        else "NEW"
    )
    verb = "WROTE" if confirm else "WOULD WRITE"
    sink.write(
        f"  {actual.name:40s} {summary}\n"
        f"      actual_sha={a_sha} golden_sha={g_sha}  -> {verb}\n"
    )
    if confirm:
        shutil.copy2(actual, golden)


def _refresh_for_test(
    pipeline_output: Path,
    golden: Path,
    name: str,
    *,
    confirm: bool,
) -> None:
    actual = pipeline_output / name
    target = golden / name

    sys.stdout.write(f"\n[refresh] {name}:\n")
    _refresh_one(actual, target, confirm=confirm, sink=sys.stdout)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """When --refresh-baseline is set, replace test bodies with a refresh routine.

    The replacement is per-item so each parametrised test (one per file)
    refreshes its own file and prints its own summary.
    """
    if not config.getoption("--refresh-baseline"):
        return

    confirm = config.getoption("--confirm")

    for item in items:
        # Only target parity tests (the file lives at backend/tests/parity/test_iberia_868.py)
        if "parity" not in [m.name for m in item.iter_markers()]:
            continue
        # Each parametrised test has a `name` callspec param.
        callspec = getattr(item, "callspec", None)
        if callspec is None or "name" not in callspec.params:
            continue
        target_name = callspec.params["name"]

        def _make_refresh(_target_name: str):
            # Signature mirrors the parametrised test it replaces — `name` is the
            # parametrize argument pytest passes; we already captured it in the
            # closure but accept the kwarg so pytest's call resolves cleanly.
            def _runner(pipeline_output, golden_dir, name):  # noqa: ARG001
                _refresh_for_test(
                    pipeline_output,
                    golden_dir,
                    _target_name,
                    confirm=confirm,
                )
            return _runner

        # Replace the test function so `pytest` still records pass/fail.
        item.obj = _make_refresh(target_name)


def pytest_report_header(config: pytest.Config) -> list[str]:
    if not config.getoption("--refresh-baseline"):
        return []
    if config.getoption("--confirm"):
        return [
            "PARITY REFRESH MODE: --refresh-baseline --confirm — golden fixtures WILL be overwritten.",
        ]
    return [
        "PARITY REFRESH MODE: --refresh-baseline (DRY RUN — pass --confirm to actually overwrite).",
    ]
