"""Wave 0 stub for Phase 08 — implemented in plan 08-01.

Covers REQ-IDs: DAG-01, DAG-02, DAG-03
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

BLOCKER-2 fix note: test names assert that count term is present in the
version_token string (not just that the token changed).
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-01")


def test_manual_edit_stage_version_token_contains_count_term():
    """Test will be filled by plan 08-01 per VALIDATION.md per-task table.

    DAG-01 + BLOCKER-2 fix: version_token for the manual_edit stage must
    include the operation count so different edit sequences produce
    non-colliding tokens (e.g. 'manual_edit_v3' not just 'manual_edit').
    """
    pass


def test_initial_manual_edit_token_is_identity_passthrough():
    """Test will be filled by plan 08-01 per VALIDATION.md per-task table.

    DAG-02: before any manual edits, the manual_edit stage version_token
    equals the identity sentinel so Iberia 868 parity is preserved
    (no spurious cache miss on first generate run).
    """
    pass


def test_dag_carry_forward_leaves_parity_stages_intact():
    """Test will be filled by plan 08-01 per VALIDATION.md per-task table.

    DAG-02: applying manual edits only invalidates stages downstream of
    manual_edit; stages upstream (voronoi, cleanup, smooth) keep their
    cached version tokens unchanged.
    """
    pass


def test_stage_order_manual_edit_inserted_after_smooth():
    """Test will be filled by plan 08-01 per VALIDATION.md per-task table.

    DAG-03: DAG_ORDER contains 'manual_edit' positioned after 'smooth' and
    before 'render' so manual edits re-trigger render but not voronoi.
    """
    pass
