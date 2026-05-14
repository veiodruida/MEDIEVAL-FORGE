"""ClaudeProvider — AsyncAnthropic + tool_use + D-07 auth chain (Plan 07-04 Task 1).

Source: 07-RESEARCH.md §Pattern 3 (full code block) + BLOCKER 1 fix.

D-07 auth chain (resolved INSIDE the provider, NOT by the runner):
    (1) CLI piggyback  -> _read_claude_cli_token()
    (2) DB payload     -> credential_store-backed dict
    (3) ANTHROPIC_API_KEY env
    (4) None (caller raises)

BLOCKER 1 (REVIEWS 2026-05-14): the CLI token returned by `claude auth status`
may be a consumer-OAuth token (claude.ai) that the Anthropic API will reject
with `anthropic.AuthenticationError` (HTTP 401). When that happens, the
provider retries ONCE with `skip_cli=True` so the chain falls through to DB/env.
This logic lives at the PROVIDER level — the research runner (Plan 07b) only
propagates exceptions.

Pitfall 4 + RESEARCH §Pattern 3 + VALIDATION row 07-00-W0-AUTH covered by
backend/tests/integration/test_claude_auth_chain.py (5 cases, @pytest.mark.anthropic).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time

import anthropic
from anthropic import AsyncAnthropic

from .base import ApiKeyAuth, CliAuth, HealthStatus

SYSTEM_PROMPT = (
    "You are a historical-research assistant. "
    "Return JSON via the submit_research tool."
)

# D-09 placeholder model id (CONTEXT.md). Update when a stable production
# model id is selected.
CLAUDE_MODEL = "claude-sonnet-4-6"


def _read_claude_cli_token() -> str | None:
    """D-07 step 1: try `claude auth status` shell-out; fall back to direct file read.

    `claude auth status` returns 0 + 'You are logged in as ...' on success.
    File at `~/.claude/.credentials.json` carries OAuth tokens with `expiresAt`
    as epoch-ms. Consumer auth (claude.ai) may NOT grant API access — see
    Pitfall 4 + BLOCKER 1 401-retry block in ClaudeProvider.research().

    T-07-04-04 mitigation: `shell=False` hardcoded argv (no user input).
    T-07-04-05 mitigation: `timeout=3.0` to bound subprocess wait.
    """
    # Try CLI first — cleanest, version-stable
    try:
        result = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=3.0)
        # CLI exits 0 if logged in; if exit non-zero, fall through to file read.
        if result.returncode != 0:
            pass  # fall through; CLI not authenticated
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass  # claude binary not installed — fall through to file read

    # File read (cross-platform).
    candidates = [
        pathlib.Path.home() / ".claude" / ".credentials.json",
        pathlib.Path(os.environ.get("APPDATA", "")) / "Claude" / "credentials.json",
        pathlib.Path(
            os.environ.get("XDG_CONFIG_HOME", str(pathlib.Path.home() / ".config"))
        )
        / "claude"
        / "credentials.json",
    ]
    for path in candidates:
        try:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            token_data = data.get("claudeAiOauth", {})
            access_token = token_data.get("accessToken")
            expires_at_ms = token_data.get("expiresAt", 0)
            # T-07-04-01 mitigation: enforce expiry epoch-ms check.
            if access_token and expires_at_ms > time.time() * 1000:
                return access_token
        except (json.JSONDecodeError, OSError):
            continue
    return None


class ClaudeProvider:
    """Anthropic Claude provider with D-07 auth chain + BLOCKER 1 401-retry."""

    provider_id = "claude"
    display_name = "Claude (Anthropic)"
    auth_methods = [
        CliAuth(cli_command="claude", auth_file_path="~/.claude/.credentials.json"),
        ApiKeyAuth(env_var="ANTHROPIC_API_KEY"),
        ApiKeyAuth(env_var=None),  # dialog paste -> persisted to DB by Plan 01
    ]

    def _resolve_key(self, db_payload: dict | None, skip_cli: bool = False) -> str | None:
        """D-07 chain order: (1) CLI if not skip_cli -> (2) DB -> (3) env -> (4) None.

        Args:
            db_payload: credentials dict returned by credential_store.get_credentials.
                        Shape: {"type": "api_key", "key": "...", ...} or None.
            skip_cli: when True, skips step 1 (used by BLOCKER 1 401-retry path).
        """
        if not skip_cli:
            cli_token = _read_claude_cli_token()
            if cli_token:
                return cli_token
        if db_payload and db_payload.get("key"):
            return db_payload["key"]
        env_key = os.getenv("ANTHROPIC_API_KEY")
        if env_key:
            return env_key
        return None

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        key = self._resolve_key(credentials, skip_cli=False)
        if not key:
            return HealthStatus(
                healthy=False,
                message="No credentials (CLI/DB/env/dialog all empty)",
            )
        return HealthStatus(healthy=True, message="Credentials present")

    async def _do_research(self, key, prompt, schema, queue):
        """Single Anthropic call. Raises anthropic.AuthenticationError on 401."""
        client = AsyncAnthropic(api_key=key)
        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": "submit_research",
                    "description": "Submit structured research result",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_research"},
        ) as stream:
            async for text in stream.text_stream:
                if queue is not None and text:
                    await queue.put(
                        "data: "
                        + json.dumps({"event_type": "token", "message": text})
                        + "\n\n"
                    )
            final = await stream.get_final_message()
        tool_block = next(
            b for b in final.content if getattr(b, "type", None) == "tool_use"
        )
        return schema.model_validate(tool_block.input)

    async def research(self, prompt, schema, credentials, queue):
        """BLOCKER 1: try CLI key first; on 401 retry once with skip_cli=True.

        The retry intentionally re-resolves the chain. If skip_cli=True yields
        the same key (or None) we re-raise — the chain is exhausted.
        """
        key = self._resolve_key(credentials, skip_cli=False)
        if key is None:
            raise RuntimeError(
                "No Claude credentials available (CLI/DB/env all empty)."
            )
        try:
            return await self._do_research(key, prompt, schema, queue)
        except anthropic.AuthenticationError:
            # Pitfall 4: CLI token may be consumer-OAuth without API access.
            # Retry once skipping CLI, falling through to DB -> env -> dialog.
            retry_key = self._resolve_key(credentials, skip_cli=True)
            if retry_key is None or retry_key == key:
                raise  # nothing more to try; chain exhausted
            return await self._do_research(retry_key, prompt, schema, queue)
