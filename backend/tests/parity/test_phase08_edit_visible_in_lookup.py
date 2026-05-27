"""Wave 0 stub for Phase 08 — implemented in plan 08-07c.

Covers REQ-IDs: DAG-01, DAG-02, EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

BLOCKER-1 closure (08-07c): lookup_barony.png must DIFFER from baseline
after a one-operation edit. The assertion is != not == — easy to write
in the wrong direction.

Parity marker is included even in Wave 0 skip state so the parity test
counter is correct from Wave 0 onward.
"""
import pytest

pytestmark = [
    pytest.mark.parity,
    pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-07c"),
]


def test_one_move_op_mutates_lookup_barony_sha256_from_baseline():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    BLOCKER-1 closure: run Iberia 868 baseline, apply a single vertex-move
    edit, re-render, assert that lookup_barony.png SHA-256 DIFFERS from
    the baseline SHA-256. Assertion direction: != (not ==).
    """
    pass


def test_zero_edit_ops_lookup_barony_sha256_equals_baseline():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    DAG-02: with an empty edit log (no edits applied), the generated
    lookup_barony.png SHA-256 equals the Iberia 868 parity baseline
    (identity carry-forward).
    """
    pass
