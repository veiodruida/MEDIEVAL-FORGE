"""SC-4e e2e — POST/DELETE/GET /api/v3/llm/llamacpp/launch lifecycle.

Implemented in plan 07.1-05. The scaffold from plan 07.1-00 is replaced here.

Per RESEARCH §Open Q4, the real subprocess is a Python `time.sleep(60)`
stand-in injected via fake_subprocess fixture. This keeps tests portable
to CI machines without llama-server installed.

7 tests cover SC-4e:
  1. Full lifecycle: POST → GET status → DELETE → process gone
  2. Idempotent same-model POST → 200, same pid
  3. Conflict different-model POST → 409 with PT-BR detail
  4. DELETE when no server → 200, was_running=False
  5. Path-traversal POST → 400
  6. GET when no process → {running: False, all None} (review-fix #4)
  7. GET reflects active process before/after DELETE (review-fix #4)
"""
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from medieval_forge.main import app
from medieval_forge.services.llm.llamacpp_launcher import (
    _reset_state_for_tests,
    status as launcher_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_launcher():
    """Isolate each test: kill any stray process and clear module state."""
    _reset_state_for_tests()
    yield
    _reset_state_for_tests()


@pytest.fixture
def models_dir_with_test_gguf(tmp_path, monkeypatch):
    """Create a tmp models dir with test.gguf and alt.gguf, point env at it."""
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    (tmp_path / "test.gguf").touch()
    (tmp_path / "alt.gguf").touch()
    return tmp_path


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Make llamacpp_launcher.subprocess.Popen spawn a portable sleep stand-in.

    The launcher's argv is preserved in the sense that the path-traversal
    guard runs BEFORE Popen is ever called; this fixture only intercepts the
    actual Popen call so no real llama-server binary is needed.
    """
    real_popen = __import__("subprocess").Popen

    def fake_popen(argv, **kwargs):
        # Replace [binary, '-m', path, '--ctx-size', '8192', '--port', port]
        # with a real process the test can terminate().
        return real_popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            **{k: v for k, v in kwargs.items() if k in ("stdout", "stderr")},
        )

    monkeypatch.setenv("LLAMA_SERVER_BIN", sys.executable)
    monkeypatch.setattr(
        "medieval_forge.services.llm.llamacpp_launcher.subprocess.Popen",
        fake_popen,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_post_launch_then_get_status_then_delete_process_gone(
    models_dir_with_test_gguf, fake_subprocess
):
    """Full lifecycle: POST → launcher_status non-None → DELETE → status None."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v3/llm/llamacpp/launch",
            json={"model": "test.gguf"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data.keys()) == {"ok", "base_url", "pid", "model", "started_at"}
        assert data["ok"] is True
        assert data["model"] == "test.gguf"
        assert isinstance(data["pid"], int)
        assert data["base_url"].startswith("http://127.0.0.1:")

        assert launcher_status() is not None

        r2 = await client.delete("/api/v3/llm/llamacpp/launch")
        assert r2.status_code == 200, r2.text
        assert r2.json() == {"ok": True, "was_running": True}

        assert launcher_status() is None


async def test_post_launch_idempotent_same_model_returns_200(
    models_dir_with_test_gguf, fake_subprocess
):
    """Same model posted twice → both 200, pid identical."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v3/llm/llamacpp/launch", json={"model": "test.gguf"})
        assert r1.status_code == 200
        r2 = await client.post("/api/v3/llm/llamacpp/launch", json={"model": "test.gguf"})
        assert r2.status_code == 200
        assert r1.json()["pid"] == r2.json()["pid"]


async def test_post_launch_conflict_different_model_returns_409(
    models_dir_with_test_gguf, fake_subprocess
):
    """Different model while one is running → 409 with PT-BR detail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v3/llm/llamacpp/launch", json={"model": "test.gguf"})
        assert r1.status_code == 200
        r2 = await client.post("/api/v3/llm/llamacpp/launch", json={"model": "alt.gguf"})
        assert r2.status_code == 409
        detail = r2.json()["detail"]
        assert "ativo" in detail
        assert "DELETE" in detail


async def test_delete_launch_when_no_server_returns_200_was_running_false():
    """DELETE with no server running → 200, was_running=False (idempotent, Discretion #7)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.delete("/api/v3/llm/llamacpp/launch")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "was_running": False}


async def test_post_launch_path_traversal_returns_400(
    models_dir_with_test_gguf, fake_subprocess
):
    """Path traversal in model name → 400 (T-07.1-05-02)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v3/llm/llamacpp/launch",
            json={"model": "../etc/passwd.gguf"},
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        # Launcher's path-traversal guard message.
        assert "directory components" in detail or "must not contain" in detail


async def test_get_launch_returns_running_false_when_no_process():
    """review-fix #4: GET with no process → {running: False, all fields None}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v3/llm/llamacpp/launch")
        assert r.status_code == 200
        assert r.json() == {
            "running": False,
            "pid": None,
            "model": None,
            "base_url": None,
            "started_at": None,
        }


async def test_get_launch_reflects_active_process(
    models_dir_with_test_gguf, fake_subprocess
):
    """review-fix #4: GET reflects launcher.status() truth across POST/DELETE."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v3/llm/llamacpp/launch", json={"model": "test.gguf"})

        r = await client.get("/api/v3/llm/llamacpp/launch")
        assert r.status_code == 200
        body = r.json()
        assert body["running"] is True
        assert isinstance(body["pid"], int)
        assert body["model"] == "test.gguf"
        assert body["base_url"].startswith("http://127.0.0.1:")
        assert body["started_at"]  # non-empty ISO8601 string

        await client.delete("/api/v3/llm/llamacpp/launch")

        r2 = await client.get("/api/v3/llm/llamacpp/launch")
        assert r2.json()["running"] is False
        assert r2.json()["pid"] is None
