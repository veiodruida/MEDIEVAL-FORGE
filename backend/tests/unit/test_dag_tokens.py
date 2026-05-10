"""Wave 0 stub for Plan 04-01 — DO NOT remove imports.

Each test is `pytest.skip`-marked; Plan 04-01 implementation removes the skip
and fills the body. Keeping the skipped functions present lets `pytest --collect-only`
catch typos in test names referenced by 04-VALIDATION.md and lets <verify>
commands in implementation plans return exit 0 (skipped, not errored).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_token_stable_across_runs() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_sigma_change_does_not_invalidate_median() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_median_passes_change_invalidates_median() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_upstream_token_change_cascades() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")
