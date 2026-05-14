"""SSE research orchestrator (Plan 07-07b Task 1).

Mirrors `api/v3/generate.py` SSE pattern:
- `_RUN_QUEUES[project_id] -> asyncio.Queue[str | None]` producer/consumer pair.
- `_RUN_TASKS[project_id] -> asyncio.Task` producer task slot.
- `_emit(queue, event_type, stage, message, progress)` envelope writer.
- `finally:` block puts the None sentinel AND evicts both maps (WR-02 fix /
  Pitfall 7 — late subscribers see 404, not a dangling queue).

Single-flight gate: research has its OWN `_RUN_QUEUES` map (independent from
generate/render's `_run_state.py`) so a project may run /generate and /research
concurrently. Within research a second `start_research` for the same project
raises `SingleFlightError` (the api/v3 layer maps that to HTTP 409).

REVIEWS fix #2 — meta sidecar dual timestamps:
- `generated_at` (DB row, propagated through cache-hit path) -> when the LLM
  originally produced the payload.
- `applied_at` (runner-write moment, ALWAYS = now()) -> when this overlay was
  written to the project.

On the fresh-run path both equal the runner-write moment. On the cache-hit
path `generated_at` is read from `ResearchCache.generated_at` (Plan 07a's
`cache_get_with_generated_at`). The UI (Plan 09b) chooses single-line vs
two-line microcopy based on equality.

Pitfall 1 + Example 3: both overlay AND meta sidecar are written via
`_write_json_atomic(path, data)` (tmp+replace) so a torn write at process
exit never leaves a half-written sidecar.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from ..llm.registry import PROVIDERS
from ..paths import project_dir
from .cache import (
    PROMPT_DIGEST,
    SCHEMA_VERSION,
    cache_get_with_generated_at,
    cache_key,
    cache_put,
)
from .matcher import llm_output_to_overlay

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level state (research-specific; INDEPENDENT from generate/render).
# ---------------------------------------------------------------------------
_RUN_QUEUES: dict[str, asyncio.Queue[Optional[str]]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}
_RUN_STOP_EVENTS: dict[str, asyncio.Event] = {}


class SingleFlightError(Exception):
    """Raised by `start_research` when a run is already alive for the project.

    The api/v3 layer translates this into HTTP 409 Conflict. Used directly by
    integration tests (no HTTP).
    """


# ---------------------------------------------------------------------------
# Helpers — atomic write + SSE emit
# ---------------------------------------------------------------------------
def _write_json_atomic(path: Path, data: dict) -> None:
    """Pitfall 1 + Example 3 — atomic write via tmp+replace.

    Writes JSON to `path.with_suffix(path.suffix + ".tmp")` and then renames.
    `Path.replace` is atomic on POSIX and best-effort on Windows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _emit(
    queue: asyncio.Queue[Optional[str]],
    event_type: str,
    stage: Optional[str],
    message: str = "",
    progress: Optional[float] = None,
) -> None:
    """Push a structured SSE envelope (mirrors api/v3/generate.py:_emit)."""
    payload = {
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "progress": progress,
    }
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")


# ---------------------------------------------------------------------------
# Producer coroutine
# ---------------------------------------------------------------------------
_RESEARCH_STAGES = ("kingdoms", "duchies", "condados", "baronies")


