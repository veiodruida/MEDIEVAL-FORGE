"""Phase 08 BLOCKER-1 closure (plan 08-07c): parity tests for edit visibility.

REQ-IDs: DAG-01, DAG-02, EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03

CRITICAL assertion polarity:
  test_one_vertex_translate_mutates_lookup_barony_png asserts != (NOT ==).
  This is intentional and easy to write in the wrong direction.
  The purpose is to prove that a user edit propagates through
  manual_edit.compute() → hierarchy → render → lookup_barony.png.

Identity test:
  test_empty_edit_log_preserves_lookup_barony_png asserts ==
  to prove D-17 carry-forward (no regression for the empty-log path).

Both tests use a stub snapshot_loader injected directly on cfg so no DB or
production branches service is required. The orchestrator honours an
already-set cfg.snapshot_loader without overwriting it.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

pytestmark = pytest.mark.parity


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Test 1: NOVEL POLARITY — one translate op MUST mutate lookup_barony.png
# ---------------------------------------------------------------------------

@pytest.mark.parity
def test_one_vertex_translate_mutates_lookup_barony_png(tmp_path):
    """BLOCKER-1 closure (D-17): a single translate op must change lookup_barony.png.

    Assertion direction: != (NOT ==) — proves edits propagate to canonical raster.
    If this test passes with == it means the replay path is identity (BLOCKER-1 regression).
    """
    from medieval_forge.services.pipeline import run_pipeline
    from medieval_forge.services.pipeline.region_loader import load_region

    # ---- Baseline: empty edit log ----
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    cfg_baseline = replace(
        load_region("iberia_868"),
        output_dir=str(baseline_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
    )
    run_pipeline(cfg_baseline)
    baseline_sha = _sha256(baseline_dir / "lookup_barony.png")

    # ---- Edited: one translate op on barony idx 1 ----
    edited_dir = tmp_path / "edited"
    edited_dir.mkdir()

    one_op_log = {
        "edit_log": [
            {
                "op": "translate",
                "polygonId": 1,    # barony idx 1 exists in every Iberia 868 run
                "dLat": 2.0,       # large enough shift to guarantee pixel-level change
                "dLon": 0.0,
                "ts": 0,
            }
        ]
    }
    edit_hash = hashlib.sha256(repr(one_op_log["edit_log"]).encode()).hexdigest()[:16]

    cfg_edited = replace(
        load_region("iberia_868"),
        output_dir=str(edited_dir),
        manual_edit_log_hash=edit_hash,
        manual_edit_log_count=1,
    )
    # Inject stub loader directly — orchestrator honours pre-set snapshot_loader
    # without overwriting it (see __init__.py wiring).
    cfg_edited.snapshot_loader = lambda _branch_id: one_op_log

    run_pipeline(cfg_edited)
    edited_sha = _sha256(edited_dir / "lookup_barony.png")

    # CRITICAL: assertion is != not == — proves the edit propagated.
    assert edited_sha != baseline_sha, (
        "BLOCKER-1 regression: lookup_barony.png unchanged after translate op. "
        "Edits are not flowing through manual_edit.compute() → DAG → lookup_barony.png."
    )


# ---------------------------------------------------------------------------
# Test 2: IDENTITY — empty edit log must NOT change lookup_barony.png
# ---------------------------------------------------------------------------

@pytest.mark.parity
def test_empty_edit_log_preserves_lookup_barony_png(tmp_path):
    """D-17 carry-forward: empty manual_edit_log_hash → lookup_barony.png unchanged.

    Runs pipeline twice with empty edit log and asserts byte-equal SHA-256.
    Also compares against canonical Reconquista baseline if available.
    """
    from medieval_forge.services.pipeline import run_pipeline
    from medieval_forge.services.pipeline.region_loader import load_region

    # Run 1
    run1_dir = tmp_path / "run1"
    run1_dir.mkdir()
    cfg1 = replace(
        load_region("iberia_868"),
        output_dir=str(run1_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
    )
    run_pipeline(cfg1)

    # Run 2 (determinism check)
    run2_dir = tmp_path / "run2"
    run2_dir.mkdir()
    cfg2 = replace(
        load_region("iberia_868"),
        output_dir=str(run2_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
    )
    run_pipeline(cfg2)

    sha1 = _sha256(run1_dir / "lookup_barony.png")
    sha2 = _sha256(run2_dir / "lookup_barony.png")

    assert sha1 == sha2, (
        "D-17 carry-forward regression: two identity runs produced different "
        "lookup_barony.png. Pipeline is non-deterministic."
    )

    # Also check against canonical Reconquista baseline if accessible
    canonical = Path("D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/lookup_barony.png")
    if canonical.exists():
        canonical_sha = _sha256(canonical)
        assert sha1 == canonical_sha, (
            "D-17 carry-forward regression: identity path no longer byte-equal "
            "to canonical Reconquista lookup_barony.png."
        )
