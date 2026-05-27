"""Wave 0 stub for Phase 08 — implemented in plan 08-08.

Covers REQ-IDs: LANDMASK-01, LANDMASK-02, DAG-04, DAG-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-08")


def test_landmask_cascade_reruns_voronoi_and_render_stages():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    DAG-04 + DAG-05: after a landmask polygon edit, a full generate() call
    recomputes voronoi, cleanup, smooth, and render stages end-to-end.
    """
    pass


def test_landmask_cascade_does_not_rerun_unchanged_upstream_stages():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    DAG-05: the ingestion/adapter stage is NOT rerun after a landmask edit
    because its version_token is unchanged.
    """
    pass


def test_landmask_cascade_output_files_reflect_edited_coastline():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    LANDMASK-02: after cascade, lookup_barony.png visually reflects the
    edited coastline polygon (pixel counts differ from pre-edit baseline).
    """
    pass
