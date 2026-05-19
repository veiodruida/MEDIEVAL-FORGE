"""Llama.cpp server subprocess lifecycle (Phase 07.1 D-08/D-08b).

Centralizes idempotent spawn (D-08 by absolute model path), auto-port allocation
(D-08 socket.bind(('', 0))), env-override-or-fallback discovery for binary
(D-07b LLAMA_SERVER_BIN | shutil.which) and models directory (D-07a
MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR | ~/.medieval-forge/models/).

Model discovery scans multiple directories:
  1. models_dir() — primary (MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR or default)
  2. Well-known OS paths (C:\\AI_Models, ~/llama.cpp/models, LM Studio, etc.)
     — only when MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS is not set
  3. MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS — semicolon-separated (Windows) or
     colon-separated (Unix) explicit extras; when set, suppresses well-known dirs

Lifecycle: FastAPI lifespan calls shutdown(); atexit.register(shutdown)
fires as belt-and-braces fallback. Test isolation via _reset_state_for_tests()
(CLAUDE.md forbids dynamic module reloading / sys.modules patching).

Threat model:
- T-07.1-05-01 command injection: subprocess.Popen([...], shell=False) — list form,
  never f-string into a shell. Mitigated.
- T-07.1-05-02 path traversal: launch() validates resolved path is under one of
  the allowed scan_dirs roots (multi-root guard). Symlink-escape guard included.
- T-07.1-05-03 LLAMA_SERVER_BIN arbitrary binary: accepted — user controls own env,
  consistent with PATH semantics.
"""
from __future__ import annotations

import atexit
import os
import platform
import shutil
import socket
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODELS_DIR: Path = Path.home() / ".medieval-forge" / "models"
SHUTDOWN_TIMEOUT_S: float = 5.0


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    base_url: str
    pid: int
    model: str        # filename (relative to models dir)
    started_at: str   # ISO8601 UTC


# ---------------------------------------------------------------------------
# Public exception classes
# ---------------------------------------------------------------------------


class LlamacppBinaryMissing(RuntimeError):
    """Raised when llama-server binary cannot be located."""


class LlamacppLaunchConflict(RuntimeError):
    """Raised when a different model is already running."""


class LlamacppModelNotFound(FileNotFoundError):
    """Raised when the requested .gguf file does not exist in models_dir."""


class LlamacppInvalidModelFilename(ValueError):
    """Raised when the filename is rejected by path-traversal or extension guards."""


# ---------------------------------------------------------------------------
# Module-level state — single-process invariant per D-08
# ---------------------------------------------------------------------------

_STATE_LOCK = threading.Lock()
_PROCESS: subprocess.Popen | None = None
_ACTIVE_MODEL_PATH: Path | None = None
_ACTIVE_PORT: int | None = None
_STARTED_AT: str | None = None

# atexit guard — must be registered exactly once
_ATEXIT_REGISTERED: bool = False


# ---------------------------------------------------------------------------
# Discovery helpers (D-07a, D-07b)
# ---------------------------------------------------------------------------


def models_dir() -> Path:
    """D-07a: env override + fallback to ~/.medieval-forge/models/."""
    env = os.environ.get("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR")
    return Path(env) if env else DEFAULT_MODELS_DIR


def _well_known_extra_dirs() -> list[Path]:
    """Platform-specific well-known .gguf directories beyond models_dir.

    Only called when MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS is not set.
    Returns only directories that currently exist on disk.
    """
    home = Path.home()
    if platform.system() == "Windows":
        candidates = [
            Path("C:/AI_Models"),
            home / "llama.cpp" / "models",
            home / ".cache" / "lm-studio" / "models",
            home / ".lmstudio" / "models",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            home / "llama.cpp" / "models",
            home / ".cache" / "lm-studio" / "models",
            home / ".lmstudio" / "models",
        ]
    else:
        candidates = [
            home / "llama.cpp" / "models",
            home / ".cache" / "huggingface" / "hub",
        ]
    return [d for d in candidates if d.exists()]


def scan_dirs() -> list[Path]:
    """All directories scanned for .gguf models (ordered, deduplicated).

    1. models_dir() — primary (MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR or default)
    2. If MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS is set: use those dirs only (no well-known).
       Set to empty string to disable all extras (useful in tests).
       If not set: add well-known OS-specific dirs that exist on disk.
    """
    dirs: list[Path] = [models_dir()]

    env_extra = os.environ.get("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS")
    if env_extra is None:
        dirs.extend(_well_known_extra_dirs())
    else:
        sep = ";" if platform.system() == "Windows" else ":"
        for raw in env_extra.split(sep):
            raw = raw.strip()
            if raw:
                dirs.append(Path(raw))

    seen: set[Path] = set()
    result: list[Path] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


