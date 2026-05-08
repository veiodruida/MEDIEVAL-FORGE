"""Unit tests for the parity baseline-refresh tool defined in
``backend/tests/parity/conftest.py``.

These tests intentionally DO NOT run the real iberia_868 pipeline (45 s).
Instead they exercise the helper functions directly with synthetic 8-pixel
PNG and 1-key JSON fixtures, plus drive the pytest plugin via
``pytester``-style subprocess invocation against a tmpdir scratch fixture
set. The real ``tests/fixtures/iberia_868/golden/`` is never touched.

Coverage:

  * ``_summarise_png_diff`` — byte-equal, pixel-diff, missing golden, shape diff
  * ``_summarise_json_diff`` — deep-equal, dict-vs-list, missing golden
  * ``_refresh_one`` dry-run vs --confirm semantics (file actually copied)
  * Plugin CLI: ``--refresh-baseline`` without ``--confirm`` reports but does
    NOT mutate; ``--refresh-baseline --confirm`` mutates.

Determinism contract is asserted by running ``_refresh_one`` twice and
checking the second run produces ``BYTE-EQUAL`` summary.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

# Import the helpers we are testing. These live in the parity conftest.py
# (a pytest plugin), but they are plain module-level functions so we can
# import them directly without invoking pytest collection.
from tests.parity import conftest as parity_conftest


# --- Fixture builders ------------------------------------------------------
def _write_png(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(pixels).save(path)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# --- _summarise_png_diff ---------------------------------------------------
def test_png_diff_byte_equal(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    g = tmp_path / "g.png"
    pixels = np.zeros((4, 4, 3), dtype=np.uint8)
    _write_png(a, pixels)
    _write_png(g, pixels)
    out = parity_conftest._summarise_png_diff(a, g)
    assert "BYTE-EQUAL" in out


def test_png_diff_with_mismatch_reports_count_and_bbox(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    g = tmp_path / "g.png"
    pix_a = np.zeros((4, 4, 3), dtype=np.uint8)
    pix_g = pix_a.copy()
    pix_g[1, 2] = [255, 0, 0]  # one differing pixel at (y=1, x=2)
    _write_png(a, pix_a)
    _write_png(g, pix_g)
    out = parity_conftest._summarise_png_diff(a, g)
    assert "pixel-diff 1/16" in out
    assert "x[2..2] y[1..1]" in out


def test_png_diff_missing_golden_reports_NEW(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    g = tmp_path / "g.png"  # not written
    _write_png(a, np.zeros((2, 2, 3), dtype=np.uint8))
    out = parity_conftest._summarise_png_diff(a, g)
    assert "NEW (no prior golden)" in out


def test_png_diff_shape_mismatch(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    g = tmp_path / "g.png"
    _write_png(a, np.zeros((4, 4, 3), dtype=np.uint8))
    _write_png(g, np.zeros((8, 8, 3), dtype=np.uint8))
    out = parity_conftest._summarise_png_diff(a, g)
    assert "SHAPE differs" in out


# --- _summarise_json_diff --------------------------------------------------
def test_json_diff_deep_equal(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    g = tmp_path / "g.json"
    _write_json(a, {"k": [1, 2]})
    _write_json(g, {"k": [1, 2]})
    out = parity_conftest._summarise_json_diff(a, g)
    assert "deep-equal" in out


def test_json_diff_reports_size_change(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    g = tmp_path / "g.json"
    _write_json(a, {"k": [1, 2, 3]})
    _write_json(g, {"k": [1, 2]})
    out = parity_conftest._summarise_json_diff(a, g)
    assert "differs" in out
    assert "dict[1 keys]" in out


def test_json_diff_missing_golden_reports_NEW(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    g = tmp_path / "g.json"  # not written
    _write_json(a, {"k": 1})
    out = parity_conftest._summarise_json_diff(a, g)
    assert "NEW (no prior golden)" in out


# --- _refresh_one ----------------------------------------------------------
def test_refresh_one_dry_run_does_not_mutate_golden(tmp_path: Path) -> None:
    a = tmp_path / "actual.png"
    g = tmp_path / "golden.png"
    _write_png(a, np.full((4, 4, 3), 255, dtype=np.uint8))  # white
    _write_png(g, np.zeros((4, 4, 3), dtype=np.uint8))  # black
    g_bytes_before = g.read_bytes()
    sink = io.StringIO()
    parity_conftest._refresh_one(a, g, confirm=False, sink=sink)
    assert g.read_bytes() == g_bytes_before, "dry run must NOT overwrite golden"
    assert "WOULD WRITE" in sink.getvalue()


def test_refresh_one_with_confirm_overwrites_golden(tmp_path: Path) -> None:
    a = tmp_path / "actual.png"
    g = tmp_path / "golden.png"
    _write_png(a, np.full((4, 4, 3), 255, dtype=np.uint8))
    _write_png(g, np.zeros((4, 4, 3), dtype=np.uint8))
    sink = io.StringIO()
    parity_conftest._refresh_one(a, g, confirm=True, sink=sink)
    assert g.read_bytes() == a.read_bytes(), "confirm must copy actual->golden"
    assert "WROTE" in sink.getvalue()


def test_refresh_one_idempotent_after_confirm(tmp_path: Path) -> None:
    """Determinism contract: a second refresh should report BYTE-EQUAL."""
    a = tmp_path / "actual.png"
    g = tmp_path / "golden.png"
    _write_png(a, np.full((4, 4, 3), 200, dtype=np.uint8))
    _write_png(g, np.zeros((4, 4, 3), dtype=np.uint8))
    parity_conftest._refresh_one(a, g, confirm=True, sink=io.StringIO())
    sink = io.StringIO()
    parity_conftest._refresh_one(a, g, confirm=False, sink=sink)
    assert "BYTE-EQUAL" in sink.getvalue()


# --- Plugin smoke test -----------------------------------------------------
@pytest.mark.parametrize("with_confirm", [False, True])
def test_plugin_dry_run_vs_confirm(tmp_path: Path, with_confirm: bool) -> None:
    """Drive the pytest plugin against a synthetic golden dir.

    Builds a ``synthetic_test.py`` that uses ``pipeline_output`` and
    ``golden_dir`` fixtures, sets up a fake pipeline_output via
    ``conftest.py`` override, and asserts the plugin replaces the test body.

    Verifies that:
      * --refresh-baseline alone never touches files
      * --refresh-baseline --confirm overwrites the (synthetic) golden
      * the real ``tests/fixtures/iberia_868/golden/`` is NEVER read or
        written by this test (we override GOLDEN_DIR via config attribute).
    """
    import subprocess
    import sys
    import textwrap

    fake_golden = tmp_path / "synthetic_golden"
    fake_golden.mkdir()
    fake_actual = tmp_path / "synthetic_actual"
    fake_actual.mkdir()

    # Synthetic golden + actual differ — actual is white, golden is black.
    actual_pixels = np.full((4, 4, 3), 255, dtype=np.uint8)
    golden_pixels = np.zeros((4, 4, 3), dtype=np.uint8)
    _write_png(fake_actual / "fake.png", actual_pixels)
    _write_png(fake_golden / "fake.png", golden_pixels)

    # tiny conftest.py that:
    #   * imports the parity plugin (so --refresh-baseline / --confirm exist)
    #   * overrides pipeline_output to point at our fake_actual
    #   * overrides GOLDEN_DIR via config attribute (the parity conftest reads it)
    rootdir = tmp_path / "scratch"
    rootdir.mkdir()
    conftest = rootdir / "conftest.py"
    conftest.write_text(textwrap.dedent(f"""
        import pytest
        from pathlib import Path
        # Re-export every option from the parity conftest by importing it.
        # The plugin only activates when its options are seen on the CLI.
        from tests.parity import conftest as parity_conftest

        def pytest_addoption(parser):
            parity_conftest.pytest_addoption(parser)

        def pytest_collection_modifyitems(config, items):
            parity_conftest.pytest_collection_modifyitems(config, items)

        def pytest_configure(config):
            config._parity_golden_dir_override = r"{fake_golden}"

        @pytest.fixture(scope="session")
        def pipeline_output():
            return Path(r"{fake_actual}")

        @pytest.fixture(scope="session")
        def golden_dir(request):
            return parity_conftest._resolve_golden_dir(request.config)
    """), encoding="utf-8")
    test_file = rootdir / "test_synthetic.py"
    test_file.write_text(textwrap.dedent("""
        import pytest

        @pytest.mark.parity
        @pytest.mark.parametrize("name", ["fake.png"])
        def test_synthetic_eq(pipeline_output, golden_dir, name):
            # The plugin replaces this body when --refresh-baseline is set.
            # Without the flag, this would assert equality and fail (white != black).
            assert (pipeline_output / name).read_bytes() == (golden_dir / name).read_bytes()
    """), encoding="utf-8")

    args = [sys.executable, "-m", "pytest", str(test_file), "-v",
            "-p", "no:cacheprovider", "--refresh-baseline",
            "--override-ini=addopts=", "-o", "markers=parity: parity tests"]
    if with_confirm:
        args.append("--confirm")
    result = subprocess.run(args, capture_output=True, text=True, timeout=60,
                            cwd=Path(__file__).resolve().parents[3])

    assert result.returncode == 0, (
        f"plugin smoke test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    # In dry-run, the synthetic golden file must remain unchanged (still black).
    # In confirm mode, the synthetic golden must now match actual (white).
    final_golden = np.array(Image.open(fake_golden / "fake.png").convert("RGB"))
    if with_confirm:
        assert np.all(final_golden == 255), "with --confirm, golden must be overwritten"
    else:
        assert np.all(final_golden == 0), "dry run must NOT overwrite golden"


# --- Safety guarantee: the real golden dir is NEVER touched by these tests ---
def test_real_golden_dir_unchanged_by_unit_tests() -> None:
    """The real fixtures live under tests/fixtures/iberia_868/golden/. None
    of the unit tests above point at that path; this test asserts the
    GOLDEN_DIR resolution helper falls back to the in-tree path only when no
    override is set, and that the override mechanism is the only way to
    redirect it.
    """

    class _Cfg:
        pass

    # No override -> resolves to in-tree GOLDEN_DIR
    cfg = _Cfg()
    assert parity_conftest._resolve_golden_dir(cfg) == parity_conftest.GOLDEN_DIR

    # With override -> resolves to override path
    cfg2 = _Cfg()
    cfg2._parity_golden_dir_override = r"C:\some\other\path"
    assert parity_conftest._resolve_golden_dir(cfg2) == Path(r"C:\some\other\path")
