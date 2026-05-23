"""services/llm/ - plugin registry (Claude + Ollama + Llama.cpp + cloud aggregators)."""
from .base import (
    ApiKeyAuth,
    AuthMethod,
    CliAuth,
    HealthStatus,
    LLMProvider,
    NoAuth,
)
from .claude import ClaudeProvider
from .gemini import GeminiProvider, GeminiProviderError
from .llamacpp import LlamaCppProvider, LlamaCppProviderError
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider, OpenAIProviderError
from .openrouter import OpenRouterProvider, OpenRouterProviderError
from .prompt import build_map_research_prompt
from .registry import PROVIDERS, get, list_providers, register
from .retry import ResearchValidationError, run_with_retry
from .sanitize import escape_condado_name
from .schemas import MapResearchResult, ResearchResult, parse_research_json

# Plan 07-04 Task 4 — import-time registration (D-05 + Discretion #10 + RESEARCH §Pattern 2).
# Plan 07.1-03 — LlamaCppProvider added as third entry (D-V3-04 rewrite under v3 patterns).
# Plan 07.2 (UAT 2026-05-23) — cloud providers added (OpenRouter, OpenAI, Gemini).
# Order is stable (alphabetical) so list_providers() returns a deterministic list
# regardless of import side-effects.
register(ClaudeProvider())
register(GeminiProvider())
register(LlamaCppProvider())
register(OllamaProvider())
register(OpenAIProvider())
register(OpenRouterProvider())

__all__ = [
    "ApiKeyAuth",
    "AuthMethod",
    "ClaudeProvider",
    "CliAuth",
    "GeminiProvider",
    "GeminiProviderError",
    "HealthStatus",
    "LLMProvider",
    "LlamaCppProvider",
    "LlamaCppProviderError",
    "MapResearchResult",
    "NoAuth",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenAIProviderError",
    "OpenRouterProvider",
    "OpenRouterProviderError",
    "PROVIDERS",
    "ResearchResult",
    "ResearchValidationError",
    "build_map_research_prompt",
    "escape_condado_name",
    "get",
    "list_providers",
    "parse_research_json",
    "register",
    "run_with_retry",
]