def list_models() -> list[str]:
    """Sorted absolute paths of .gguf files across all scan_dirs (top-level only).

    Returns absolute path strings so callers can pass them directly to launch()
    without knowing which directory each model came from.
    """
    found: list[str] = []
    for d in scan_dirs():
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() == ".gguf":
                found.append(str(p.resolve()))
    return found


def _resolve_binary() -> str | None:
    """D-07b: env override + shutil.which fallback."""
    return os.environ.get("LLAMA_SERVER_BIN") or shutil.which("llama-server")


def _pick_port() -> int:
    """D-08: pick a free ephemeral port via SO_REUSEADDR."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Core lifecycle
# ---------------------------------------------------------------------------


def launch(model_path: str) -> LaunchResult:
    """D-08: idempotent by absolute model path.

    Accepts either:
    - Absolute path (as returned by list_models()) — validated against allowed roots.
    - Bare basename (e.g. "model.gguf") — searched across scan_dirs; first match wins.

    Path-traversal guard (T-07.1-05-02, ASVS V12) runs BEFORE any state mutation.
    Multi-root allowed-list replaces the old single-root check; symlink-escape guard
    is preserved — resolved path must land under one of the scan_dirs roots.

    Raises:
        LlamacppInvalidModelFilename: path fails validation or escapes allowed roots.
        LlamacppModelNotFound: file does not exist in any scan dir.
        LlamacppBinaryMissing: binary not found via env or PATH.
        LlamacppLaunchConflict: a different model is already running.
    """
    # --- Validation layer (no state mutation yet) ---
    if not model_path:
        raise LlamacppInvalidModelFilename("model path is empty")

    p = Path(model_path)

    if p.suffix.lower() != ".gguf":
        raise LlamacppInvalidModelFilename(
            f"model filename must end with .gguf: {model_path!r}"
        )

    allowed_roots = [d.resolve() for d in scan_dirs() if d.exists()]

    if p.is_absolute():
        # Full path from list_models() — resolve and check against allowed roots.
        try:
            target_path = p.resolve(strict=True)
        except (FileNotFoundError, OSError):
            raise LlamacppModelNotFound(f"model not found: {model_path}")
        if not any(
            target_path == r or r in target_path.parents for r in allowed_roots
        ):
            raise LlamacppInvalidModelFilename(
                f"model path escapes all allowed directories: {target_path}"
            )
    else:
        # Basename-only — reject relative paths with directory components.
        if p.name != model_path:
            raise LlamacppInvalidModelFilename(
                f"model filename must not contain directory components: {model_path!r}"
            )
        # Search scan_dirs for the first safe match.
        target_path = None
        escaped_candidate: Path | None = None
        for d in scan_dirs():
            if not d.exists():
                continue
            candidate = d / p.name
            if not candidate.exists():
                continue
            resolved_candidate = candidate.resolve()
            if any(
                resolved_candidate == r or r in resolved_candidate.parents
                for r in allowed_roots
            ):
                target_path = resolved_candidate
                break
            else:
                escaped_candidate = resolved_candidate

        if target_path is None:
            if escaped_candidate is not None:
                raise LlamacppInvalidModelFilename(
                    f"model path escapes all allowed directories: {escaped_candidate}"
                )
            raise LlamacppModelNotFound(
                f"model {model_path!r} not found in any scan directory"
            )

    if not target_path.exists():
        raise LlamacppModelNotFound(f"model not found: {target_path}")

    # --- Binary resolution ---
    binary = _resolve_binary()
    if binary is None:
        raise LlamacppBinaryMissing(
            "llama-server não encontrado no PATH (defina LLAMA_SERVER_BIN)"
        )

    # --- State mutation under lock ---
    with _STATE_LOCK:
        global _PROCESS, _ACTIVE_MODEL_PATH, _ACTIVE_PORT, _STARTED_AT

        if _PROCESS is not None and _PROCESS.poll() is None:
            # A process is already alive
            if _ACTIVE_MODEL_PATH == target_path:
                # Same model — idempotent return
                return LaunchResult(
                    ok=True,
                    base_url=f"http://127.0.0.1:{_ACTIVE_PORT}",
                    pid=_PROCESS.pid,
                    model=target_path.name,
                    started_at=_STARTED_AT,
                )
            raise LlamacppLaunchConflict(
                f"modelo `{_ACTIVE_MODEL_PATH.name}` ativo — pare-o antes via DELETE"
            )

        port = _pick_port()
        # T-07.1-05-01: list-form argv, shell=False — never pass user input to a shell.
        # T-07.1-05-06: DEVNULL avoids pipe-buffer deadlock (Pitfall 8).
        proc = subprocess.Popen(
            [binary, "-m", str(target_path), "--ctx-size", "8192", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _PROCESS = proc
        _ACTIVE_MODEL_PATH = target_path
        _ACTIVE_PORT = port
        _STARTED_AT = datetime.now(timezone.utc).isoformat()

    return LaunchResult(
        ok=True,
        base_url=f"http://127.0.0.1:{port}",
        pid=proc.pid,
        model=target_path.name,
        started_at=_STARTED_AT,
    )


def shutdown() -> bool:
    """D-08b: synchronous shutdown with terminate → 5s grace → kill.

    Returns:
        True  — a process was running and has been killed.
        False — no-op (no process was alive).

    Callers:
        - FastAPI lifespan: ``await asyncio.to_thread(shutdown)``
        - atexit: registered directly (sync, no await needed)

    review-fix #4: single sync entry point. No ``_sync`` variant exists in this module.
    """
    global _PROCESS, _ACTIVE_MODEL_PATH, _ACTIVE_PORT, _STARTED_AT

    with _STATE_LOCK:
        if _PROCESS is None or _PROCESS.poll() is not None:
            _PROCESS = _ACTIVE_MODEL_PATH = _ACTIVE_PORT = _STARTED_AT = None
            return False
        proc = _PROCESS

    proc.terminate()
    try:
        proc.wait(timeout=SHUTDOWN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1.0)

    with _STATE_LOCK:
        _PROCESS = _ACTIVE_MODEL_PATH = _ACTIVE_PORT = _STARTED_AT = None

    return True


def status() -> dict | None:
    """Return current process info or None if no process is alive."""
    with _STATE_LOCK:
        if _PROCESS is None or _PROCESS.poll() is not None:
            return None
        return {
            "pid": _PROCESS.pid,
            "model": _ACTIVE_MODEL_PATH.name if _ACTIVE_MODEL_PATH else None,
            "base_url": f"http://127.0.0.1:{_ACTIVE_PORT}",
            "started_at": _STARTED_AT,
        }


# ---------------------------------------------------------------------------
# Test isolation (CLAUDE.md forbids dynamic module reloading — no reload/sys.modules tricks)
# ---------------------------------------------------------------------------


def _reset_state_for_tests() -> None:
    """Reset module-level state for test isolation (no dynamic module reloading).

    NEVER call from production code. Use only in test fixtures.
    """
    global _PROCESS, _ACTIVE_MODEL_PATH, _ACTIVE_PORT, _STARTED_AT
    with _STATE_LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            _PROCESS.kill()
            try:
                _PROCESS.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        _PROCESS = _ACTIVE_MODEL_PATH = _ACTIVE_PORT = _STARTED_AT = None


def _set_process_for_tests(
    proc: subprocess.Popen,
    model_path: Path,
    port: int,
) -> None:
    """Inject a live process into module state for test seam (Test 13).

    NEVER call from production code.
    """
    global _PROCESS, _ACTIVE_MODEL_PATH, _ACTIVE_PORT, _STARTED_AT
    with _STATE_LOCK:
        _PROCESS = proc
        _ACTIVE_MODEL_PATH = model_path
        _ACTIVE_PORT = port
        _STARTED_AT = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# atexit registration — exactly once per process
# ---------------------------------------------------------------------------


def _register_atexit_once() -> None:
    """Register shutdown() with atexit if not already registered.

    Guards against duplicate registration when the module is re-imported in
    the same process (should not happen in normal operation, but test isolation
    via _reset_state_for_tests makes it possible in test suites).
    """
    global _ATEXIT_REGISTERED
    if not _ATEXIT_REGISTERED:
        atexit.register(shutdown)  # review-fix #4: single sync entry point
        _ATEXIT_REGISTERED = True


_register_atexit_once()
