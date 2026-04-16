"""Tests for INGEST-01..04 and T-SSRF guards.

Stubs in Wave 0 of Plan 01-03; implemented in Tasks 2, 3, 4.
"""
import pytest


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
async def test_wikidata_pagination():
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
def test_validate_qid_rejects_non_qid_strings():
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
async def test_osm_fallback():
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
def test_validate_iso_country_rejects_bad_format():
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 3")
async def test_geojson_written(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
async def test_sse_stream(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
async def test_sse_stream_invalid_uuid_returns_400(client):
    pass
