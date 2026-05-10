"""Wave 0 stub for Plan 04-02 — DO NOT remove imports.

Each test is `pytest.skip`-marked; Plan 04-02 implementation removes the skip
and fills the body. Keeping the skipped functions present lets `pytest --collect-only`
catch typos in test names referenced by 04-VALIDATION.md and lets <verify>
commands in implementation plans return exit 0 (skipped, not errored).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_cancel_during_median_returns_within_2s() -> None:
    pytest.skip("Wave 0 stub — Plan 04-02 implements")


def test_cancel_emits_stage_cancel_per_affected_stage() -> None:
    pytest.skip("Wave 0 stub — Plan 04-02 implements")


def test_cancel_on_first_render_falls_back_to_generate_baseline() -> None:
    pytest.skip("Wave 0 stub — Plan 04-02 implements")


def test_cancel_does_not_update_cache() -> None:
    pytest.skip("Wave 0 stub — Plan 04-02 implements")
