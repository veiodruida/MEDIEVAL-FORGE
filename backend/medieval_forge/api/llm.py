"""LLM provider discovery endpoints (RESEARCH-05, RESEARCH-09, D-05, D-17).

GET /llm/providers  — machine-readable list of all registered providers (auto-discovered from PROVIDERS)
GET /llm/health     — per-provider health check results

Both endpoints iterate PROVIDERS.values() so adding a new provider adapter
automatically appears here — no code changes needed in this file (RESEARCH-09).
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..services.llm import PROVIDERS
from ..services.llm.auth import resolve_credentials
from ..services.research_runner import PROVIDER_DEFAULT_MODEL

router = APIRouter(tags=["llm"])


@router.get("/llm/providers")
async def list_providers(request: Request) -> list[dict]:
    """Return all registered providers with auth status and health.

    Response shape per D-05:
      [{provider_id, display_name, auth_methods, configured, healthy, default_model}, ...]

    configured = bool(resolve_credentials) or provider is Ollama (NoAuth)
    healthy    = result of provider.health_check(credentials)
    """
    out: list[dict] = []
    for pid, prov in PROVIDERS.items():
        creds = resolve_credentials(pid, request.app.state)
        configured = bool(creds) or pid == "ollama"
        try:
            health = await prov.health_check(creds or None)
            healthy = bool(health.healthy)
        except Exception:
            healthy = False
        out.append({
            "provider_id": prov.provider_id,
            "display_name": prov.display_name,
            "auth_methods": [m.model_dump() for m in prov.auth_methods],
            "configured": configured,
            "healthy": healthy,
            "default_model": PROVIDER_DEFAULT_MODEL.get(pid, ""),
        })
    return out


@router.get("/llm/health")
async def health_all(request: Request) -> dict:
    """Return per-provider health status dict.

    Response shape:
      {provider_id: {healthy: bool, message: str}, ...}
    """
    result: dict = {}
    for pid, prov in PROVIDERS.items():
        creds = resolve_credentials(pid, request.app.state)
        try:
            h = await prov.health_check(creds or None)
            result[pid] = {"healthy": h.healthy, "message": h.message}
        except Exception as e:
            result[pid] = {"healthy": False, "message": str(e)}
    return result
