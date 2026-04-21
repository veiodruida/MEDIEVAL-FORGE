"""Provider registry for the LLM adapter layer.

PROVIDERS maps provider_id strings to LLMProvider instances.
Adding a new provider = create adapter file + add one line here (D-04).

Known providers (Phase 3):
  claude  — Anthropic Claude API + CLI piggyback
  openai  — OpenAI GPT API
  gemini  — Google Gemini API + OAuth
  ollama  — Local Ollama (no auth)
"""
from __future__ import annotations

from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

PROVIDERS: dict[str, object] = {
    "claude": ClaudeProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "ollama": OllamaProvider(),
}
