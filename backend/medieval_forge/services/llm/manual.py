"""Manual (copy/paste) provider — no network, no credentials.

User copies the prompt we build, pastes into any external chat, pastes the
response back into the manual endpoint. Never invoked via the SSE runner.
"""
from __future__ import annotations
import asyncio
from pydantic import BaseModel
from .base import HealthStatus, NoAuth


class ManualProvider:
    provider_id = "manual"
    display_name = "Manual (Copiar/Colar)"
    auth_methods = [NoAuth()]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        return HealthStatus(healthy=True, message="Sem necessidade de conexão")

    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue | None,
    ) -> BaseModel:
        raise NotImplementedError(
            "ManualProvider does not use the SSE research() path. "
            "Use POST /projects/{id}/research/manual instead."
        )
