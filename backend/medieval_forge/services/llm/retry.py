# Literal port from commit 87f8aab~1; see D-02 in 07-CONTEXT.md.
# DO NOT MODIFY behaviorally. Allowed edits: import-line adjustments only.
"""Shared 3-retry validation loop for LLM providers.

D-27/D-28: Pydantic extra='forbid' catches malformed LLM output; retry loop
appends the validation error to the prompt for self-correction.
D-29: After max_retries failures, raises ResearchValidationError.
"""
from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, ValidationError

from .base import LLMProvider


class ResearchValidationError(Exception):
    """Raised after all retry attempts are exhausted."""

    def __init__(self, last_error: str, last_raw: str | None):
        super().__init__(last_error)
        self.last_error = last_error
        self.last_raw = last_raw


async def run_with_retry(
    provider: LLMProvider,
    prompt_base: str,
    schema: type[BaseModel],
    credentials: dict | None,
    queue: asyncio.Queue[str | None] | None = None,
    max_retries: int = 3,
) -> BaseModel:
    """Call provider.research up to max_retries times.

    On each ValidationError / ValueError / JSONDecodeError:
    - appends the error message to the prompt for self-correction
    - emits a progress message to queue if provided

    Raises ResearchValidationError after max_retries consecutive failures.
    """
    prompt = prompt_base
    last_error: str = ""
    last_raw: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await provider.research(prompt, schema, credentials, queue)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            # Provider may attach raw response as exc.raw_response when applicable.
            last_raw = getattr(exc, "raw_response", None)

            if queue is not None:
                await queue.put(
                    f"data: Tentativa {attempt}/{max_retries}: {last_error[:80]}\n\n"
                )

            correction = (
                f"\n\nYour previous response failed validation with: {last_error}. "
                "Return corrected JSON only, no prose."
            )
            prompt = prompt_base + correction

    raise ResearchValidationError(last_error, last_raw)
