"""Wave 0 stub for Phase 08 — implemented in plan 08-07.

Covers REQ-IDs: EDIT-POLYGON-02, EDIT-POLYGON-03, DAG-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-07")


def test_merge_two_adjacent_territories_produces_single_polygon():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    EDIT-POLYGON-02: merge_territories() dissolves the shared border between
    two baronies and returns a single Shapely polygon with no interior ring.
    """
    pass


def test_merge_non_adjacent_territories_raises_validation_error():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    EDIT-POLYGON-02: merge_territories() raises a ValidationError when the
    two input geometries do not share any boundary (disjoint).
    """
    pass


def test_merge_emits_dag_manual_edit_version_token():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    DAG-01: merge_territories() increments the manual_edit stage
    version_token so downstream DAG stages are cache-invalidated.
    """
    pass


def test_merged_result_preserves_original_idx_of_surviving_territory():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    EDIT-POLYGON-03: the merged territory retains the original_idx of the
    primary (first) input territory, satisfying Unity byOriginalIdx contract.
    """
    pass
