"""Unit tests for the additive ``idx`` field on territories.geojson condado features.

Plan 08.3-09 Task 1 (RED → GREEN).

INVARIANT: ``ci`` (the enumerate index in ``for ci, c in enumerate(condados)``) equals
the same index space used by the baronies emitter (``cfg.condados[condado_idx]``).
Adding ``"idx": ci`` to each condado Feature makes this index readable by the
CondadoPicker without a separate lookup.

Key fixture requirement: at least ONE condado must be SKIPPED by the
``if not geoms: continue`` guard so that emitted-array position ≠ original ci.
Without a skipped condado, emitted-position and ci coincide and the test would
false-pass under a wrong implementation.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from medieval_forge.services.canvas_sidecars import build_territories_geojson_sidecar
from medieval_forge.services.pipeline.contracts import RegionConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_cfg_three_condados(tmp_path: str) -> RegionConfig:
    """Build a minimal RegionConfig with 3 condados in 1 duchy/kingdom.

    condados:
      idx 0 → C0 "Condado Zero"   (duchy D1, kingdom K1)
      idx 1 → C1 "Condado Um"     (duchy D1, kingdom K1)  — will be SKIPPED (no geom)
      idx 2 → C2 "Condado Dois"   (duchy D2, kingdom K1)

    Two duchies so transitive duchy/kingdom differ between idx 0 and idx 2.
    """
    cfg = RegionConfig(
        name="test",
        map_w=20,
        map_h=20,
        lon_min=-10.0,
        lon_max=0.0,
        lat_min=36.0,
        lat_max=44.0,
        output_dir=tmp_path,
        kingdoms={"K1": ("K1", "Reino de Test")},
        duchies={
            "D1": ("K1", "Ducado Um"),
            "D2": ("K1", "Ducado Dois"),
        },
        condados=[
            ("C0", "Condado Zero", -8.0, 40.0, "D1"),   # idx 0
            ("C1", "Condado Um",   -7.0, 40.0, "D1"),   # idx 1 — NO geometry (skipped)
            ("C2", "Condado Dois", -6.0, 40.0, "D2"),   # idx 2
        ],
    )
    if cfg.lon_scale is None:
        import math
        cfg.lon_scale = math.cos(math.radians((cfg.lat_min + cfg.lat_max) / 2))
    return cfg


def _make_pc_two_condados() -> np.ndarray:
    """20×20 raster: left half = condado 0, right half = condado 2.

    Condado 1 intentionally has NO pixels → skipped by the sidecar emitter.
    pc uses ORIGINAL condado indices (0 and 2 — not compacted to 0 and 1).
    """
    pc = np.full((20, 20), -1, dtype=np.int64)
    pc[:, :10] = 0   # condado idx 0
    pc[:, 10:] = 2   # condado idx 2 (skip idx 1 — no pixels for it)
    return pc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_territories_geojson_condado_feature_carries_idx_equal_to_ORIGINAL_cfg_condados_index(tmp_path):
    """Every emitted condado feature's properties.idx must equal its ORIGINAL enumerate
    index ``ci`` into ``cfg.condados`` — NOT its position in the emitted features array.

    With condados [C0(idx0, geom), C1(idx1, NO geom → skipped), C2(idx2, geom)]:
      - Emitted features: [C0, C2]
      - C0.properties.idx must be 0 (original enumerate index, not array position 0 — coincides)
      - C2.properties.idx must be 2 (original enumerate index), NOT 1 (emitted array position)

    Without the skipped condado C1, emitted-array-position and ci would coincide,
    making the test unable to distinguish a correct idx from a wrong "array position" idx.
    """
    cfg = _make_cfg_three_condados(str(tmp_path))
    pc = _make_pc_two_condados()
    condado_cmap: dict[str, int] = {}

    build_territories_geojson_sidecar(
        pc=pc,
        condados=cfg.condados,
        duchies=cfg.duchies,
        cfg=cfg,
        condado_cmap=condado_cmap,
        out_dir=str(tmp_path),
    )

    with open(os.path.join(str(tmp_path), "territories.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    assert fc["type"] == "FeatureCollection"
    # Exactly 2 features emitted (C1 skipped — no geometry)
    assert len(fc["features"]) == 2, (
        f"Expected 2 features (C0, C2); got {len(fc['features'])}"
    )

    feat_by_id: dict[str, dict] = {f["id"]: f for f in fc["features"]}

    # C0: original enumerate index = 0
    assert "C0" in feat_by_id, "Feature for C0 not found"
    assert "idx" in feat_by_id["C0"]["properties"], "properties.idx missing from C0"
    assert feat_by_id["C0"]["properties"]["idx"] == 0, (
        f"C0.properties.idx expected 0, got {feat_by_id['C0']['properties']['idx']}"
    )
    assert isinstance(feat_by_id["C0"]["properties"]["idx"], int)

    # C2: original enumerate index = 2 (NOT 1, the emitted array position)
    assert "C2" in feat_by_id, "Feature for C2 not found"
    assert "idx" in feat_by_id["C2"]["properties"], "properties.idx missing from C2"
    assert feat_by_id["C2"]["properties"]["idx"] == 2, (
        f"C2.properties.idx expected 2 (original ci), got {feat_by_id['C2']['properties']['idx']} "
        "(wrong: this would be 1 if implementation used emitted array position instead of ci)"
    )
    assert isinstance(feat_by_id["C2"]["properties"]["idx"], int)


@pytest.mark.unit
def test_territories_geojson_retains_id_name_duchy_kingdom_after_adding_idx(tmp_path):
    """Existing properties (id, name, duchy_id, kingdom_id, neighbors, centroid) must all
    still be present after the additive idx field is introduced — nothing removed or renamed.
    """
    cfg = _make_cfg_three_condados(str(tmp_path))
    pc = _make_pc_two_condados()

    build_territories_geojson_sidecar(
        pc=pc,
        condados=cfg.condados,
        duchies=cfg.duchies,
        cfg=cfg,
        condado_cmap={},
        out_dir=str(tmp_path),
    )

    with open(os.path.join(str(tmp_path), "territories.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    for feat in fc["features"]:
        props = feat["properties"]
        # existing fields must survive
        assert "id" in props, f"id missing from {feat['id']}"
        assert "name" in props, f"name missing from {feat['id']}"
        assert "duchy_id" in props, f"duchy_id missing from {feat['id']}"
        assert "kingdom_id" in props, f"kingdom_id missing from {feat['id']}"
        assert "neighbors" in props, f"neighbors missing from {feat['id']}"
        assert "centroid" in props, f"centroid missing from {feat['id']}"
        # additive field present too
        assert "idx" in props, f"idx missing from {feat['id']}"

    # Spot-check values for C2 (duchy D2, kingdom K1)
    feat_c2 = next(f for f in fc["features"] if f["id"] == "C2")
    assert feat_c2["properties"]["duchy_id"] == "D2"
    assert feat_c2["properties"]["kingdom_id"] == "K1"
    assert feat_c2["properties"]["name"] == "Condado Dois"


@pytest.mark.unit
def test_territories_idx_matches_barony_condado_idx_source(tmp_path):
    """The ``idx`` value on a territories.geojson condado feature equals the index used to
    look up ``cfg.condados`` in the baronies emitter (``cfg.condados[condado_idx]``).

    Concretely: a barony with condado_idx=2 belongs to the condado whose territories feature
    has properties.idx==2. This verifies the index spaces are the same by construction.
    """
    cfg = _make_cfg_three_condados(str(tmp_path))
    pc = _make_pc_two_condados()

    build_territories_geojson_sidecar(
        pc=pc,
        condados=cfg.condados,
        duchies=cfg.duchies,
        cfg=cfg,
        condado_cmap={},
        out_dir=str(tmp_path),
    )

    with open(os.path.join(str(tmp_path), "territories.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    feat_by_id: dict[str, dict] = {f["id"]: f for f in fc["features"]}

    # cfg.condados[2] is C2 ("Condado Dois") — a barony with condado_idx=2 belongs to C2.
    # The territories feature for C2 must have idx==2 so the picker can resolve the name.
    condado_at_idx_2 = cfg.condados[2]  # ("C2", "Condado Dois", -6.0, 40.0, "D2")
    condado_id_at_2 = condado_at_idx_2[0]  # "C2"

    assert condado_id_at_2 in feat_by_id, f"Feature for condado id {condado_id_at_2!r} not found"
    feat = feat_by_id[condado_id_at_2]
    assert feat["properties"]["idx"] == 2, (
        f"territories feature for cfg.condados[2] must have idx==2; got {feat['properties']['idx']}"
    )

    # Also verify for idx 0
    condado_id_at_0 = cfg.condados[0][0]  # "C0"
    assert feat_by_id[condado_id_at_0]["properties"]["idx"] == 0
