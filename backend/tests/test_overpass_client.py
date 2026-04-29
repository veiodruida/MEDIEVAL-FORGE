"""Wave 0 RED tests for overpass_client module (Plan 02.1-01, Task 0).

These tests MUST fail until Task 1 creates services/overpass_client.py.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

# --- helpers ------------------------------------------------------------------

EXPECTED_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

_SUCCESS_PAYLOAD = {
    "elements": [
        {"id": 1, "type": "way", "geometry": [{"lon": -1.0, "lat": 46.5}]}
    ]
}


# --- tests --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_query_succeeds_first_mirror(respx_mock):
    """post_query returns dict when first mirror responds 200."""
    import httpx
    from medieval_forge.services import overpass_client

    respx_mock.post(EXPECTED_ENDPOINTS[0]).mock(
        return_value=httpx.Response(200, json=_SUCCESS_PAYLOAD)
    )

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    result = await overpass_client.post_query(
        "[out:json];node(1);out;", queue, None
    )
    assert result == _SUCCESS_PAYLOAD

    messages: list[str] = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    assert any("[Tentativa 1]" in m and "sucesso" in m for m in messages), (
        f"Expected success message in queue. Got: {messages}"
    )


@pytest.mark.asyncio
async def test_post_query_rotates_to_second_mirror_on_503(respx_mock):
    """post_query tries first endpoint (503), then second (200)."""
    import httpx
    from medieval_forge.services import overpass_client

    respx_mock.post(EXPECTED_ENDPOINTS[0]).mock(
        return_value=httpx.Response(503)
    )
    respx_mock.post(EXPECTED_ENDPOINTS[1]).mock(
        return_value=httpx.Response(200, json=_SUCCESS_PAYLOAD)
    )

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    result = await overpass_client.post_query(
        "[out:json];node(1);out;", queue, None
    )
    assert result == _SUCCESS_PAYLOAD

    messages: list[str] = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    combined = " ".join(messages)
    assert "[Tentativa 1]" in combined, f"Expected attempt 1 in messages: {messages}"
    assert "[Tentativa 2]" in combined, f"Expected attempt 2 in messages: {messages}"


@pytest.mark.asyncio
async def test_post_query_honors_stop_event():
    """post_query raises CancelledError immediately when stop_event is pre-set."""
    from medieval_forge.services import overpass_client

    stop = asyncio.Event()
    stop.set()  # already stopped before calling

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    with pytest.raises(asyncio.CancelledError, match="ingest stopped by user"):
        await overpass_client.post_query(
            "[out:json];node(1);out;", queue, None, stop_event=stop
        )

    # No HTTP calls should have been made — queue should be empty
    assert queue.empty()


def test_overpass_endpoints_list_has_three_mirrors():
    """OVERPASS_ENDPOINTS is the canonical list of three Overpass mirrors."""
    from medieval_forge.services import overpass_client

    assert overpass_client.OVERPASS_ENDPOINTS == EXPECTED_ENDPOINTS


def test_ingest_osm_uses_overpass_client():
    """ingest_osm source code references overpass_client (delegation check)."""
    from medieval_forge.services import ingest_osm

    source = inspect.getsource(ingest_osm)
    assert "overpass_client" in source, (
        "ingest_osm.py must import or reference overpass_client"
    )
