"""LLM adapter package for Medieval Forge.

Exports the provider registry and base types.
"""
from .registry import PROVIDERS
from .base import LLMProvider, AuthMethod, HealthStatus

__all__ = ["PROVIDERS", "LLMProvider", "AuthMethod", "HealthStatus"]
