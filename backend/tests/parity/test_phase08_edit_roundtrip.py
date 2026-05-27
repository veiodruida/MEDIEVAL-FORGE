"""Phase 08 Plan 11 — D-17 carry-forward: empty edit-log identity parity (full 10-file contract).

REQ-IDs: EDIT-VERTEX-01, EDIT-POLYGON-01, EDIT-POLYGON-02, DAG-01, DAG-03, BRANCH-01, PERF-01

This test is the non-skippable parity gate for Plan 08-11. It extends
test_phase08_edit_visible_in_lookup.py (which checks only lookup_barony.png)
to assert the FULL 10-file export contract is byte-equal between two identity
runs (empty manual_edit_log_hash + branch_id='main').

Golden dir contract (Phase 05 decision): 10 files (not 12).
terrain_lookup.png + terrain_types.json are deferred to Phase 06 (P-2).

Files compared:
  lookup_barony.png, lookup_condado.png,
  lookup_barony_colors.json, lookup_condado_colors.json,
  territory_metadata.json,
  visual_condado.png, visual_barony.png,
  mountains_mask.png, rivers_overlay.png,
  mountain_river_data.json

Identity contract (D-17 carry-forward):
  Two sequential runs with manual_edit_log_hash="" and branch_id="main"
  must produce IDENTICAL SHA-256 hashes for all 10 contract files.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

pytestmark = pytest.mark.parity

# Contract files — 10 files (terrain deferred per Phase 05 decision)
ROUNDTRIP_CONTRACT_FILES = [
    "lookup_barony.png",
    "lookup_condado.png",
    "lookup_barony_colors.json",
    "lookup_condado_colors.json",
    "territory_metadata.json",
    "visual_condado.png",
    "visual_barony.png",
    "mountains_mask.png",
    "rivers_overlay.png",
    "mountain_river_data.json",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.mark.parity
def test_empty_edit_log_full_contract_byte_equal(tmp_path: Path) -> None:
    """D-17 carry-forward (Plan 08-11): two identity runs with empty edit log
    produce byte-equal SHA-256 for all 10 contract files.

    This is the non-skippable parity gate that closes Wave 8.
    manual_edit_log_hash="" + branch_id="main" is the identity path —
    no edits should affect any output file.
    """
    from medieval_forge.services.pipeline import run_pipeline
    from medieval_forge.services.pipeline.region_loader import load_region

    # --- Run 1: identity path ---
    run1_dir = tmp_path / "run1"
    run1_dir.mkdir()
    cfg1 = replace(
        load_region("iberia_868"),
        output_dir=str(run1_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
        branch_id="main",
    )
    run_pipeline(cfg1)

    # --- Run 2: identity path (determinism check) ---
    run2_dir = tmp_path / "run2"
    run2_dir.mkdir()
    cfg2 = replace(
        load_region("iberia_868"),
        output_dir=str(run2_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
        branch_id="main",
    )
    run_pipeline(cfg2)

    # --- Assert byte-equal across all 10 contract files ---
    mismatches: list[str] = []
    missing: list[str] = []

    for fname in ROUNDTRIP_CONTRACT_FILES:
        f1 = run1_dir / fname
        f2 = run2_dir / fname

        if not f1.exists():
            missing.append(f"run1/{fname}")
            continue
        if not f2.exists():
            missing.append(f"run2/{fname}")
            continue

        sha1 = _sha256(f1)
        sha2 = _sha256(f2)

        if sha1 != sha2:
            mismatches.append(
                f"{fname}:\n"
                f"  run1: {sha1}\n"
                f"  run2: {sha2}"
            )

    if missing:
        pytest.fail(
            f"D-17 carry-forward: {len(missing)} file(s) missing from pipeline output "
            f"(expected 10 contract files):\n" + "\n".join(missing)
        )

    assert not mismatches, (
        f"D-17 carry-forward regression: {len(mismatches)} file(s) differ between "
        f"two identity runs (manual_edit_log_hash='', branch_id='main').\n"
        f"Pipeline is non-deterministic with empty edit log:\n"
        + "\n".join(mismatches)
    )


@pytest.mark.parity
def test_empty_edit_log_matches_golden_fixtures(tmp_path: Path) -> None:
    """D-17 carry-forward (Plan 08-11): identity run matches committed golden fixtures.

    Compares against tests/fixtures/iberia_868/golden/ — the parity contract.
    Skips gracefully if golden files are missing (e.g. fresh checkout without LFS).
    """
    from medieval_forge.services.pipeline import run_pipeline
    from medieval_forge.services.pipeline.region_loader import load_region

    # Locate golden dir relative to this file:
    # backend/tests/parity/ -> parents[3] = repo root
    repo_root = Path(__file__).resolve().parents[3]
    golden_dir = repo_root / "tests" / "fixtures" / "iberia_868" / "golden"

    if not golden_dir.exists():
        pytest.skip(f"Golden fixtures dir not found: {golden_dir}")

    # Run pipeline with identity parameters
    out_dir = tmp_path / "identity"
    out_dir.mkdir()
    cfg = replace(
        load_region("iberia_868"),
        output_dir=str(out_dir),
        manual_edit_log_hash="",
        manual_edit_log_count=0,
        branch_id="main",
    )
    run_pipeline(cfg)

    # Compare against golden dir
    mismatches: list[str] = []
    skipped: list[str] = []

    for fname in ROUNDTRIP_CONTRACT_FILES:
        actual = out_dir / fname
        golden = golden_dir / fname

        if not golden.exists():
            skipped.append(fname)
            continue

        if not actual.exists():
            mismatches.append(f"{fname}: missing from pipeline output")
            continue

        sha_actual = _sha256(actual)
        sha_golden = _sha256(golden)

        if sha_actual != sha_golden:
            mismatches.append(
                f"{fname}:\n"
                f"  actual: {sha_actual}\n"
                f"  golden: {sha_golden}"
            )

    if skipped:
        # Not a failure — golden files may be partially committed
        import warnings
        warnings.warn(
            f"D-17 parity: {len(skipped)} golden file(s) absent from fixtures dir "
            f"(not counted as failure): {skipped}",
            stacklevel=1,
        )

    assert not mismatches, (
        f"D-17 carry-forward regression: {len(mismatches)} file(s) differ from "
        f"committed golden fixtures (manual_edit_log_hash='', branch_id='main'):\n"
        + "\n".join(mismatches)
    )
