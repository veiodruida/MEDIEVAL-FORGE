"""Phase 08 plan 08-01 — DAG-01, DAG-02 (BLOCKER-2 fix).

Tests for the `manual_edit` stage inserted between `merge` and `hierarchy`
per D-17, and for the D-18 token derivation (sha256(stage + count + loghash)).

Covers:
  DAG-01: manual_edit stage in correct position (merge → manual_edit → hierarchy)
  DAG-02: token is stable for empty hash; differs on hash change; differs when
          ONLY count changes (BLOCKER-2 fix — count is a separate term).
"""
import numpy as np
import pytest
from medieval_forge.services.pipeline import dag, manual_edit
from medieval_forge.services.pipeline.contracts import RegionConfig


@pytest.fixture
def minimal_cfg():
    """Minimal RegionConfig with Phase 08 fields at their defaults (empty log)."""
    return RegionConfig()


# ---------------------------------------------------------------------------
# DAG_ORDER structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dag_order_contains_manual_edit_between_merge_and_hierarchy():
    """DAG-01: DAG_ORDER has 13 entries; manual_edit is at merge+1 and hierarchy-1."""
    assert "manual_edit" in dag.DAG_ORDER, "manual_edit must be in DAG_ORDER"
    idx = dag.DAG_ORDER.index("manual_edit")
    assert dag.DAG_ORDER[idx - 1] == "merge", \
        f"stage before manual_edit must be 'merge', got {dag.DAG_ORDER[idx - 1]}"
    assert dag.DAG_ORDER[idx + 1] == "hierarchy", \
        f"stage after manual_edit must be 'hierarchy', got {dag.DAG_ORDER[idx + 1]}"
    assert len(dag.DAG_ORDER) == 13, \
        f"DAG_ORDER must have 13 entries after Phase 08 insertion, got {len(dag.DAG_ORDER)}"


@pytest.mark.unit
def test_dag_parents_manual_edit_is_merge():
    """DAG-01: manual_edit parents = ('merge',); hierarchy parents = ('manual_edit',)."""
    assert dag.DAG_PARENTS["manual_edit"] == ("merge",), \
        f"manual_edit parents must be ('merge',), got {dag.DAG_PARENTS['manual_edit']}"
    assert dag.DAG_PARENTS["hierarchy"] == ("manual_edit",), \
        f"hierarchy parents must be ('manual_edit',) after Phase 08, " \
        f"got {dag.DAG_PARENTS['hierarchy']}"


@pytest.mark.unit
def test_stage_reads_manual_edit_is_empty_frozenset():
    """DAG-01: manual_edit reads frozenset() — inputs are out-of-band (snapshot blob)."""
    assert dag.STAGE_READS["manual_edit"] == frozenset(), \
        f"STAGE_READS['manual_edit'] must be frozenset(), got {dag.STAGE_READS['manual_edit']}"


@pytest.mark.unit
def test_stage_token_overrides_manual_edit_is_callable():
    """DAG-01: STAGE_TOKEN_OVERRIDES['manual_edit'] is registered and callable."""
    assert "manual_edit" in dag.STAGE_TOKEN_OVERRIDES, \
        "STAGE_TOKEN_OVERRIDES must contain 'manual_edit'"
    assert callable(dag.STAGE_TOKEN_OVERRIDES["manual_edit"]), \
        "STAGE_TOKEN_OVERRIDES['manual_edit'] must be callable"


# ---------------------------------------------------------------------------
# D-18 token formula (BLOCKER-2 fix: count is a separate term)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_manual_edit_token_empty_hash_is_stable_across_two_calls(minimal_cfg):
    """DAG-02: identity token (empty log_hash) is stable across repeated calls."""
    t1 = manual_edit.manual_edit_token(minimal_cfg, ["upstream_a"])
    t2 = manual_edit.manual_edit_token(minimal_cfg, ["upstream_a"])
    assert t1 == t2, "identity token must be deterministic"
    assert len(t1) == 16, f"token must be 16 hex chars, got {len(t1)}"


@pytest.mark.unit
def test_manual_edit_token_differs_with_non_empty_log_hash(minimal_cfg):
    """DAG-02: token for hash='' differs from token for hash='abc123def4567890'."""
    minimal_cfg.manual_edit_log_hash = ""
    t_empty = manual_edit.manual_edit_token(minimal_cfg, ["u"])
    minimal_cfg.manual_edit_log_hash = "abc123def4567890"
    t_full = manual_edit.manual_edit_token(minimal_cfg, ["u"])
    assert t_empty != t_full, "non-empty log_hash must produce a different token"


@pytest.mark.unit
def test_manual_edit_token_differs_when_only_count_changes(minimal_cfg):
    """DAG-02 + BLOCKER-2 fix: D-18 token formula includes edit_op_count as a separate term.

    Even if log_hash is the same, a different count must yield a different token.
    This proves the count term is in the formula and not just derived from the hash.

    Fixture: same hash='abc123def4567890', count=0 vs count=5 → tokens must differ.
    """
    minimal_cfg.manual_edit_log_hash = "abc123def4567890"
    minimal_cfg.manual_edit_log_count = 0
    t_c0 = manual_edit.manual_edit_token(minimal_cfg, ["u"])
    minimal_cfg.manual_edit_log_count = 5
    t_c5 = manual_edit.manual_edit_token(minimal_cfg, ["u"])
    assert t_c0 != t_c5, (
        "count term must be a separate term in the D-18 token formula per BLOCKER-2 fix; "
        "token with count=0 must differ from token with count=5 (same hash)"
    )


# ---------------------------------------------------------------------------
# Identity compute (D-17 carry-forward)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_manual_edit_compute_empty_hash_returns_input_byte_equal(minimal_cfg):
    """DAG-02 + D-17: empty log_hash → compute() returns input array byte-equal."""
    arr = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int16)
    minimal_cfg.manual_edit_log_hash = ""
    out, _entries = manual_edit.compute(arr, minimal_cfg)
    # Either the same object (preferred — no copy) or byte-equal values
    assert out is arr or np.array_equal(out, arr), \
        "empty log_hash must produce byte-equal output (identity pass-through)"
