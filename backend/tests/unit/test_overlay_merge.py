"""Wave 0 gate — merge_overlay() invariants (Plan 07-05 Task 2).

8 cases covering: original_idx preservation (CLAUDE.md rule 4), input immutability
(deepcopy invariant 1), unknown-id tolerance (invariant 3), 3-field merge,
allowed_fields filtering, load_overlay_if_exists guard semantics, pydantic
validation on corrupt file, REVIEWS fix #1 max_length=2048 boundary.

Fixtures use explicit numeric values (project memory: descriptive names +
explicit fixtures).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from medieval_forge.services.research.overlay import (
    CondadoOverlayEntry,
    _ALL_OVERLAY_FIELDS,
    _ZIP_BOUND_FIELDS,
    load_overlay_if_exists,
    merge_overlay,
)

pytestmark = pytest.mark.unit


FIXTURE_METADATA: dict = {
    "region": "iberia",
    "map_size": [3840, 2160],
    "bounds": {"lon_min": -13.2, "lon_max": 8.2, "lat_min": 35.4, "lat_max": 44.6},
    "kingdoms": {"asturias": "Reino das Astúrias", "leon": "Reino de León"},
    "duchies": {"d_asturias": {"kingdom": "asturias", "name": "Ducado das Astúrias"}},
    "condados": [
        {
            "id": "oviedo", "name": "Condado_001", "original_idx": 1,
            "pixel_count": 4500, "pixel_center": [120, 80],
            "lon": -5.84, "lat": 43.36, "duchy": "d_asturias", "kingdom": "asturias",
            "baronies": ["Grado"],
        },
        {
            "id": "leon", "name": "Condado_002", "original_idx": 2,
            "pixel_count": 3800, "pixel_center": [140, 90],
            "lon": -5.57, "lat": 42.60, "duchy": "d_asturias", "kingdom": "asturias",
            "baronies": [],
        },
        {
            "id": "burgos", "name": "Condado_003", "original_idx": 3,
            "pixel_count": 4200, "pixel_center": [180, 100],
            "lon": -3.70, "lat": 42.34, "duchy": "d_asturias", "kingdom": "asturias",
            "baronies": [],
        },
        {
            "id": "toledo", "name": "Condado_004", "original_idx": 4,
            "pixel_count": 5100, "pixel_center": [200, 140],
            "lon": -4.02, "lat": 39.86, "duchy": "d_asturias", "kingdom": "leon",
            "baronies": [],
        },
        {
            "id": "cordoba", "name": "Condado_005", "original_idx": 5,
            "pixel_count": 4700, "pixel_center": [180, 180],
            "lon": -4.78, "lat": 37.89, "duchy": "d_asturias", "kingdom": "leon",
            "baronies": [],
        },
    ],
    "baronies": [],
}

FIXTURE_OVERLAY: dict = {
    "oviedo": {
        "name": "Condado de Oviedo",
        "kingdom_owner": "Reino de Asturias",
        "historical_notes": "Founded 791 AD.",
    },
    "leon": {"name": "Condado de León"},
    "cordoba": {"name": "Califato de Córdoba", "kingdom_owner": "Califato de Córdoba"},
}


# ---------------------------------------------------------------------------
# Test 1: original_idx preservation (CLAUDE.md rule 4)
# ---------------------------------------------------------------------------


def test_merge_overlay_preserves_original_idx_when_condado_has_overlay_entry() -> None:
    merged = merge_overlay(FIXTURE_METADATA, FIXTURE_OVERLAY)
    original_idxs = [c["original_idx"] for c in merged["condados"]]
    assert original_idxs == [1, 2, 3, 4, 5]
    # Sanity: name DID change on oviedo (overlay applied).
    assert merged["condados"][0]["name"] == "Condado de Oviedo"


# ---------------------------------------------------------------------------
# Test 2: input immutability (invariant 1 — deepcopy at top)
# ---------------------------------------------------------------------------


def test_merge_overlay_returns_new_dict_input_unchanged() -> None:
    snapshot = copy.deepcopy(FIXTURE_METADATA)
    merged = merge_overlay(FIXTURE_METADATA, FIXTURE_OVERLAY)
    # Input is byte-identical to its pre-call state.
    assert FIXTURE_METADATA == snapshot
    # Merged is a different object — mutating it must not touch input.
    merged["condados"][0]["name"] = "MUTATED"
    assert FIXTURE_METADATA["condados"][0]["name"] == "Condado_001"


# ---------------------------------------------------------------------------
# Test 3: unknown condado_id silently ignored (invariant 3)
# ---------------------------------------------------------------------------


def test_merge_overlay_ignores_unknown_condado_id_in_overlay() -> None:
    overlay = {
        "ghost_condado": {"name": "Ghost"},  # not in metadata — silently skipped
        "oviedo": {"name": "Condado de Oviedo"},
    }
    merged = merge_overlay(FIXTURE_METADATA, overlay)
    # No exception; condados list length unchanged.
    assert len(merged["condados"]) == len(FIXTURE_METADATA["condados"])
    # ghost_condado did NOT leak into the output.
    ids = [c["id"] for c in merged["condados"]]
    assert "ghost_condado" not in ids


# ---------------------------------------------------------------------------
# Test 4: all 3 fields merged when allowed_fields = _ALL_OVERLAY_FIELDS
# ---------------------------------------------------------------------------


def test_merge_overlay_applies_all_three_fields_when_present() -> None:
    merged = merge_overlay(FIXTURE_METADATA, FIXTURE_OVERLAY, allowed_fields=_ALL_OVERLAY_FIELDS)
    oviedo = merged["condados"][0]
    assert oviedo["name"] == "Condado de Oviedo"
    assert oviedo["kingdom_owner"] == "Reino de Asturias"
    assert oviedo["historical_notes"] == "Founded 791 AD."


# ---------------------------------------------------------------------------
# Test 5: allowed_fields=frozenset({"name"}) drops kingdom_owner + historical_notes
# ---------------------------------------------------------------------------


def test_merge_overlay_with_zip_bound_fields_only_writes_name_when_strict_verdict() -> None:
    """Even though overlay entry supplies all 3, strict bound drops 2 of them."""
    merged = merge_overlay(
        FIXTURE_METADATA,
        FIXTURE_OVERLAY,
        allowed_fields=frozenset({"name"}),
    )
    oviedo = merged["condados"][0]
    assert oviedo["name"] == "Condado de Oviedo"
    # kingdom_owner + historical_notes must NOT be present in the merged condado
    # (they were not in the raw metadata fixture, so absence == not written).
    assert "kingdom_owner" not in oviedo
    assert "historical_notes" not in oviedo


# ---------------------------------------------------------------------------
# Test 6: load_overlay_if_exists returns None when file absent (D-12 guard)
# ---------------------------------------------------------------------------


def test_load_overlay_if_exists_returns_none_when_file_absent(tmp_path: Path) -> None:
    missing = tmp_path / "research_overlay.json"
    assert not missing.exists()
    result = load_overlay_if_exists(missing)
    assert result is None


# ---------------------------------------------------------------------------
# Test 7: load_overlay_if_exists raises ValidationError on schema-invalid file
# ---------------------------------------------------------------------------


def test_load_overlay_if_exists_validates_pydantic_and_raises_on_corrupt_file(
    tmp_path: Path,
) -> None:
    # Schema-invalid: unknown extra key on the entry (extra='forbid').
    bad = tmp_path / "research_overlay.json"
    bad.write_text(json.dumps({"oviedo": {"name": "X", "bogus_key": "y"}}), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_overlay_if_exists(bad)


# ---------------------------------------------------------------------------
# Test 8 (REVIEWS fix #1): CondadoOverlayEntry rejects historical_notes > 2048
# ---------------------------------------------------------------------------


def test_condado_overlay_entry_rejects_historical_notes_longer_than_2048_chars() -> None:
    """Pydantic max_length=2048 enforced at the model boundary."""
    # Exactly 2048 chars — must succeed.
    entry = CondadoOverlayEntry(historical_notes="x" * 2048)
    assert entry.historical_notes is not None
    assert len(entry.historical_notes) == 2048
    # 2049 chars — must raise.
    with pytest.raises(ValidationError):
        CondadoOverlayEntry(historical_notes="x" * 2049)


# ---------------------------------------------------------------------------
# Bonus: invariant 4 — None overlay value leaves existing field alone
# (not strictly required by plan behaviors but documents the invariant)
# ---------------------------------------------------------------------------


def test_merge_overlay_does_not_overwrite_when_overlay_field_value_is_none() -> None:
    overlay = {"oviedo": {"name": None, "kingdom_owner": "Reino de Asturias"}}
    merged = merge_overlay(FIXTURE_METADATA, overlay)
    oviedo = merged["condados"][0]
    # name stayed the original (None was a no-op).
    assert oviedo["name"] == "Condado_001"
    # kingdom_owner was written.
    assert oviedo["kingdom_owner"] == "Reino de Asturias"


# Sanity: _ZIP_BOUND_FIELDS imported correctly (regression guard).
def test_zip_bound_fields_is_a_frozenset() -> None:
    assert isinstance(_ZIP_BOUND_FIELDS, frozenset)
