"""LLM provider discovery endpoints (RESEARCH-05, RESEARCH-09, D-05, D-17).

GET /llm/providers       — list all registered providers (auto-discovered from PROVIDERS)
GET /llm/health          — per-provider health check results
GET /llm/ollama/models   — list models available on the local Ollama instance
POST /llm/ollama/model   — set the active Ollama model for this session
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.llm import PROVIDERS
from ..services.llm.auth import resolve_credentials
from ..services.llm.ollama import OLLAMA_HOST
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


@router.get("/llm/ollama/models")
async def list_ollama_models(request: Request) -> dict:
    """Return models installed on the local Ollama instance.

    Response shape:
      {"models": ["llama3.2:3b", "qwen2.5:14b", ...], "selected": "qwen2.5:14b" | null,
       "default": "qwen2.5:7b", "healthy": bool, "message": str | null}
    """
    from ollama import AsyncClient

    default = PROVIDER_DEFAULT_MODEL.get("ollama", "")
    creds = getattr(request.app.state, "credentials", {}).get("ollama") or {}
    selected = creds.get("model")

    try:
        client = AsyncClient(host=OLLAMA_HOST)
        resp = await asyncio.wait_for(client.list(), timeout=3.0)
        models_data = resp.get("models") if isinstance(resp, dict) else getattr(resp, "models", [])
        names: list[str] = []
        for m in models_data or []:
            name = m.get("name") if isinstance(m, dict) else getattr(m, "model", None) or getattr(m, "name", None)
            if name:
                names.append(name)
        return {
            "models": names,
            "selected": selected,
            "default": default,
            "healthy": True,
            "message": None,
        }
    except asyncio.TimeoutError:
        return {"models": [], "selected": selected, "default": default, "healthy": False,
                "message": f"Ollama não respondeu em {OLLAMA_HOST} (timeout 3s). Inicia 'ollama serve'."}
    except Exception as exc:
        return {"models": [], "selected": selected, "default": default, "healthy": False,
                "message": f"Falha ao conectar no Ollama: {exc}"}


class OllamaModelPayload(BaseModel):
    model: str


@router.post("/llm/ollama/model")
async def set_ollama_model(payload: OllamaModelPayload, request: Request) -> dict:
    """Set the active Ollama model for this session.

    Stores the choice in app.state.credentials["ollama"] = {"model": ...} so that
    research_runner and the Ollama provider pick it up. Never written to disk.
    """
    name = payload.model.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty model name")

    creds = getattr(request.app.state, "credentials", None)
    if creds is None:
        request.app.state.credentials = {}
        creds = request.app.state.credentials
    creds["ollama"] = {"model": name, "source": "session"}
    return {"ok": True, "model": name}
