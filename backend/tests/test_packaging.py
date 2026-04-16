"""Tests for PKG-05: frontend bundle is included as package data."""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_declares_static_glob():
    """pyproject.toml must declare static/**/* in tool.setuptools.package-data."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "static/**/*" in pyproject
    assert "[tool.setuptools.package-data]" in pyproject


@pytest.mark.slow
def test_static_in_wheel(tmp_path):
    """Building the wheel produces an artifact whose RECORD includes static/."""
    # Seed a marker file so static/ has at least one entry to ship.
    static_marker = REPO_ROOT / "backend" / "medieval_forge" / "static" / "WHEEL_TEST_MARKER"
    static_marker.write_text("ok", encoding="utf-8")
    try:
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        wheels = list(tmp_path.glob("*.whl"))
        assert wheels, "no wheel produced"
        with zipfile.ZipFile(wheels[0]) as zf:
            names = zf.namelist()
        assert any(
            "medieval_forge/static/WHEEL_TEST_MARKER" in n for n in names
        ), f"static/ not packaged. wheel contents: {names[:30]}"
    finally:
        static_marker.unlink(missing_ok=True)
