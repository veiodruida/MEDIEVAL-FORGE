"""Wave 0 retry-loop coverage for services/llm/retry.py (Phase 07-03 Task 2).

Validates the 3-retry self-correction loop:
- Success on attempt 2 after attempt 1 raises ValueError (simulated invalid JSON).
- Failure after 3 consecutive ValidationError-style raises (ResearchValidationError).
- Error message gets appended to the prompt for self-correction on subsequent attempts.

Uses a hand-rolled fake provider (AsyncMock-equivalent) so behavior is observable
in the prompt-mutation assertion (Test 3).
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from medieval_forge.services.llm.retry import (
    ResearchValidationError,
    run_with_retry,
)


class _ToyResult(BaseModel):
    value: int


class _FakeProvider:
    """Stand-in LLMProvider whose `research` cycles through a script of side-effects.

    Each entry in `script` is either an Exception (raised) or a BaseModel (returned).
    Records every prompt it sees so the test can inspect prompt mutation.
    """

    provider_id = "fake"
    display_name = "Fake"
    auth_methods: list[Any] = []

    def __init__(self, script: list[Any]):
        self._script = list(script)
        self.prompts_seen: list[str] = []

    async def health_check(self, credentials: dict | None):  # pragma: no cover
        raise NotImplementedError

    async def research(
        self,
        prompt: str,
        schema: Any,
        credentials: dict | None,
        queue: Any,
    ) -> Any:
        self.prompts_seen.append(prompt)
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.mark.asyncio
async def test_run_with_retry_succeeds_on_second_attempt_when_first_returns_invalid_json():
    success = _ToyResult(value=42)
    provider = _FakeProvider(
        script=[
            ValueError("invalid JSON: missing closing brace at line 7"),
            success,
        ]
    )

    result = await run_with_retry(
        provider=provider,
        prompt_base="base prompt",
        schema=_ToyResult,
        credentials=None,
        queue=None,
        max_retries=3,
    )

    assert result is success
    assert len(provider.prompts_seen) == 2  # exactly 2 calls — succeeded on attempt 2


@pytest.mark.asyncio
async def test_run_with_retry_raises_after_3_consecutive_validation_errors():
    provider = _FakeProvider(
        script=[
            ValueError("attempt 1 bad json"),
            ValueError("attempt 2 bad json"),
            ValueError("attempt 3 bad json"),
        ]
    )

    with pytest.raises(ResearchValidationError) as excinfo:
        await run_with_retry(
            provider=provider,
            prompt_base="base prompt",
            schema=_ToyResult,
            credentials=None,
            queue=None,
            max_retries=3,
        )

    assert "attempt 3 bad json" in excinfo.value.last_error
    assert len(provider.prompts_seen) == 3  # hard cap honoured


@pytest.mark.asyncio
async def test_run_with_retry_appends_error_to_subsequent_prompt():
    success = _ToyResult(value=7)
    provider = _FakeProvider(
        script=[
            ValueError("MISSING_FIELD_BARONIES"),
            success,
        ]
    )
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    await run_with_retry(
        provider=provider,
        prompt_base="ORIGINAL_PROMPT_BODY",
        schema=_ToyResult,
        credentials=None,
        queue=queue,
        max_retries=3,
    )

    # First call sees the bare prompt; second call sees prompt + correction suffix.
    assert provider.prompts_seen[0] == "ORIGINAL_PROMPT_BODY"
    assert provider.prompts_seen[1].startswith("ORIGINAL_PROMPT_BODY")
    assert "MISSING_FIELD_BARONIES" in provider.prompts_seen[1]
    assert "failed validation" in provider.prompts_seen[1]

    # Queue received PT-BR "Tentativa 1/3: ..." progress event (Pitfall 9).
    msg = await queue.get()
    assert msg is not None
    assert "Tentativa 1/3" in msg