async def _research_producer(
    project_id: str,
    provider_id: str,
    model: str,
    country_qid: str,
    period_label: str,
    condado_ids: list[str],
    force_refresh: bool,
    queue: asyncio.Queue[Optional[str]],
    stop_event: asyncio.Event,
    session_factory: Callable[[], Awaitable[Any]] | Callable[[], Any],
) -> None:
    """Run the research pipeline + emit SSE events.

    Stages are virtual (kingdoms / duchies / condados / baronies) — the underlying
    LLM call is a single round-trip; we emit 4 stage_start/stage_done envelopes
    so the UI progress bar can render four ticks (UI-SPEC §Surface 2).
    """
    try:
        _emit(queue, "started", None, f"Iniciando pesquisa para projeto {project_id}", 0.0)

        # Compute applied_at ONCE at the top — used by SSE events + meta sidecar.
        applied_at = datetime.now(timezone.utc)

        # 1. Cache lookup ----------------------------------------------------
        ck = cache_key(country_qid, period_label, provider_id, model, condado_ids)
        payload: Optional[dict] = None
        generated_at: datetime = applied_at

        # session_factory is a zero-arg callable that returns a usable AsyncSession.
        # In tests it's `lambda: db_session` (already-open session). In production
        # it's `AsyncSessionLocal` (a fresh context-managed session); we handle both.
        session = session_factory()
        # If session_factory returned a coroutine (rare), await it.
        if asyncio.iscoroutine(session):
            session = await session

        try:
            if not force_refresh:
                cached = await cache_get_with_generated_at(session, ck)
                if cached is not None:
                    payload, raw_generated_at = cached
                    # Ensure tz-aware for downstream isoformat compare.
                    if raw_generated_at.tzinfo is None:
                        generated_at = raw_generated_at.replace(tzinfo=timezone.utc)
                    else:
                        generated_at = raw_generated_at

            if stop_event.is_set():
                _emit(queue, "stopped", None, "Pesquisa cancelada", None)
                return

            # 2. Fresh run path -------------------------------------------------
            if payload is None:
                provider = PROVIDERS.get(provider_id)
                if provider is None:
                    raise KeyError(f"unknown provider_id: {provider_id!r}")

                # Build a minimal prompt placeholder (Plan 09a/09b owns full
                # prompt composition). Runner stays prompt-agnostic — the
                # provider sees an opaque string.
                prompt = (
                    f"Research request — country={country_qid}, period={period_label}, "
                    f"condado_ids={','.join(condado_ids)}"
                )

                result = await provider.research(prompt, schema=None, credentials=None, queue=queue)
                # Provider may return a Pydantic model OR a dict — normalize.
                if hasattr(result, "model_dump"):
                    payload = result.model_dump()
                elif isinstance(result, dict):
                    payload = result
                else:
                    raise TypeError(
                        f"provider.research must return dict or Pydantic model, got {type(result).__name__}"
                    )
                generated_at = applied_at  # fresh run: same moment
                # Cache the fresh payload (D-11 force-refresh path also lands here).
                await cache_put(
                    session, ck, payload, provider=provider_id, model=model
                )
        finally:
            # Only close if session_factory yielded an async context-managed session.
            close = getattr(session, "close", None)
            if callable(close) and not _is_outer_session(session_factory):
                maybe_coro = close()
                if asyncio.iscoroutine(maybe_coro):
                    try:
                        await maybe_coro
                    except Exception:  # noqa: BLE001 — close errors must not mask data
                        logger.warning("session close raised", exc_info=True)

        # 3. Stage events --------------------------------------------------
        for i, stage in enumerate(_RESEARCH_STAGES):
            if stop_event.is_set():
                _emit(queue, "stopped", None, "Pesquisa cancelada", None)
                return
            _emit(queue, "stage_start", stage, "OK", i / len(_RESEARCH_STAGES))
            _emit(queue, "stage_done", stage, "OK", (i + 1) / len(_RESEARCH_STAGES))

        # 4. Build overlay --------------------------------------------------
        overlay = llm_output_to_overlay(payload, condado_ids)

        # 5. Atomic dual write (overlay + meta) -----------------------------
        pdir = project_dir(project_id)
        overlay_path = pdir / "research_overlay.json"
        meta_path = pdir / "research_overlay.meta.json"
        _write_json_atomic(overlay_path, overlay)
        meta = {
            "provider": provider_id,
            "model": model,
            "generated_at": generated_at.isoformat(),
            "applied_at": applied_at.isoformat(),
            "prompt_digest": PROMPT_DIGEST,
            "schema_version": SCHEMA_VERSION,
            "country": country_qid,
            "period": period_label,
        }
        _write_json_atomic(meta_path, meta)

        _emit(queue, "done", None, "OK", 1.0)
    except SingleFlightError:
        raise
    except asyncio.CancelledError:
        _emit(queue, "stopped", None, "Pesquisa cancelada", None)
        raise
    except Exception as exc:  # noqa: BLE001 — surface class name only (T-03-05 carry)
        logger.exception("research run failed for project %s", project_id)
        _emit(queue, "error", None, exc.__class__.__name__, None)
    finally:
        # Terminal sentinel — MUST be before evictions so consumers exit cleanly.
        await queue.put(None)
        # WR-02: prevent late-subscriber hang + stale task reference.
        _RUN_QUEUES.pop(project_id, None)
        _RUN_TASKS.pop(project_id, None)
        _RUN_STOP_EVENTS.pop(project_id, None)


