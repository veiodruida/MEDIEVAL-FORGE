"""services/llm/ - 2-provider plugin registry (Claude + Ollama)."""
from .base import (
    ApiKeyAuth,
    AuthMethod,
    CliAuth,
    HealthStatus,
    LLMProvider,
    NoAuth,
)
from .claude import ClaudeProvider
from .llamacpp import LlamaCppProvider, LlamaCppProviderError
from .ollama import OllamaProvider
from .prompt import build_map_research_prompt
from .registry import PROVIDERS, get, list_providers, register
from .retry import ResearchValidationError, run_with_retry
from .sanitize import escape_condado_name
from .schemas import MapResearchResult, ResearchResult, parse_research_json

# Plan 07-04 Task 4 — import-time registration (D-05 + Discretion #10 + RESEARCH §Pattern 2).
# Plan 07.1-03 — LlamaCppProvider added as third entry (D-V3-04 rewrite under v3 patterns).
# Order is stable (alphabetical) so list_providers() returns ['claude', 'llamacpp', 'ollama']
# after sort, regardless of import side-effects.
register(ClaudeProvider())
register(LlamaCppProvider())
register(OllamaProvider())

__all__ = [
    "ApiKeyAuth",
    "AuthMethod",
    "ClaudeProvider",
    "CliAuth",
    "HealthStatus",
    "LLMProvider",
    "LlamaCppProvider",
    "LlamaCppProviderError",
    "NoAuth",
    "MapResearchResult",
    "OllamaProvider",
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
