"""Tests for Plan 04-01 D-02: version_token determinism + isolation.

Verifies:
  - compute_version_token is stable across two calls with identical args
  - smooth_sigma change does NOT invalidate median token (reads-scoped)
  - median_passes change DOES invalidate median token
  - upstream token change cascades (smooth token changes when median token changes)
"""
from __future__ import annotations

import pytest

from dataclasses import replace

from medieval_forge.services.pipeline.dag import (
    compute_version_token,
    STAGE_READS,
    DAG_ORDER,
)
from medieval_forge.services.pipeline.region_loader import load_region

pytestmark = pytest.mark.unit


def test_token_stable_across_runs() -> None:
    """Same inputs produce the same 16-char token every call."""
    cfg = load_region("iberia_868")
    tok1 = compute_version_token("median", STAGE_READS["median"], cfg, [])
    tok2 = compute_version_token("median", STAGE_READS["median"], cfg, [])
    assert tok1 == tok2
    assert len(tok1) == 16


def test_sigma_change_does_not_invalidate_median() -> None:
    """smooth_sigma is not in STAGE_READS['median'] — median token must be identical."""
    cfg_a = replace(load_region("iberia_868"), smooth_sigma=3.0)
    cfg_b = replace(load_region("iberia_868"), smooth_sigma=4.5)

    tok_a = compute_version_token("median", STAGE_READS["median"], cfg_a, [])
    tok_b = compute_version_token("median", STAGE_READS["median"], cfg_b, [])
    assert tok_a == tok_b, (
        "smooth_sigma change must NOT invalidate the median token "
        "(median reads only median_passes)"
    )


def test_median_passes_change_invalidates_median() -> None:
    """median_passes IS in STAGE_READS['median'] — changing it must change the token."""
    cfg_a = replace(load_region("iberia_868"), median_passes=8)
    cfg_b = replace(load_region("iberia_868"), median_passes=4)

    tok_a = compute_version_token("median", STAGE_READS["median"], cfg_a, [])
    tok_b = compute_version_token("median", STAGE_READS["median"], cfg_b, [])
    assert tok_a != tok_b, (
        "changing median_passes must produce a different median token"
    )


def test_upstream_token_change_cascades() -> None:
    """When the upstream (median) token changes, the smooth token must also change."""
    cfg = load_region("iberia_868")
    upstream_tok_a = "deadbeef12345678"
    upstream_tok_b = "cafebabe87654321"

    smooth_tok_a = compute_version_token(
        "smooth", STAGE_READS["smooth"], cfg, [upstream_tok_a]
    )
    smooth_tok_b = compute_version_token(
        "smooth", STAGE_READS["smooth"], cfg, [upstream_tok_b]
    )
    assert smooth_tok_a != smooth_tok_b, (
        "upstream token change must cascade: smooth token must differ "
        "when its upstream (median) token differs"
    )
