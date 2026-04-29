"""Shared Overpass POST helper. 3-mirror infinite retry + stop_event cancellation.

Single source of truth per D-02.
Plans 02-05 all use post_query() — no duplication of the mirror list.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx

log = logging.getLogger(__name__)

# Endpoints públicos do Overpass API em ordem de preferência.
# Verificados live em 2026-04-28:
#   - overpass-api.de: instância oficial principal
#   - overpass.private.coffee: mirror europeu independente
#   - overpass.kumi.systems: mirror alemão confiável
OVERPASS_ENDPOINTS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

_TIMEOUT_S: float = 180.0  # 3 minutes


async def post_query(
    query: str,
    queue: asyncio.Queue[str | None],
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
    *,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Loop infinito pelos endpoints Overpass até um responder com sucesso ou stop_event ser setado.

    Cicla OVERPASS_ENDPOINTS indefinidamente (attempt % len). Emite mensagens
    SSE [Tentativa N] para cada tentativa. Quando stop_event é setado, levanta
    asyncio.CancelledError para sinalizar cancelamento pelo usuário.

    Backoff: min(30, 5 * attempt) segundos após respostas 5xx. Erros de rede
    (timeout/connect) passam imediatamente para o próximo endpoint sem espera.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    def _factory() -> httpx.AsyncClient:
        if client_factory is not None:
            return client_factory()
        return httpx.AsyncClient(timeout=_TIMEOUT_S)

    retryable = {406, 408, 429, 502, 503, 504}
    attempt = 0

    while not stop_event.is_set():
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        attempt += 1
        await queue.put(f"data: [Tentativa {attempt}] {endpoint} — aguardando resposta...\n\n")
        try:
            async with _factory() as client:
                resp = await asyncio.wait_for(
                    client.post(
                        endpoint,
                        data={"data": query},
                        headers={"Accept": "application/json"},
                    ),
                    timeout=_TIMEOUT_S,
                )

                if resp.status_code >= 500 or resp.status_code in retryable:
                    wait_s = min(30, 5 * attempt)
                    await queue.put(
                        f"data: [Tentativa {attempt}] {endpoint} retornou {resp.status_code}. "
                        f"Aguardando {wait_s}s...\n\n"
                    )
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=wait_s)
                    except (asyncio.TimeoutError, TimeoutError):
                        pass  # backoff elapsed, continue loop
                    continue

                resp.raise_for_status()
                payload = resp.json()
                elem_count = len(payload.get("elements", []))
                await queue.put(
                    f"data: [Tentativa {attempt}] {endpoint} — sucesso ({elem_count} elementos).\n\n"
                )
                return payload

        except (asyncio.TimeoutError, TimeoutError):
            await queue.put(
                f"data: [Tentativa {attempt}] Timeout em {endpoint}. Tentando próximo...\n\n"
            )
            continue
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await queue.put(
                f"data: [Tentativa {attempt}] Falha de rede ({exc.__class__.__name__}) "
                f"em {endpoint}. Tentando próximo...\n\n"
            )
            continue

    raise asyncio.CancelledError("ingest stopped by user")
