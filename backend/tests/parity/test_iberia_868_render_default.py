"""Wave 0 stub for Plan 04-02 — DO NOT remove imports.

Each test is `pytest.skip`-marked; Plan 04-02 implementation removes the skip
and fills the body. Keeping the skipped functions present lets `pytest --collect-only`
catch typos in test names referenced by 04-VALIDATION.md and lets <verify>
commands in implementation plans return exit 0 (skipped, not errored).

# This test runs only when --run-parity is implicitly enabled by the marker config
# in pyproject.toml (consistent with test_iberia_868.py)
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.parity


def test_render_at_default_cfg_matches_generate_byte_equal() -> None:
    pytest.skip("Wave 0 stub — Plan 04-02 implements")
