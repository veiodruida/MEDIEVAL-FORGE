"""Wave 0 stub for Phase 08 — implemented in plan 08-06a.

Covers REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, TOPO-01, TOPO-02
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-06a")


def test_validate_endpoint_returns_ok_for_valid_polygon():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    EDIT-VERTEX-01: POST /api/v3/projects/{id}/editor/validate with a valid
    polygon returns {"ok": true, "code": null}.
    """
    pass


def test_validate_endpoint_returns_error_code_for_self_intersecting_polygon():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    TOPO-01: POST /api/v3/projects/{id}/editor/validate with a self-intersecting
    polygon returns {"ok": false, "code": "SELF_INTERSECT"}.
    """
    pass


def test_validate_endpoint_returns_error_code_for_neighbour_gap():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    TOPO-02: POST /api/v3/projects/{id}/editor/validate detects a gap between
    edited and neighbour polygon and returns code "NEIGHBOUR_GAP".
    """
    pass


def test_validate_endpoint_returns_422_for_malformed_geojson():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    EDIT-VERTEX-02: POST /api/v3/projects/{id}/editor/validate with malformed
    GeoJSON input returns HTTP 422 with a descriptive error body.
    """
    pass
