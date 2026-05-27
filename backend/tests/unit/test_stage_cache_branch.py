"""Wave 0 stub for Phase 08 — implemented in plan 08-02.

Covers REQ-IDs: BRANCH-01, BRANCH-02, DAG-04, DAG-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

NOTE: This file ANNOUNCES the rewrite of the existing test_stage_cache.py
in plan 08-02 (atomic swap). It does NOT delete the old file.
Plan 08-02 does the atomic swap: removes test_stage_cache.py and
promotes this file to carry both original + branch-aware tests.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-02")


def test_stage_cache_keyed_by_project_id_and_branch_id():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-01 + DAG-04: cache keys must include branch_id so that edits
    to a branch do not pollute the main branch cache.
    """
    pass


def test_switch_branch_evicts_stale_branch_cache_entries():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    BRANCH-02: switching to a different branch clears stage cache entries
    belonging to the previous branch.
    """
    pass


def test_cache_clear_project_removes_all_branches_for_project():
    """Test will be filled by plan 08-02 per VALIDATION.md per-task table.

    DAG-05: cache_clear_project() removes cache entries for every branch of
    that project, not just the main branch.
    """
    pass
