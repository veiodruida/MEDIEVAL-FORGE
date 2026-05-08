"""End-to-end smoke test for the standalone pipeline CLI (WR-02 fix).

Per ROADMAP success criterion 2 the pipeline must run without FastAPI via
``python -m medieval_forge.services.pipeline``. Phase 01's existing
``backend/tests/unit/test_pipeline_cli.py`` only covers ``--help``, which
exits before ``run_pipeline(cfg)`` is reached. A typo in any of the three
substantive lines in ``__main__.py``::

    cfg = REGIONS[args.region]()    # __main__.py:18
    cfg.output_dir = args.out       # __main__.py:19
    run_pipeline(cfg)               # __main__.py:20

would slip past CI today because the parity fixture imports ``run_pipeline``
directly rather than going through the ``__main__`` shim.

This test runs the CLI as a real subprocess against a tmpdir and asserts:

* exit code 0
* the 10 expected files from the v3 12-file Unity contract land on disk
  (terrain pair is deferred per P-2; ``mountain_river_data.json`` IS
  emitted by ``export_mountain_rivers`` in Phase 01).

Byte-for-byte equality is intentionally NOT asserted here — the parity
suite (``backend/tests/parity/test_iberia_868.py``) already does that.
This test only verifies the CLI plumbing.

The test is marked ``@pytest.mark.integration`` so CI's
``pytest -m "parity or integration"`` selector picks it up. Runtime is
roughly the parity-fixture cost (~45 s on cold disk); since CI already
pays that cost in the parity suite, the additional spend here is just
the second pipeline run and a process bootstrap.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


EXPECTED_FILES = {
    "lookup_barony.png",
    "lookup_condado.png",
    "lookup_barony_colors.json",
    "lookup_condado_colors.json",
    "territory_metadata.json",
    "visual_condado.png",
    "visual_barony.png",
    "mountains_mask.png",
    "rivers_overlay.png",
    "mountain_river_data.json",
}


@pytest.mark.integration
def test_pipeline_cli_end_to_end(tmp_path: Path) -> None:
    """`python -m medieval_forge.services.pipeline` produces the 10 expected files.

    Covers the three lines in ``__main__.py:18-20`` that the existing
    ``--help`` smoke test never reaches.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "medieval_forge.services.pipeline",
            "--region",
            "iberia_868",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,  # ~45 s pipeline + generous CI margin
        # Inherit PYTHONPATH so the package resolves whether installed
        # editable (-e .) or run via pythonpath=["backend"] from pytest.ini.
        env=os.environ.copy(),
    )

    assert result.returncode == 0, (
        f"CLI exited {result.returncode}.\n"
        f"stdout (tail): {result.stdout[-2000:]}\n"
        f"stderr: {result.stderr[-2000:]}"
    )

    produced = {p.name for p in tmp_path.iterdir() if p.is_file()}
    missing = EXPECTED_FILES - produced
    assert not missing, (
        f"CLI did not produce all expected files. Missing: {sorted(missing)}.\n"
        f"Found: {sorted(produced)}"
    )
