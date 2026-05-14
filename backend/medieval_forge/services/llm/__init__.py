"""services/llm/ - 2-provider plugin registry (Claude + Ollama)."""
from .base import (
    ApiKeyAuth,
    AuthMethod,
    CliAuth,
    HealthStatus,
    LLMProvider,
    NoAuth,
)
from .prompt import build_map_research_prompt
from .registry import PROVIDERS, get, list_providers, register
from .retry import ResearchValidationError, run_with_retry
from .schemas import MapResearchResult, ResearchResult, parse_research_json

__all__ = [
    "ApiKeyAuth",
    "AuthMethod",
    "CliAuth",
    "HealthStatus",
    "LLMProvider",
    "NoAuth",
    "MapResearchResult",
    "PROVIDERS",
    "ResearchResult",
    "ResearchValidationError",
    "build_map_research_prompt",
    "get",
    "list_providers",
    "parse_research_json",
    "register",
    "run_with_retry",
]
