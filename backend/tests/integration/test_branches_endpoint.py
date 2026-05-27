"""Wave 0 stub for Phase 08 — implemented in plan 08-02.

Covers REQ-IDs: BRANCH-01, BRANCH-02, BRANCH-04, BRANCH-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-02")


def test_POST_branches_creates_branch_and_returns_201():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-01: POST /api/v3/projects/{id}/branches creates a branch row
    and returns 201 with branch_id in response body.
    """
    pass


def test_GET_branches_lists_all_branches_for_project():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-02: GET /api/v3/projects/{id}/branches returns a list of all
    branch names and IDs for the given project.
    """
    pass


def test_DELETE_branch_removes_branch_and_associated_snapshots():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-05: DELETE /api/v3/projects/{id}/branches/{branch_id} removes
    the branch row and cascades to snapshot rows.
    """
    pass


def test_PATCH_branch_switch_updates_active_branch_in_project():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-04: PATCH /api/v3/projects/{id}/branches/active sets the active
    branch for the project and returns updated project state.
    """
    pass
