"""Per-provider unit tests with mocked SDK clients — RESEARCH-01/02/06/07."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from medieval_forge.services.llm.schemas import ResearchResult

_VALID_PAYLOAD = {
    "kingdoms": {"asturias": "Reino de Asturias"},
    "duchies": {"galicia": {"kingdom_id": "asturias", "name": "Ducado de Galicia"}},
    "condados": [
        {"id": "C_BRAGA", "name": "Condado de Braga", "lon": -8.43, "lat": 41.55,
         "kingdom_id": "asturias", "duchy_id": "galicia"},
    ],
    "baronies": {"C_BRAGA": [{"name": "Baronia de Braga", "lon": -8.43, "lat": 41.55}]},
}
_VALID_JSON = json.dumps(_VALID_PAYLOAD)


# ─── Claude ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claude_provider_calls_anthropic_messages_stream():
    """ClaudeProvider.research uses model='claude-sonnet-4-6' and tool_use."""
    from medieval_forge.services.llm.claude import ClaudeProvider

    # Build a fake tool_use block matching the SDK shape
    tool_block = SimpleNamespace(type="tool_use", input=_VALID_PAYLOAD)
    final_message = SimpleNamespace(content=[tool_block])

    # Fake stream context manager
    class _FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        @property
        def text_stream(self):
            async def _gen():
                yield "partial"
            return _gen()

        async def get_final_message(self):
            return final_message

    _captured: dict = {}

    class _FakeMessages:
        def stream(self, **kwargs):
            _captured.update(kwargs)
            return _FakeStream()

    class _FakeClient:
        messages = _FakeMessages()

    provider = ClaudeProvider()
    with patch("medieval_forge.services.llm.claude.AsyncAnthropic", return_value=_FakeClient()):
        result = await provider.research("prompt", ResearchResult, {"key": "test-key"}, None)

    assert isinstance(result, ResearchResult)
    assert _captured.get("model") == "claude-sonnet-4-6"
    assert "tool_choice" in _captured


# ─── OpenAI ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_provider_uses_response_format_json_schema():
    """OpenAIProvider.research uses response_format=json_schema and stream=True."""
    from medieval_forge.services.llm.openai import OpenAIProvider

    _captured: dict = {}

    # Build a fake async stream of chunks
    async def _fake_stream():
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=_VALID_JSON))]
        )

    class _FakeCompletions:
        async def create(self, **kwargs):
            _captured.update(kwargs)
            return _fake_stream()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    provider = OpenAIProvider()
    with patch("medieval_forge.services.llm.openai.AsyncOpenAI", return_value=_FakeClient()):
        result = await provider.research("prompt", ResearchResult, {"key": "test-key"}, None)

    assert isinstance(result, ResearchResult)
    assert _captured.get("response_format", {}).get("type") == "json_schema"
    assert _captured.get("stream") is True


# ─── Gemini ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_provider_uses_response_mime_type_application_json():
    """GeminiProvider.research uses response_mime_type='application/json'."""
    from medieval_forge.services.llm.gemini import GeminiProvider

    _captured_config = {}

    class _FakeAioModels:
        async def generate_content(self, model, contents, config):
            _captured_config["config"] = config
            return SimpleNamespace(text=_VALID_JSON)

    class _FakeAio:
        models = _FakeAioModels()

    class _FakeClient:
        aio = _FakeAio()

    provider = GeminiProvider()
    with patch("medieval_forge.services.llm.gemini.genai") as mock_genai:
        mock_genai.Client.return_value = _FakeClient()
        result = await provider.research(
            "prompt", ResearchResult, {"api_key": "test-key"}, None
        )

    assert isinstance(result, ResearchResult)
    config = _captured_config["config"]
    assert config.response_mime_type == "application/json"
    # response_schema is intentionally NOT set: Gemini rejects additionalProperties
    # which Pydantic emits for dict[str, X] fields (kingdoms, duchies, baronies).
    # Plain JSON mode + prompt-based format spec is used instead (see gemini.py).
    assert config.response_schema is None


# ─── Ollama ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_provider_uses_grammar_constrained_format():
    """OllamaProvider.research passes a JSON schema dict as format (grammar-constrained decoding) and stream=False."""
    from medieval_forge.services.llm.ollama import OllamaProvider

    _captured: dict = {}

    class _FakeAsyncClient:
        async def chat(self, **kwargs):
            _captured.update(kwargs)
            return {"message": {"content": _VALID_JSON}}

    provider = OllamaProvider()
    with patch(
        "medieval_forge.services.llm.ollama.AsyncClient",
        return_value=_FakeAsyncClient(),
    ):
        result = await provider.research("prompt", ResearchResult, None, None)

    assert isinstance(result, ResearchResult)
    assert isinstance(_captured.get("format"), dict)
    assert _captured.get("format", {}).get("title") == "ResearchResult"
    assert _captured.get("stream") is False


# ─── Health check ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_health_check_handles_missing_credentials():
    """Each provider's health_check(None) returns HealthStatus(healthy=False) without raising."""
    from medieval_forge.services.llm import PROVIDERS, HealthStatus

    for name, provider in PROVIDERS.items():
        status = await provider.health_check(None)
        assert isinstance(status, HealthStatus), f"{name} health_check did not return HealthStatus"
        # Ollama may return True if the server happens to be running locally; that's fine.
        # For providers that require API keys (claude, openai, gemini), healthy must be False.
        if name in ("claude", "openai", "gemini"):
            assert status.healthy is False, (
                f"{name}.health_check(None) returned healthy=True — expected False when no key"
            )
        assert isinstance(status.message, str)
