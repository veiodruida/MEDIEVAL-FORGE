"""SC-3, SC-4a..f unit coverage. Implemented in plan 07.1-02."""
import atexit
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from medieval_forge.services.llm import llamacpp_launcher
from medieval_forge.services.llm.llamacpp_launcher import (
    LlamacppBinaryMissing,
    LlamacppInvalidModelFilename,
    LlamacppLaunchConflict,
    LlamacppModelNotFound,
    _reset_state_for_tests,
    _resolve_binary,
    launch,
    list_models,
    models_dir,
    shutdown,
    status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_launcher_state():
    _reset_state_for_tests()
    yield
    _reset_state_for_tests()


@pytest.fixture
def models_dir_with_files(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    # Disable well-known extra dirs so tests see only the controlled tmp_path.
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS", "")
    return tmp_path


@pytest.fixture
def fake_binary(monkeypatch):
    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)
    return sys.executable


# ---------------------------------------------------------------------------
# Helper for symlink permission check (used by test 17)
# ---------------------------------------------------------------------------


def _can_create_symlink() -> bool:
    """On Windows non-admin sessions, os.symlink raises OSError (WinError 1314).
    Skip the test rather than fail the suite."""
    if sys.platform == "win32":
        import tempfile

        try:
            with tempfile.TemporaryDirectory() as d:
                src = os.path.join(d, "src")
                dst = os.path.join(d, "dst")
                open(src, "w").close()
                os.symlink(src, dst)
                return True
        except (OSError, NotImplementedError):
            return False
    return True


# ---------------------------------------------------------------------------
# Test 1 — list_models: empty dir
# ---------------------------------------------------------------------------


def test_list_models_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS", "")
    assert list_models() == []


# ---------------------------------------------------------------------------
# Test 2 — list_models: sorted .gguf only, returns absolute paths
# ---------------------------------------------------------------------------


def test_list_models_returns_sorted_gguf_absolute_paths_only(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS", "")
    (tmp_path / "c.gguf").touch()
    (tmp_path / "a.gguf").touch()
    (tmp_path / "b.gguf").touch()
    (tmp_path / "noise.txt").touch()
    expected = [str((tmp_path / name).resolve()) for name in ["a.gguf", "b.gguf", "c.gguf"]]
    assert list_models() == expected


# ---------------------------------------------------------------------------
# Test 3 — list_models: case-insensitive .gguf suffix, returns absolute paths
# ---------------------------------------------------------------------------


def test_list_models_case_insensitive_gguf_suffix(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS", "")
    (tmp_path / "X.GGUF").touch()
    (tmp_path / "y.Gguf").touch()
    (tmp_path / "z.gguf").touch()
    result = list_models()
    expected = sorted(
        str((tmp_path / name).resolve()) for name in ["X.GGUF", "y.Gguf", "z.gguf"]
    )
    assert sorted(result) == expected


# ---------------------------------------------------------------------------
# Test 4 — _resolve_binary: env override
# ---------------------------------------------------------------------------


def test_resolve_binary_uses_env_override_when_set(monkeypatch):
    monkeypatch.setenv("LLAMA_SERVER_BIN", "/fake/llama-server")
    assert _resolve_binary() == "/fake/llama-server"


# ---------------------------------------------------------------------------
# Test 5 — _resolve_binary: shutil.which fallback
# ---------------------------------------------------------------------------


def test_resolve_binary_falls_back_to_shutil_which(monkeypatch):
    monkeypatch.delenv("LLAMA_SERVER_BIN", raising=False)
    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.shutil.which",
        lambda name: "/path/from/which" if name == "llama-server" else None,
    )
    assert _resolve_binary() == "/path/from/which"


# ---------------------------------------------------------------------------
# Test 6 — launch: picks free port via socket.bind
# ---------------------------------------------------------------------------


def test_launch_picks_free_port_via_socket_bind(models_dir_with_files, monkeypatch):
    (models_dir_with_files / "model.gguf").touch()
    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None

    captured_args = {}

    def fake_popen(args, **kwargs):
        captured_args["args"] = args
        return mock_proc

    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.subprocess.Popen",
        fake_popen,
    )

    result = launch("model.gguf")

    assert result.ok is True
    assert result.base_url.startswith("http://127.0.0.1:")
    port_str = result.base_url.split(":")[-1]
    port = int(port_str)
    assert port > 0
    # Confirm port was passed to Popen
    assert str(port) in captured_args["args"]


# ---------------------------------------------------------------------------
# Test 7 — launch: rejects path traversal with dotdot filename
# ---------------------------------------------------------------------------


def test_launch_rejects_path_traversal_dotdot_filename():
    with pytest.raises(LlamacppInvalidModelFilename):
        launch("../etc/passwd.gguf")


# ---------------------------------------------------------------------------
# Test 8 — launch: rejects filename with directory component
# ---------------------------------------------------------------------------


def test_launch_rejects_filename_with_directory_component():
    with pytest.raises(LlamacppInvalidModelFilename):
        launch("subdir/model.gguf")


# ---------------------------------------------------------------------------
# Test 9 — launch: rejects non-.gguf suffix
# ---------------------------------------------------------------------------


def test_launch_rejects_non_gguf_suffix():
    with pytest.raises(LlamacppInvalidModelFilename):
        launch("model.bin")


# ---------------------------------------------------------------------------
# Test 10 — launch: idempotent for same model
# ---------------------------------------------------------------------------


def test_launch_idempotent_same_model_returns_same_pid(models_dir_with_files, monkeypatch):
    (models_dir_with_files / "m.gguf").touch()
    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None

    popen_call_count = {"n": 0}

    def fake_popen(args, **kwargs):
        popen_call_count["n"] += 1
        return mock_proc

    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.subprocess.Popen",
        fake_popen,
    )

    r1 = launch("m.gguf")
    r2 = launch("m.gguf")

    assert r1.pid == r2.pid == 12345
    assert popen_call_count["n"] == 1


