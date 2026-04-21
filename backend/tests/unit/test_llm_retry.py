"""Tests for run_with_retry — RESEARCH-03."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from medieval_forge.services.llm.retry import ResearchValidationError, run_with_retry
from medieval_forge.services.llm.schemas import ResearchResult

_VALID_RESULT = ResearchResult.model_validate(
    {
        "kingdoms": {"k1": "Kingdom"},
        "duchies": {"d1": ["k1", "Duchy"]},
        "condados_assignment": [
            {"condado_id": "c1", "kingdom_id": "k1", "duchy_id": "d1"}
        ],
        "baronies": {"c1": [{"name": "B", "lon": 1.0, "lat": 2.0}]},
    }
)


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    provider = MagicMock()
    provider.research = AsyncMock(return_value=_VALID_RESULT)
    result = await run_with_retry(provider, "prompt", ResearchResult, None, None)
    assert result == _VALID_RESULT
    provider.research.assert_called_once()


@pytest.mark.asyncio
async def test_retry_appends_error_message_on_validation_failure():
    call_prompts: list[str] = []

    async def _research(prompt, schema, credentials, queue):
        call_prompts.append(prompt)
        if len(call_prompts) < 3:
            raise ValueError("bad json")
        return _VALID_RESULT

    provider = MagicMock()
    provider.research = _research

    result = await run_with_retry(provider, "original", ResearchResult, None, None)
    assert result == _VALID_RESULT
    # 2nd and 3rd call prompts must include the validation error phrase
    assert "Your previous response failed validation with:" in call_prompts[1]
    assert "Your previous response failed validation with:" in call_prompts[2]


@pytest.mark.asyncio
async def test_retry_raises_after_three_failures():
    call_count = 0

    async def _always_fail(prompt, schema, credentials, queue):
        nonlocal call_count
        call_count += 1
        raise ValueError("always fails")

    provider = MagicMock()
    provider.research = _always_fail

    with pytest.raises(ResearchValidationError):
        await run_with_retry(provider, "prompt", ResearchResult, None, None, max_retries=3)

    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_emits_progress_to_queue_when_provided():
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    call_count = 0

    async def _fail_twice(prompt, schema, credentials, q):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("fail")
        return _VALID_RESULT

    provider = MagicMock()
    provider.research = _fail_twice

    await run_with_retry(provider, "prompt", ResearchResult, None, queue, max_retries=3)

    # Collect all queued messages
    messages: list[str] = []
    while not queue.empty():
        msg = queue.get_nowait()
        if msg is not None:
            messages.append(msg)

    # Must have emitted at least one retry message
    assert any("Tentativa" in m or "Retry" in m or "1/" in m for m in messages), (
        f"No retry progress messages found in: {messages}"
    )
