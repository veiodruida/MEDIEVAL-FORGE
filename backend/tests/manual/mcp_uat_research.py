"""End-to-end UAT harness for the research SSE flow.

Run me from `backend/` while a backend is alive at 127.0.0.1:8765:

    python tests/manual/mcp_uat_research.py

What it does:
  1. Lists every registered provider via GET /v3/research/providers.
  2. For each healthy provider that exposes an `available_models` list,
     picks a small/fast model and fires POST /v3/research/start against
     a real generated project (condado_ids from territory_metadata.json).
  3. Subscribes to the SSE stream, drains it until the terminal envelope
     (success | error | stopped) arrives.
  4. Reports a one-row-per-provider summary including:
       - phase reached (running / succeeded / failed)
       - elapsed seconds until terminal
       - error message verbatim (or count of applied condados)

Designed to be re-runnable so we can spot regressions without manually
clicking through the React dialog.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

BACKEND = os.environ.get("MF_BACKEND", "http://127.0.0.1:8765")
PROJECT_ID = "69fdddbd-3fa6-4102-8b98-b586f5af18ba"  # ES / 868 / 91 condados
PER_RUN_TIMEOUT_S = 90  # cap each provider's wait so a hung local model
                        # doesn't block the rest of the suite

# Small-model preference list per provider — pick the FIRST one in
# `available_models` that matches a name fragment in this list.
SMALL_MODEL_HINTS: dict[str, list[str]] = {
    "ollama": ["qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.2:3b"],
    "llamacpp": ["qwen2.5-0.5b", "qwen2.5-1.5b", "llama-3.2-1b"],
    "openrouter": [
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "openai": ["gpt-4o-mini"],
    "gemini": ["gemini-1.5-flash", "gemini-2.0-flash-exp"],
    "claude": ["claude-3-haiku", "claude-3-5-haiku"],
}


def http_json(method: str, path: str, body: dict | None = None) -> Any:
    url = f"{BACKEND}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pick_model(provider_id: str, available: list[str]) -> str | None:
    hints = SMALL_MODEL_HINTS.get(provider_id) or []
    for hint in hints:
        for m in available:
            if hint.lower() in m.lower():
                return m
    return available[0] if available else None


def load_condado_ids() -> list[str]:
    p = Path.home() / ".medieval-forge" / "projects" / PROJECT_ID / "output" / "territory_metadata.json"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        meta = json.load(f)
    return [c["id"] for c in meta.get("condados", [])]


def stream_terminal(project_id: str, deadline_s: float) -> dict:
    """Open the SSE stream and return the first terminal envelope.

    Returns a dict with keys: phase ("succeeded"|"failed"|"timeout"),
    message, elapsed.
    """
    url = f"{BACKEND}/api/v3/research/stream/{project_id}"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    start = time.monotonic()
    progress_msgs: list[str] = []
    last_progress = ""
    try:
        with urllib.request.urlopen(req, timeout=deadline_s) as resp:
            for raw in resp:
                if time.monotonic() - start > deadline_s:
                    return {
                        "phase": "timeout",
                        "message": f"deadline exceeded after {deadline_s}s, last progress: {last_progress!r}",
                        "elapsed": deadline_s,
                    }
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    env = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                et = env.get("event_type", "")
                if et == "progress":
                    last_progress = env.get("message", "")
                    progress_msgs.append(last_progress)
                elif et == "terminal":
                    return {
                        "phase": "succeeded" if env.get("status") == "success" else "failed",
                        "message": env.get("message", ""),
                        "elapsed": time.monotonic() - start,
                    }
                elif et == "error":
                    return {
                        "phase": "failed",
                        "message": env.get("message", ""),
                        "elapsed": time.monotonic() - start,
                    }
    except Exception as exc:  # noqa: BLE001
        return {
            "phase": "stream_error",
            "message": f"{type(exc).__name__}: {exc}",
            "elapsed": time.monotonic() - start,
        }
    return {
        "phase": "timeout",
        "message": f"stream closed without terminal, last progress: {last_progress!r}",
        "elapsed": time.monotonic() - start,
    }


def stop_run(project_id: str) -> None:
    """Best-effort cancel of any in-flight run for this project + brief wait.

    SingleFlight on the backend rejects a second start with 409 until the
    previous producer's `finally` block evicts _RUN_QUEUES. Calling /stop
    triggers cancellation; the small sleep gives the producer time to
    surface the `stopped` envelope and clean up.
    """
    url = f"{BACKEND}/api/v3/research/stop/{project_id}"
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.5)


def run_one(provider_id: str, model: str, condado_ids: list[str]) -> dict:
    body = {
        "project_id": PROJECT_ID,
        "provider": provider_id,
        "model": model,
        "country_qid": "ES",
        "period_start": 868,
        "period_end": 868,
        "condado_ids": condado_ids,
        "force_refresh": True,
    }
    try:
        http_json("POST", "/api/v3/research/start", body)
    except Exception as exc:  # noqa: BLE001
        return {
            "phase": "start_failed",
            "message": f"{type(exc).__name__}: {exc}",
            "elapsed": 0.0,
        }
    return stream_terminal(PROJECT_ID, PER_RUN_TIMEOUT_S)


def main() -> int:
    print(f"backend: {BACKEND}")
    providers = http_json("GET", "/api/v3/research/providers")
    condado_ids = load_condado_ids()
    print(f"project: {PROJECT_ID} ({len(condado_ids)} condados)")
    print()

    rows = []
    for p in providers:
        pid = p["provider_id"]
        if not p.get("healthy"):
            rows.append((pid, "(not healthy)", "skipped", p.get("message", ""), 0.0))
            continue
        avail = p.get("available_models") or []
        if not avail and pid in ("claude",):
            # Claude has no model registry; pass a sensible default.
            model = "claude-3-haiku-20240307"
        else:
            model = pick_model(pid, avail)
        if not model:
            rows.append((pid, "(no model)", "skipped", "no candidate model", 0.0))
            continue
        print(f"--- {pid} | model={model!r} ---")
        # Ensure any previous run is cancelled before starting (SingleFlight
        # 409 otherwise blocks back-to-back tests).
        stop_run(PROJECT_ID)
        result = run_one(pid, model, condado_ids)
        stop_run(PROJECT_ID)
        print(
            f"  phase={result['phase']} elapsed={result['elapsed']:.1f}s\n"
            f"  msg: {result['message'][:200]}"
        )
        print()
        rows.append(
            (pid, model, result["phase"], result["message"][:200], result["elapsed"])
        )

    print("=== SUMMARY ===")
    for pid, model, phase, msg, elapsed in rows:
        print(f"{pid:12} {phase:14} {elapsed:6.1f}s  {model}")
        if phase not in ("succeeded", "skipped"):
            print(f"             err: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
