"""LLM provider registry — maps provider_id -> LLMProvider instance.

To add a new provider: create an adapter module file and add one line here.
No other files need to change (RESEARCH-09).
"""
from __future__ import annotations

from .base import LLMProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider

# PROVIDERS: populated at import time; consumed by api/research.py (Plan 03)
PROVIDERS: dict[str, LLMProvider] = {
    "claude": ClaudeProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "ollama": OllamaProvider(),
}
