"""Wave 0 stub for Phase 08 — implemented in plan 08-10.

Covers REQ-IDs: DAG-01, DAG-02, BRANCH-04, BRANCH-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-10")


def test_render_on_branch_uses_branch_stage_cache_not_main():
    """Test will be filled by plan 08-10 per VALIDATION.md per-task table.

    BRANCH-04: POST /api/v3/projects/{id}/generate with an active branch
    populates branch-keyed cache entries, not the main branch cache.
    """
    pass


def test_render_on_main_branch_unaffected_by_feature_branch_edits():
    """Test will be filled by plan 08-10 per VALIDATION.md per-task table.

    BRANCH-05: lookup_barony.png generated on main branch is byte-equal
    before and after edits made on a separate feature branch.
    """
    pass


def test_render_with_manual_edits_produces_different_lookup_than_baseline():
    """Test will be filled by plan 08-10 per VALIDATION.md per-task table.

    DAG-01 + DAG-02: after applying manual vertex edits and re-rendering,
    lookup_barony.png SHA-256 differs from the pre-edit baseline.
    """
    pass
