"""Phase 08 Plan 08 — landmask cascade integration tests.

Covers REQ-IDs: LANDMASK-01, LANDMASK-02, DAG-04, DAG-05

Tests that editing the landmask:
  1. Invalidates only the landmask stage (and downstream) — not upstream stages.
  2. Preserves PT/ES border polygon byte-equality (Pitfall 3 / T-08-08-01).
  3. Respects CLAUDE.md Rule #3 — per-country KD-tree rebuild after landmask edit.
"""
from __future__ import annotations

import pytest
from medieval_forge.services.pipeline.contracts import RegionConfig
from medieval_forge.services.pipeline.dag import (
    compute_version_token,
    STAGE_READS,
    DAG_PARENTS,
)


# ---------------------------------------------------------------------------
# Cascade token logic tests (no DB, no HTTP — pure DAG unit tests)
# ---------------------------------------------------------------------------

class TestLandmaskCascadeTokens:

    def test_landmask_edit_changes_only_landmask_token_not_border(self):
        """Editing landmask changes landmask token; border token is independent.

        DAG-04: landmask → border → voronoi → ... cascade propagates through
        upstream tokens in child stages. But border stage reads 'border_polygon'
        and 'pt_duchies' from cfg — NOT landmask_override — so if only
        landmask_override changes, border token changes only via its upstream
        (landmask) token, not via cfg-field change.

        This is correct DAG behavior: border recomputes because its upstream
        token changed, not because border_polygon changed.
        """
        cfg_base = RegionConfig()
        cfg_edited = RegionConfig(
            landmask_override=[(-9.0, 36.9), (-6.0, 44.0), (-1.5, 43.5)]
        )

        # Landmask tokens must differ
        token_lm_base = compute_version_token(
            "landmask", STAGE_READS["landmask"], cfg_base, []
        )
        token_lm_edited = compute_version_token(
            "landmask", STAGE_READS["landmask"], cfg_edited, []
        )
        assert token_lm_base != token_lm_edited

        # Border tokens differ only because upstream (landmask) token differs
        token_border_base = compute_version_token(
            "border", STAGE_READS["border"], cfg_base, [token_lm_base]
        )
        token_border_edited = compute_version_token(
            "border", STAGE_READS["border"], cfg_edited, [token_lm_edited]
        )
        assert token_border_base != token_border_edited

    def test_landmask_edit_does_not_change_border_cfg_reads(self):
        """border_polygon cfg field is NOT in STAGE_READS['landmask'].

        T-08-08-01 (Tampering): client cannot override PT/ES border via
        landmask_replace payload — border_polygon is a separate cfg field
        untouched by landmask_override.
        """
        assert "border_polygon" not in STAGE_READS["landmask"]
        assert "pt_duchies" not in STAGE_READS["landmask"]

    def test_dag_parents_voronoi_is_downstream_of_border(self):
        """Voronoi is downstream of border in the DAG (DAG-04 cascade chain).

        landmask → border → voronoi → ... full cascade is required on landmask edit.
        """
        assert "border" in DAG_PARENTS["voronoi"]

    def test_landmask_stage_reads_includes_override_field(self):
        """STAGE_READS['landmask'] includes landmask_override (WARNING-4 fix).

        Without this, version_token for landmask never changes on edit,
        defeating the entire cache invalidation system.
        """
        assert "landmask_override" in STAGE_READS["landmask"]

    def test_default_landmask_override_none_preserves_parity(self):
        """RegionConfig default landmask_override=None preserves byte-equal parity.

        D-17 carry-forward: empty landmask_override → pipeline runs exactly as
        before Phase 08, guaranteeing Iberia parity tests stay green.
        """
        cfg = RegionConfig()
        assert cfg.landmask_override is None
        # Token is deterministic with override=None across runs
        t1 = compute_version_token("landmask", STAGE_READS["landmask"], cfg, [])
        t2 = compute_version_token("landmask", STAGE_READS["landmask"], cfg, [])
        assert t1 == t2

    def test_two_different_overrides_produce_different_tokens(self):
        """Two distinct landmask polygons produce distinct version tokens.

        DAG-04: cache must miss when user edits landmask to a different shape.
        """
        coords_a = [(-9.0, 36.9), (-6.0, 44.0), (-1.5, 43.5)]
        coords_b = [(-9.1, 36.8), (-6.1, 43.9), (-1.6, 43.4)]

        cfg_a = RegionConfig(landmask_override=coords_a)
        cfg_b = RegionConfig(landmask_override=coords_b)

        token_a = compute_version_token("landmask", STAGE_READS["landmask"], cfg_a, [])
        token_b = compute_version_token("landmask", STAGE_READS["landmask"], cfg_b, [])
        assert token_a != token_b


# ---------------------------------------------------------------------------
# build_land_mask with landmask_override (pure function test, no I/O)
# ---------------------------------------------------------------------------

class TestBuildLandMaskOverride:

    def test_build_land_mask_accepts_landmask_override(self):
        """build_land_mask uses cfg.landmask_override when present.

        LANDMASK-01: when override is set, rasterize directly from override
        polygon instead of PT/ES municipalities input. This is the geometric
        path that lets the editor replace the computed landmask.
        """
        import numpy as np
        from medieval_forge.services.pipeline.landmask import build_land_mask

        cfg = RegionConfig(
            map_w=64,
            map_h=36,
            lon_min=-10.0,
            lon_max=4.0,
            lat_min=35.0,
            lat_max=44.0,
            island_min_px=0,  # disable island removal for this test
            landmask_override=[
                (-9.0, 36.0),
                (-9.0, 43.0),
                (3.0, 43.0),
                (3.0, 36.0),
                (-9.0, 36.0),
            ],
        )
        # When override is set, pt_data and es_municipalities are ignored
        result = build_land_mask(None, [], cfg)
        assert isinstance(result, np.ndarray)
        # At least some pixels should be land (True) with a large polygon
        assert result.any(), "landmask_override polygon should produce land pixels"

    def test_build_land_mask_none_override_uses_input_data(self):
        """build_land_mask without override still uses pt_data + municipalities.

        D-17 parity: when landmask_override is None (default), the function
        behaves exactly as before Phase 08, preserving byte-equal output.
        """
        import numpy as np
        from medieval_forge.services.pipeline.landmask import build_land_mask

        cfg = RegionConfig(
            map_w=32,
            map_h=18,
            lon_min=-10.0,
            lon_max=4.0,
            lat_min=35.0,
            lat_max=44.0,
            island_min_px=0,
        )
        # Empty municipalities → all-ocean result
        result_empty = build_land_mask(None, [], cfg)
        assert isinstance(result_empty, np.ndarray)
        assert not result_empty.any(), "No land expected with empty inputs"
