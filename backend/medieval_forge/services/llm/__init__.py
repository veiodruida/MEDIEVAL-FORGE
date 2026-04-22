"""Multi-provider LLM adapter layer (Phase 3 — D-01)."""
from .base import (
    LLMProvider,
    HealthStatus,
    AuthMethod,
    ApiKeyAuth,
    OAuthAuth,
    CliAuth,
    NoAuth,
)
from .manual import ManualProvider
from .schemas import ResearchResult, CondadoAssignment, Barony
from .registry import PROVIDERS
from .retry import run_with_retry, ResearchValidationError

__all__ = [
    "LLMProvider",
    "HealthStatus",
    "AuthMethod",
    "ApiKeyAuth",
    "OAuthAuth",
    "CliAuth",
    "NoAuth",
    "ManualProvider",
    "ResearchResult",
    "CondadoAssignment",
    "Barony",
    "PROVIDERS",
    "run_with_retry",
    "ResearchValidationError",
]
