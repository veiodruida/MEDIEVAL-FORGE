"""Wave 0 stub for Plan 04-01 — DO NOT remove imports.

Each test is `pytest.skip`-marked; Plan 04-01 implementation removes the skip
and fills the body. Keeping the skipped functions present lets `pytest --collect-only`
catch typos in test names referenced by 04-VALIDATION.md and lets <verify>
commands in implementation plans return exit 0 (skipped, not errored).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_cache_put_then_get_returns_entry() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_second_put_promotes_prior() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_clear_project_removes_all_entries() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_concurrent_put_get_thread_safe() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")
