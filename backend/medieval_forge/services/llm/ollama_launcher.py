"""Ollama daemon launcher (POST /api/v3/llm/ollama/launch).

Ollama runs as a long-lived service (`ollama serve`). On Windows the user
usually installs Ollama Desktop which auto-starts the daemon on login, but
the daemon can be stopped via the tray icon or after a reboot. When the
backend's health-check reports ollama unreachable but the binary is on PATH,
the user clicks "Iniciar Ollama" in the UI and we exec `ollama serve` as a
detached subprocess.

Scope choice — NO shutdown endpoint:
    Ollama is a shared system service, not owned by Medieval Forge. Killing it
    might interfere with other apps the user has running (LMStudio + Ollama is
    common). The user kills it via Ollama Desktop or `Stop-Service` themselves.

Idempotency:
    `launch()` probes the HTTP endpoint first (`GET /api/tags`). If the daemon
    is already up, returns LaunchResult(ok=True, was_running=True) without
    spawning a duplicate. Otherwise spawns `ollama serve` and waits for the
    HTTP endpoint to come up (similar to llamacpp readiness probe).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_HOST = "http://127.0.0.1:11434"
READINESS_TIMEOUT_S: float = 30.0
READINESS_POLL_INTERVAL_S: float = 0.5


@dataclass(frozen=True)
class OllamaLaunchResult:
    ok: bool
    was_running: bool
    base_url: str


class OllamaBinaryMissing(RuntimeError):
    """Raised when the `ollama` CLI binary cannot be located on PATH."""


class OllamaLaunchTimeout(RuntimeError):
    """Raised when `ollama serve` starts but never opens the HTTP socket."""


def _is_running() -> bool:
    """True iff GET /api/tags returns 200 OK within 1s."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError):
        return False


def _resolve_binary() -> str | None:
    """Locate the ollama CLI. Env override > shutil.which."""
    return os.environ.get("OLLAMA_BIN") or shutil.which("ollama")


def _wait_for_ready(timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _is_running():
            return True
        time.sleep(READINESS_POLL_INTERVAL_S)
    return False


def launch() -> OllamaLaunchResult:
    """Start `ollama serve` if the daemon isn't already up. Idempotent.

    Raises:
        OllamaBinaryMissing: `ollama` CLI not on PATH.
        OllamaLaunchTimeout: subprocess spawned but daemon never bound the port.
    """
    if _is_running():
        return OllamaLaunchResult(ok=True, was_running=True, base_url=OLLAMA_HOST)

    binary = _resolve_binary()
    if binary is None:
        raise OllamaBinaryMissing(
            "Ollama não encontrado no PATH. Instale em https://ollama.com"
        )

    # Detached subprocess — we don't track its PID because ollama is a
    # shared system service. If the user wants to stop it, they do so via
    # the Ollama Desktop tray icon.
    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # Windows
    subprocess.Popen(
        [binary, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )

    if not _wait_for_ready(READINESS_TIMEOUT_S):
        raise OllamaLaunchTimeout(
            f"`ollama serve` iniciado mas /api/tags não respondeu em {READINESS_TIMEOUT_S:.0f}s."
        )

    return OllamaLaunchResult(ok=True, was_running=False, base_url=OLLAMA_HOST)


__all__ = [
    "OllamaBinaryMissing",
    "OllamaLaunchResult",
    "OllamaLaunchTimeout",
    "launch",
]
