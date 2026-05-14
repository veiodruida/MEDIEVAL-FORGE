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
from .ollama import OllamaProvider
from .prompt import build_map_research_prompt
from .registry import PROVIDERS, get, list_providers, register
from .retry import ResearchValidationError, run_with_retry
from .sanitize import escape_condado_name
from .schemas import MapResearchResult, ResearchResult, parse_research_json

# Plan 07-04 Task 4 — import-time registration (D-05 + Discretion #10 + RESEARCH §Pattern 2).
# Order is stable (claude first) so list_providers() returns ['claude', 'ollama']
# after sort, regardless of import side-effects.
register(ClaudeProvider())
register(OllamaProvider())

__all__ = [
    "ApiKeyAuth",
    "AuthMethod",
    "ClaudeProvider",
    "CliAuth",
    "HealthStatus",
    "LLMProvider",
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
