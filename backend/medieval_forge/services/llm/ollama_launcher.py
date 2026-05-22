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

Logs (UAT 2026-05-22):
    When we spawn the daemon ourselves we keep stdout open and tail it into a
    bounded ring buffer (`_LOG_BUFFER`) so the UI can show "what is ollama
    doing right now". If the daemon was already up before we got here, there
    is no PID to attach to and `get_logs()` returns an empty list.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass

OLLAMA_HOST = "http://127.0.0.1:11434"
READINESS_TIMEOUT_S: float = 30.0
READINESS_POLL_INTERVAL_S: float = 0.5

_LOG_BUFFER_MAX = 1000
_LOG_BUFFER: "deque[str]" = deque(maxlen=_LOG_BUFFER_MAX)
_LOG_LOCK = threading.Lock()
_LOG_READER_THREAD: threading.Thread | None = None


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


def _log_reader(proc: subprocess.Popen) -> None:
    """Drain `ollama serve` stdout into the ring buffer."""
    try:
        if proc.stdout is None:
            return
        for raw in proc.stdout:
            if not raw:
                continue
            line = raw.rstrip("\r\n")
            if not line:
                continue
            with _LOG_LOCK:
                _LOG_BUFFER.append(line)
    except (OSError, ValueError):
        return


def get_logs(tail: int = 200) -> list[str]:
    """Snapshot of the last `tail` ollama-server log lines."""
    if tail <= 0:
        return []
    with _LOG_LOCK:
        if tail >= len(_LOG_BUFFER):
            return list(_LOG_BUFFER)
        return list(_LOG_BUFFER)[-tail:]


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

    # Spawn with PIPE so we can tail logs. CREATE_NEW_PROCESS_GROUP on Windows
    # so the daemon survives backend restarts; the reader thread is a daemon
    # and dies with us — logs are lost on restart but ollama keeps running.
    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # Windows
    proc = subprocess.Popen(
        [binary, "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        bufsize=1,
        universal_newlines=True,
        creationflags=creationflags,
        close_fds=True,
    )

    # Reset buffer for the new daemon + spawn reader thread.
    with _LOG_LOCK:
        _LOG_BUFFER.clear()
    global _LOG_READER_THREAD
    _LOG_READER_THREAD = threading.Thread(
        target=_log_reader, args=(proc,), daemon=True, name="ollama-log-reader"
    )
    _LOG_READER_THREAD.start()

    if not _wait_for_ready(READINESS_TIMEOUT_S):
        raise OllamaLaunchTimeout(
            f"`ollama serve` iniciado mas /api/tags não respondeu em {READINESS_TIMEOUT_S:.0f}s."
        )

    return OllamaLaunchResult(ok=True, was_running=False, base_url=OLLAMA_HOST)


__all__ = [
    "OllamaBinaryMissing",
    "OllamaLaunchResult",
    "OllamaLaunchTimeout",
    "get_logs",
    "launch",
]
