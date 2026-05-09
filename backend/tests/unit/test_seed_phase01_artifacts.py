"""Unit tests for tests/fixtures/seed_phase01_artifacts.py (Plan 03-08 T1).

Three behaviours guarded:
  1. copies all 14 ARTIFACT_FILES (10 Unity + 4 sidecars) from source_dir
     into projects/<id>/output/ (the file-set contract is what the UAT
     relies on for SC-1 + SC-4).
  2. is idempotent — running twice yields identical state on disk.
  3. delegates project_id validation to paths.project_dir → bad UUIDs
     surface as ValueError (T-03-UAT-01 mitigation).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from medieval_forge.api.v3.artifacts import ARTIFACT_FILES
from medieval_forge.services import paths as paths_mod
from tests.fixtures.seed_phase01_artifacts import seed_phase01_artifacts


@pytest.fixture
def isolated_projects_root(monkeypatch, tmp_path):
    """Redirect PROJECTS_ROOT to a per-test tmp dir."""
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    return tmp_path


@pytest.fixture
def fake_source_dir(tmp_path) -> Path:
    """Create a synthetic source dir holding all 14 ARTIFACT_FILES with
    distinguishable bytes so we can verify byte-exact copy."""
    src = tmp_path / "source"
    src.mkdir()
    for name in ARTIFACT_FILES:
        # Distinct content per file so a swap during copy would surface.
        (src / name).write_bytes(f"FAKE_CONTENT::{name}".encode("utf-8"))
    return src


def test_copies_all_14_artifact_files_into_output_dir(
    isolated_projects_root, fake_source_dir
):
    project_id = str(uuid.uuid4())

    output = seed_phase01_artifacts(project_id, fake_source_dir)

    # Must land inside projects/<id>/output/.
    assert output.name == "output"
    assert output.parent.name == project_id

    # All 14 files present + byte-exact copies of source.
    copied = {p.name for p in output.iterdir() if p.is_file()}
    assert copied == set(ARTIFACT_FILES), (
        f"expected 14 files, got {len(copied)}: missing={set(ARTIFACT_FILES) - copied}"
    )
    for name in ARTIFACT_FILES:
        assert (output / name).read_bytes() == f"FAKE_CONTENT::{name}".encode("utf-8")

    # Sidecar contract (Plan 03-01): the 4 canvas-sidecar files MUST be present.
    for sidecar in (
        "territories.geojson",
        "baronies.geojson",
        "condado_colors.json",
        "barony_colors.json",
    ):
        assert (output / sidecar).is_file(), f"missing sidecar: {sidecar}"


def test_is_idempotent_running_twice_yields_identical_state(
    isolated_projects_root, fake_source_dir
):
    project_id = str(uuid.uuid4())

    seed_phase01_artifacts(project_id, fake_source_dir)
    output = seed_phase01_artifacts(project_id, fake_source_dir)

    copied = {p.name for p in output.iterdir() if p.is_file()}
    assert copied == set(ARTIFACT_FILES)
    # Bytes still correct after second run.
    for name in ARTIFACT_FILES:
        assert (output / name).read_bytes() == f"FAKE_CONTENT::{name}".encode("utf-8")


def test_rejects_invalid_project_id_with_value_error(
    isolated_projects_root, fake_source_dir
):
    with pytest.raises(ValueError, match="invalid project_id"):
        seed_phase01_artifacts("not-a-uuid", fake_source_dir)
