"""Smoke test for the standalone pipeline CLI.

Per ROADMAP success criterion 2: the pipeline must run without FastAPI via
`python -m medieval_forge.services.pipeline`. The end-to-end run is covered
by the parity session fixture (a separate @pytest.mark.slow CLI run would
roughly double CI time).
"""
from __future__ import annotations

import subprocess
import sys


def test_main_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "medieval_forge.services.pipeline", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"CLI --help exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "iberia_868" in result.stdout, (
        f"--help output must list `iberia_868` as a region choice; got:\n{result.stdout}"
    )
