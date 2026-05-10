"""Wave 0 stub for Plan 04-01 — DO NOT remove imports.

Each test is `pytest.skip`-marked; Plan 04-01 implementation removes the skip
and fills the body. Keeping the skipped functions present lets `pytest --collect-only`
catch typos in test names referenced by 04-VALIDATION.md and lets <verify>
commands in implementation plans return exit 0 (skipped, not errored).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_apply_median_does_not_mutate_input() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_apply_median_default_cfg_matches_monolith() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_remove_fragments_does_not_mutate_input() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_smooth_per_territory_returns_new_array() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_merge_small_blobs_does_not_mutate_input() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")


def test_split_chain_default_cfg_matches_cleanup_and_smooth() -> None:
    pytest.skip("Wave 0 stub — Plan 04-01 implements")
