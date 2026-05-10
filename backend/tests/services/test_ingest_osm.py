"""Tests for ingest_osm: infinite retry loop, stop_event plumbing, and endpoint list."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, payload: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload or {})
    # Simulate raise_for_status for non-2xx (only needed on success path, keep simple)
    if status_code >= 400:
        import httpx
        resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=resp
            )
        )
    else:
        resp.raise_for_status = MagicMock(return_value=None)
    return resp


class _StubClient:
    """Async context manager wrapping an AsyncMock .post method.

    ``side_effects`` is a list of either:
    - a mock response (returned by post), or
    - an exception instance (raised by post).
    Once exhausted, always returns the last item (or raises last exc).
    """

    def __init__(self, side_effects: list):
        self._effects = list(side_effects)
        self.post = AsyncMock(side_effect=self._pop_effect)
        self.call_count = 0

    async def _pop_effect(self, *args, **kwargs):
        self.call_count += 1
        if self._effects:
            effect = self._effects.pop(0)
        else:
            # fallback: repeat last state — never-ending 504
            effect = _make_response(504)
        if isinstance(effect, BaseException):
            raise effect
        return effect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Test 1: OVERPASS_ENDPOINTS list
# ---------------------------------------------------------------------------

def test_overpass_endpoints_are_three_live_mirrors():
    """OVERPASS_ENDPOINTS must list exactly the 3 verified live mirrors."""
    from medieval_forge.services.ingest_osm import OVERPASS_ENDPOINTS

    assert len(OVERPASS_ENDPOINTS) == 3
    joined = " ".join(OVERPASS_ENDPOINTS)
    # Must contain all 3 live mirrors
    assert "overpass-api.de" in joined
    assert "overpass.private.coffee" in joined
    assert "overpass.kumi.systems" in joined
    # Must NOT contain dead mirrors
    assert "openstreetmap.ru" not in joined
    assert "maps.mail.ru" not in joined


# ---------------------------------------------------------------------------
# Test 2: All 504s — loop keeps cycling past 3 attempts until stop_event
# ---------------------------------------------------------------------------

async def test_post_query_retries_past_three_endpoints_then_stops():
    """When all mirrors return 504, _post_query keeps cycling until stop_event is set."""
    from medieval_forge.services.ingest_osm import _post_query, OVERPASS_ENDPOINTS

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop_event = asyncio.Event()

    # Track how many times post() is called. After 5 calls (> len(OVERPASS_ENDPOINTS)),
    # set the stop_event so the loop exits.
    call_log: list[int] = []

    class _CountingClient(_StubClient):
        async def _pop_effect(self, *args, **kwargs):
            self.call_count += 1
            call_log.append(self.call_count)
            if self.call_count >= 5:
                stop_event.set()
            return _make_response(504)

    client = _CountingClient([])

    with pytest.raises(asyncio.CancelledError):
        await _post_query(
            query="[out:json];",
            queue=queue,
            client_factory=lambda: client,
            stop_event=stop_event,
        )

    # Must have looped past 3 (one full pass through all endpoints)
    assert len(call_log) >= 4, f"Expected > 3 attempts, got {len(call_log)}"


# ---------------------------------------------------------------------------
# Test 3: stop_event set before first iteration — no HTTP call made
# ---------------------------------------------------------------------------

async def test_post_query_honours_pre_set_stop_event():
    """When stop_event is already set, _post_query raises CancelledError immediately."""
    from medieval_forge.services.ingest_osm import _post_query

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop_event = asyncio.Event()
    stop_event.set()  # pre-set

    mock_client = _StubClient([])

    with pytest.raises(asyncio.CancelledError):
        await _post_query(
            query="[out:json];",
            queue=queue,
            client_factory=lambda: mock_client,
            stop_event=stop_event,
        )

    # No HTTP calls should have been made
    assert mock_client.call_count == 0, "Expected 0 HTTP calls when stop_event pre-set"


# ---------------------------------------------------------------------------
# Test 4: Second attempt succeeds — returns payload, emits [Tentativa N] SSE
# ---------------------------------------------------------------------------

async def test_post_query_succeeds_on_second_attempt():
    """When the second attempt succeeds, returns payload and emits Tentativa SSE messages."""
    from medieval_forge.services.ingest_osm import _post_query

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stop_event = asyncio.Event()

    success_payload = {"elements": [{"type": "relation", "id": 1}]}
    client = _StubClient([
        _make_response(504),
        _make_response(200, success_payload),
    ])

    result = await _post_query(
        query="[out:json];",
        queue=queue,
        client_factory=lambda: client,
        stop_event=stop_event,
    )

    assert result == success_payload

    # Collect all SSE messages
    messages: list[str] = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    combined = " ".join(messages)
    # Must contain [Tentativa 1] for the 504 attempt
    assert "[Tentativa 1]" in combined or "Tentativa 1" in combined
    # Must contain [Tentativa 2] for the successful attempt
    assert "[Tentativa 2]" in combined or "Tentativa 2" in combined