# ---------------------------------------------------------------------------
# Test 11 — launch: conflict raises LlamacppLaunchConflict with PT-BR message
# ---------------------------------------------------------------------------


def test_launch_conflict_different_model_raises_LlamacppLaunchConflict(
    models_dir_with_files, monkeypatch
):
    (models_dir_with_files / "a.gguf").touch()
    (models_dir_with_files / "b.gguf").touch()
    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None

    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.subprocess.Popen",
        lambda args, **kwargs: mock_proc,
    )

    launch("a.gguf")

    with pytest.raises(LlamacppLaunchConflict) as exc_info:
        launch("b.gguf")

    msg = str(exc_info.value)
    assert "modelo" in msg
    assert "ativo" in msg


# ---------------------------------------------------------------------------
# Test 12 — launch: missing binary raises LlamacppBinaryMissing
# ---------------------------------------------------------------------------


def test_launch_missing_binary_raises_LlamacppBinaryMissing(
    models_dir_with_files, monkeypatch
):
    (models_dir_with_files / "m.gguf").touch()
    monkeypatch.delenv("LLAMA_SERVER_BIN", raising=False)
    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.shutil.which",
        lambda name: None,
    )

    with pytest.raises(LlamacppBinaryMissing):
        launch("m.gguf")


# ---------------------------------------------------------------------------
# Test 13 — shutdown: kills alive subprocess within 5s, returns True
# ---------------------------------------------------------------------------


def test_shutdown_kills_alive_subprocess_within_5s(monkeypatch):
    # Use real Python subprocess as stand-in for llama-server (Pitfall 5)
    real_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Inject into module state via test seam
    llamacpp_launcher._set_process_for_tests(
        real_proc,
        Path("/tmp/model.gguf"),
        8080,
    )

    result = shutdown()

    assert result is True
    assert real_proc.poll() is not None


# ---------------------------------------------------------------------------
# Test 14 — shutdown: idempotent when no process, returns False
# ---------------------------------------------------------------------------


def test_shutdown_idempotent_when_no_process_returns_false():
    _reset_state_for_tests()
    assert shutdown() is False
    assert shutdown() is False


# ---------------------------------------------------------------------------
# Test 15 — atexit: registered exactly once
# ---------------------------------------------------------------------------


def test_atexit_registered_exactly_once():
    assert llamacpp_launcher._ATEXIT_REGISTERED is True
    before = llamacpp_launcher._ATEXIT_REGISTERED
    llamacpp_launcher._register_atexit_once()
    assert llamacpp_launcher._ATEXIT_REGISTERED == before


# ---------------------------------------------------------------------------
# Test 16 — _reset_state_for_tests: clears module state
# ---------------------------------------------------------------------------


def test_reset_state_for_tests_clears_module_state(models_dir_with_files, monkeypatch):
    (models_dir_with_files / "m.gguf").touch()
    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)

    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.poll.return_value = None

    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.subprocess.Popen",
        lambda args, **kwargs: mock_proc,
    )

    launch("m.gguf")
    assert status() is not None

    _reset_state_for_tests()

    assert status() is None
    assert llamacpp_launcher._PROCESS is None


# ---------------------------------------------------------------------------
# Test 17 — launch: rejects symlink escape outside models_dir (review-fix #9)
# ---------------------------------------------------------------------------


def test_launcher_rejects_symlink_escape_outside_models_dir(
    models_dir_with_files, fake_binary, monkeypatch
):
    if not _can_create_symlink():
        pytest.skip("symlink creation not permitted on this platform")

    # Pick a target OUTSIDE models_dir that actually exists on the filesystem
    if sys.platform == "win32":
        outside_target = r"C:\Windows\System32\notepad.exe"
    else:
        outside_target = "/etc/passwd"

    sym = models_dir_with_files / "evil.gguf"
    os.symlink(outside_target, sym)

    # Symlink lives inside models_dir AND has .gguf suffix:
    # basename + suffix guards pass. Only the symlink-escape guard (resolve) rejects.
    with pytest.raises(LlamacppInvalidModelFilename) as exc_info:
        launch("evil.gguf")

    msg = str(exc_info.value).lower()
    assert "escape" in msg or "outside" in msg or "models dir" in msg
