"""Wave 0 gate — _ZIP_BOUND_FIELDS verifies actual drop behavior + REVIEWS fix #1.

5 cases:
    1. Strict-verdict (allowed_fields={name}) drops kingdom_owner + historical_notes.
    2. Tolerant-verdict (allowed_fields={name,kingdom_owner,historical_notes}) keeps all.
    3. _ZIP_BOUND_FIELDS <= _ALL_OVERLAY_FIELDS containment.
    4. Drift guard — overlay.py constant matches Q2 verdict file literal.
    5. REVIEWS fix #1 contract test — pydantic schema accepts all three but strict
       zip emission drops two (schema-vs-zip asymmetry).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from medieval_forge.services.research.overlay import (
    CondadoOverlayEntry,
    _ALL_OVERLAY_FIELDS,
    _ZIP_BOUND_FIELDS,
    merge_overlay,
)

pytestmark = pytest.mark.unit


METADATA: dict = {
    "region": "iberia",
    "map_size": [3840, 2160],
    "bounds": {"lon_min": -13.2, "lon_max": 8.2, "lat_min": 35.4, "lat_max": 44.6},
    "kingdoms": {},
    "duchies": {},
    "condados": [
        {
            "id": "oviedo", "name": "Condado_001", "original_idx": 1,
            "pixel_count": 4500, "pixel_center": [120, 80],
            "lon": -5.84, "lat": 43.36, "duchy": "d_asturias", "kingdom": "asturias",
            "baronies": [],
        },
    ],
    "baronies": [],
}

OVERLAY: dict = {
    "oviedo": {
        "name": "Condado de Oviedo",
        "kingdom_owner": "Reino de Asturias",
        "historical_notes": "Founded 791 AD.",
    },
}


# ---------------------------------------------------------------------------
# Test 1: strict verdict — only name leaks into the merged condado
# ---------------------------------------------------------------------------


def test_zip_bound_fields_with_strict_verdict_drops_kingdom_owner_and_historical_notes() -> None:
    merged = merge_overlay(METADATA, OVERLAY, allowed_fields=frozenset({"name"}))
    c = merged["condados"][0]
    assert c["name"] == "Condado de Oviedo"
    # Not in original metadata, must not appear in merged output under strict.
    assert c.get("kingdom_owner") is None or "kingdom_owner" not in c
    assert c.get("historical_notes") is None or "historical_notes" not in c


# ---------------------------------------------------------------------------
# Test 2: tolerant verdict — all 3 emitted
# ---------------------------------------------------------------------------


def test_zip_bound_fields_with_tolerant_verdict_includes_all_three_fields() -> None:
    tolerant = frozenset({"name", "kingdom_owner", "historical_notes"})
    merged = merge_overlay(METADATA, OVERLAY, allowed_fields=tolerant)
    c = merged["condados"][0]
    assert c["name"] == "Condado de Oviedo"
    assert c["kingdom_owner"] == "Reino de Asturias"
    assert c["historical_notes"] == "Founded 791 AD."


# ---------------------------------------------------------------------------
# Test 3: containment — zip-bound is a subset of all overlay fields
# ---------------------------------------------------------------------------


def test_zip_bound_fields_is_a_frozenset_subset_of_all_overlay_fields() -> None:
    assert isinstance(_ZIP_BOUND_FIELDS, frozenset)
    assert _ZIP_BOUND_FIELDS <= _ALL_OVERLAY_FIELDS


# ---------------------------------------------------------------------------
# Test 4: DRIFT GUARD — overlay.py constant matches Q2 verdict file value
# ---------------------------------------------------------------------------


def test_zip_bound_fields_matches_q2_verdict_file_value() -> None:
    """If the Q2 verdict file changes, overlay.py constant must change with it.

    The test reads the verdict file, extracts the literal `_ZIP_BOUND_FIELDS:`
    Python line, evaluates it, and asserts the value matches the constant
    imported from overlay.py. This catches stale constants after a verdict update.
    """
    # Walk up from this test file to repo root, then to the verdict file.
    # tests/unit/test_overlay_merge_strict_bound.py -> tests/unit -> tests -> backend -> repo
    repo_root = Path(__file__).resolve().parents[3]
    verdict_path = (
        repo_root
        / ".planning"
        / "phases"
        / "07-llm-research-as-opt-in-metadata-layer"
        / "07-Q2-UNITY-LOADER-VERDICT.md"
    )
    assert verdict_path.exists(), f"Verdict file not found at {verdict_path}"
    verdict_text = verdict_path.read_text(encoding="utf-8")
    # Match: _ZIP_BOUND_FIELDS: frozenset[str] = frozenset({...})
    m = re.search(
        r"_ZIP_BOUND_FIELDS:\s*frozenset\[str\]\s*=\s*(frozenset\(\{[^}]*\}\))",
        verdict_text,
    )
    assert m, "Verdict file is missing the _ZIP_BOUND_FIELDS literal Python line"
    verdict_value = eval(m.group(1))  # noqa: S307 — controlled input from verdict file
    assert _ZIP_BOUND_FIELDS == verdict_value, (
        f"overlay.py drift from verdict: {_ZIP_BOUND_FIELDS} != {verdict_value}"
    )


# ---------------------------------------------------------------------------
# Test 5 (REVIEWS fix #1): schema-vs-zip asymmetry contract
# ---------------------------------------------------------------------------


def test_schema_accepts_all_three_fields_but_strict_zip_emission_drops_two() -> None:
    """Pydantic schema tolerates all three; strict zip emission drops two.

    The asymmetry is the documented contract: cache hits and reloads validate
    cleanly under both verdicts because the schema is broader, but the zip-bound
    consumer is narrower under Strict.
    """
    # Pydantic schema accepts all three (validates clean — schema tolerance).
    entry = CondadoOverlayEntry(name="X", kingdom_owner="Y", historical_notes="Z")
    assert entry.name == "X"
    assert entry.kingdom_owner == "Y"
    assert entry.historical_notes == "Z"

    # Zip emission under Strict drops kingdom_owner + historical_notes.
    merged = merge_overlay(
        METADATA,
        {"oviedo": entry.model_dump()},
        allowed_fields=frozenset({"name"}),
    )
    c = merged["condados"][0]
    assert c["name"] == "X"
    assert "kingdom_owner" not in c or c["kingdom_owner"] is None
    assert "historical_notes" not in c or c["historical_notes"] is None
