"""Parity test: incremental /render at default cfg must be byte-equal to /generate.

Plan 04-02 D-17 invariant: run_pipeline_incremental with default iberia_config()
must produce output files with identical SHA-256 hashes to run_pipeline.

This test is intentionally expensive (~90s) — it runs the full pipeline twice.
It is gated by the 'parity' marker and runs only in CI / explicit parity runs.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.parity


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Files to compare (the 10 non-terrain contract files produced by iberia_868)
COMPARE_FILES = [
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


def test_render_at_default_cfg_matches_generate_byte_equal(tmp_path):
    """D-17: run_pipeline (full path) byte-equals run_pipeline_incremental
    (incremental path) at default iberia_config(). Both use tmp_path subdirs
    so they don't interfere with each other or with the parity golden dir."""
    from medieval_forge.services.pipeline import run_pipeline, run_pipeline_incremental
    from medieval_forge.services.pipeline.cache import cache_clear_project
    from medieval_forge.services.pipeline.regions import iberia_config

    # Use a fake project_id for cache operations
    project_id = "d17-parity-test-00000000-0000"

    # Run 1: full /generate path (run_pipeline)
    gen_dir = tmp_path / "generate_out"
    gen_dir.mkdir()
    cfg_gen = iberia_config()
    cfg_gen.output_dir = str(gen_dir)
    cache_clear_project(project_id)
    run_pipeline(cfg_gen, project_id=project_id)

    # Collect hashes from full run
    gen_hashes = {}
    for fname in COMPARE_FILES:
        fpath = gen_dir / fname
        if fpath.exists():
            gen_hashes[fname] = _sha256(fpath)

    # Run 2: incremental /render path (cold cache — all stages must run)
    render_dir = tmp_path / "render_out"
    render_dir.mkdir()
    cfg_render = iberia_config()
    cfg_render.output_dir = str(render_dir)
    cache_clear_project(project_id)
    affected = run_pipeline_incremental(cfg_render, project_id)

    # Collect hashes from incremental run
    render_hashes = {}
    for fname in COMPARE_FILES:
        fpath = render_dir / fname
        if fpath.exists():
            render_hashes[fname] = _sha256(fpath)

    # D-17: both must be identical
    mismatches = []
    for fname in COMPARE_FILES:
        if fname not in gen_hashes:
            mismatches.append(f"{fname}: missing from /generate output")
        elif fname not in render_hashes:
            mismatches.append(f"{fname}: missing from /render output")
        elif gen_hashes[fname] != render_hashes[fname]:
            mismatches.append(
                f"{fname}: hash mismatch\n"
                f"  generate: {gen_hashes[fname]}\n"
                f"  render:   {render_hashes[fname]}"
            )

    assert not mismatches, (
        f"D-17 FAILED: {len(mismatches)} file(s) differ between "
        f"run_pipeline and run_pipeline_incremental at default cfg:\n"
        + "\n".join(mismatches)
    )

    # Also assert that affected is non-empty (all stages ran on cold cache)
    assert len(affected) > 0, "run_pipeline_incremental returned empty affected list on cold cache"
