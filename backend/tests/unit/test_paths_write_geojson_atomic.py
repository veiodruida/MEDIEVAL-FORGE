"""Unit tests for `_write_geojson_atomic` after the Plan 03-01 lift.

The helper used to live in ``services/ingest_runner.py``; this plan moves it
to ``services/paths.py`` so Phase 03 Plan 07 can delete ``ingest_runner.py``
cleanly. The legacy import path stays green via a re-export stub at
``ingest_runner.py`` (kept for tests + Phase 02 callsites until Plan 07).
"""
from __future__ import annotations

import json

import pytest


def test_canonical_import_path_works():
    """`_write_geojson_atomic` is importable from `services.paths`."""
    from medieval_forge.services.paths import _write_geojson_atomic
    assert callable(_write_geojson_atomic)


def test_legacy_import_path_still_works_via_reexport():
    """The old `ingest_runner` import keeps working — Plan 07 will delete it."""
    from medieval_forge.services.ingest_runner import _write_geojson_atomic as legacy
    from medieval_forge.services.paths import _write_geojson_atomic as canonical
    assert legacy is canonical


def test_write_creates_valid_json_that_roundtrips(tmp_path):
    """Writing a FeatureCollection produces a file whose JSON content roundtrips."""
    from medieval_forge.services.paths import _write_geojson_atomic
    out = tmp_path / "out.geojson"
    payload = {"type": "FeatureCollection", "features": []}
    _write_geojson_atomic(out, payload)

    assert out.is_file()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == payload


def test_write_to_nonexistent_parent_raises(tmp_path):
    """Helper does NOT auto-mkdir — preserves original ingest_runner semantics."""
    from medieval_forge.services.paths import _write_geojson_atomic
    out = tmp_path / "does_not_exist" / "out.geojson"
    payload = {"type": "FeatureCollection", "features": []}
    with pytest.raises((FileNotFoundError, OSError)):
        _write_geojson_atomic(out, payload)
