"""Tests for INGEST-01..04 and T-SSRF guards."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


# ---------- T-SSRF: validators reject malformed input ----------

def test_validate_qid_rejects_non_qid_strings():
    from medieval_forge.services.ingest_wikidata import validate_qid

    validate_qid("Q29")  # ok
    validate_qid("Q1234567")  # ok
    for bad in ["q29", "spain", "29", "Q", "../etc/passwd", "Q29; DROP TABLE"]:
        with pytest.raises(ValueError):
            validate_qid(bad)


def test_validate_iso_country_rejects_bad_format():
    from medieval_forge.services.ingest_osm import validate_iso_country

    validate_iso_country("ES")
    validate_iso_country("PT")
    for bad in ["es", "ESP", "E", "12", "../", "ES; DROP"]:
        with pytest.raises(ValueError):
            validate_iso_country(bad)


# ---------- INGEST-01: Wikidata pagination ----------

class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    """Yields a sequence of fake JSON payloads for successive .get() calls."""

    def __init__(self, payloads: list[dict[str, Any]]):
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if not self._payloads:
            return _FakeResponse({"results": {"bindings": []}})
        return _FakeResponse(self._payloads.pop(0))

    async def post(self, url, data=None):
        return _FakeResponse(self._payloads.pop(0) if self._payloads else {})


def _binding(qid_num: int):
    return {
        "item": {"value": f"http://www.wikidata.org/entity/Q{qid_num}"},
        "itemLabel": {"value": f"Place {qid_num}"},
        "lat": {"value": "40.0"},
        "lon": {"value": "-3.0"},
    }


async def test_wikidata_pagination():
    from medieval_forge.services.ingest_wikidata import fetch_municipalities

    # Two pages: first 500 items, second 200 items (terminates).
    page1 = {"results": {"bindings": [_binding(i) for i in range(500)]}}
    page2 = {"results": {"bindings": [_binding(500 + i) for i in range(200)]}}
    fake = _FakeClient([page1, page2])
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    result = await fetch_municipalities(
        "Q29", queue, page_size=500, client_factory=lambda: fake
    )

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 700
    # SSE messages: 2 "Fetching page" + 1 "complete" = 3 puts (plus possibly intermediate)
    assert queue.qsize() >= 3
    # Verify pagination params advanced.
    assert len(fake.calls) == 2
    assert "OFFSET 0" in fake.calls[0]["params"]["query"]
    assert "OFFSET 500" in fake.calls[1]["params"]["query"]
    # T-SSRF: query contains ONLY validated QID, never raw user input.
    assert "wd:Q29" in fake.calls[0]["params"]["query"]


# ---------- INGEST-02: OSM fallback ----------

async def test_osm_fallback():
    from medieval_forge.services.ingest_osm import fetch_municipalities

    overpass_payload = {
        "elements": [
            {
                "type": "relation",
                "id": 1,
                "tags": {"name": "Province A", "admin_level": "8", "boundary": "administrative"},
                "members": [
                    {
                        "role": "outer",
                        "geometry": [
                            {"lon": 0.0, "lat": 0.0},
                            {"lon": 1.0, "lat": 0.0},
                            {"lon": 1.0, "lat": 1.0},
                            {"lon": 0.0, "lat": 1.0},
                        ],
                    }
                ],
            },
            {
                "type": "node",  # Should be filtered out
                "id": 2,
            },
        ]
    }
    fake = _FakeClient([overpass_payload])
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    result = await fetch_municipalities(
        "ES", queue, client_factory=lambda: fake
    )

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    feat = result["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["name"] == "Province A"
    assert feat["geometry"]["coordinates"][0][0] == feat["geometry"]["coordinates"][0][-1]  # closed


# ---------- Tasks 3 and 4 tests (stubs until implemented) ----------

@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 3")
async def test_geojson_written(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
async def test_sse_stream(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
async def test_sse_stream_invalid_uuid_returns_400(client):
    pass
