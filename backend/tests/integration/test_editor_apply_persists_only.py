"""Wave 0 stub for Phase 08 — implemented in plan 08-07.

Covers REQ-IDs: EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03, PERSIST-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

BLOCKER-1 contract: /editor/apply response JSON must have no geometry/polygon/coords keys.
The endpoint persists the edit event to the DB and returns a lightweight
acknowledgement; geometry computation happens server-side via compute() replay,
never round-trips raw coordinates to the client.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-07")


def test_editor_apply_response_has_no_geometry_key():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    BLOCKER-1 contract: POST /api/v3/projects/{id}/editor/apply response
    body must NOT contain any of: 'geometry', 'polygon', 'coords', 'coordinates'.
    """
    pass


def test_editor_apply_response_has_no_polygon_key():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    BLOCKER-1 contract: POST /api/v3/projects/{id}/editor/apply response
    body must NOT contain a 'polygon' key at any nesting level.
    """
    pass


def test_editor_apply_response_has_no_coords_key():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    BLOCKER-1 contract: POST /api/v3/projects/{id}/editor/apply response
    body must NOT contain a 'coords' or 'coordinates' key at any nesting level.
    """
    pass


def test_editor_apply_persists_edit_event_to_db_and_returns_201():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    PERSIST-01: POST /api/v3/projects/{id}/editor/apply returns HTTP 201
    and the edit_event row is persisted in the edit_events table.
    """
    pass