def _is_outer_session(session_factory) -> bool:
    """Detect the test-style `lambda: db_session` factory (returns same session).

    When tests pass an already-open AsyncSession via `lambda: db_session`, we
    must NOT close it — the fixture owns its lifetime. We treat any callable
    whose return value is the SAME object on two consecutive calls as an
    "outer-owned" session. Production `AsyncSessionLocal` returns a fresh
    context-managed session each call.
    """
    try:
        a = session_factory()
        b = session_factory()
    except Exception:  # noqa: BLE001
        return False
    return a is b


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def start_research(
    *,
    project_id: str,
    provider: str,
    model: str,
    country_qid: str,
    period_label: str,
    condado_ids: list[str],
    force_refresh: bool = False,
    session_factory: Callable[[], Any],
) -> str:
    """Schedule a research run and return a run_id.

    Raises SingleFlightError if a run is already alive for this project. The
    api/v3/research.py endpoint translates that to HTTP 409.
    """
    if project_id in _RUN_QUEUES:
        raise SingleFlightError(
            f"research already in flight for project {project_id}"
        )

    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    stop_event = asyncio.Event()
    _RUN_QUEUES[project_id] = queue
    _RUN_STOP_EVENTS[project_id] = stop_event
    task = asyncio.create_task(
        _research_producer(
            project_id=project_id,
            provider_id=provider,
            model=model,
            country_qid=country_qid,
            period_label=period_label,
            condado_ids=list(condado_ids),
            force_refresh=force_refresh,
            queue=queue,
            stop_event=stop_event,
            session_factory=session_factory,
        )
    )
    _RUN_TASKS[project_id] = task
    # Yield once so the producer can emit its `started` envelope before the
    # api layer responds (mirrors generate.py timing).
    await asyncio.sleep(0)
    return project_id


def get_stream(project_id: str) -> asyncio.Queue[Optional[str]]:
    """Return the SSE queue for an active research run.

    Raises KeyError if no run is alive (api layer maps to HTTP 404 per
    Pitfall 7 / WR-02 — late-subscriber 404 is intentional).
    """
    queue = _RUN_QUEUES.get(project_id)
    if queue is None:
        raise KeyError(f"no active research run for project {project_id}")
    return queue


async def stop_research(project_id: str) -> bool:
    """Cancel an in-flight research run. Returns True if a run was aborted."""
    task = _RUN_TASKS.get(project_id)
    stop_event = _RUN_STOP_EVENTS.get(project_id)
    if task is None and stop_event is None:
        return False
    if stop_event is not None:
        stop_event.set()
    if task is not None and not task.done():
        task.cancel()
    return True


__all__ = [
    "SingleFlightError",
    "_RUN_QUEUES",
    "_RUN_STOP_EVENTS",
    "_RUN_TASKS",
    "_emit",
    "_write_json_atomic",
    "get_stream",
    "start_research",
    "stop_research",
]
