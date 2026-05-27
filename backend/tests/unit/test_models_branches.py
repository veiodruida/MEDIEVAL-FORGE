"""Wave 0 stub for Phase 08 — implemented in plan 08-02.

Covers REQ-IDs: BRANCH-01, BRANCH-02, BRANCH-03, PERSIST-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-02")


def test_branch_orm_roundtrip_persists_and_retrieves_by_id():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-01 + PERSIST-01: Branch ORM model inserts a row in the
    'branches' table and SELECT by primary key returns the same data.
    """
    pass


def test_snapshot_orm_roundtrip_stores_compressed_geojson():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    PERSIST-01: Snapshot ORM model stores compressed GeoJSON bytes in
    the 'snapshots' table; decompress on retrieve yields identical JSON.
    """
    pass


def test_edit_event_orm_roundtrip_preserves_operation_type_and_payload():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    PERSIST-01: EditEvent ORM model persists operation_type (move/split/merge)
    and payload dict; round-trip via ORM yields equal dict.
    """
    pass


def test_branch_has_unique_constraint_on_project_id_and_name():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-03: IntegrityError raised when inserting a second branch with
    the same (project_id, name) pair.
    """
    pass
