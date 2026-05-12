"""Plan 03-01 Task 2: cfg.on_stage callback contract.

Verifies:
- RegionConfig instantiates with on_stage=None (Phase 01 parity guarantee)
- run_pipeline emits 24 events in canonical order when on_stage is wired (12 stages × 2)
- Callback exceptions propagate (SSE producer wraps and reports)

The full pipeline run is shared with the parity test fixture for cost; this
file relies on a minimal "spy" callable that captures the (stage, evt) tuples
without doing any I/O of its own.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dataclasses import replace

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.contracts import RegionConfig
from medieval_forge.services.pipeline.region_loader import load_region


CANONICAL_STAGES = (
    "landmask", "border", "voronoi",
    "median", "fragment", "smooth", "merge",  # Plan 04-01: cleanup → median + fragment split
    "hierarchy", "render", "lookup",
    "metadata", "export",
)


def test_region_config_default_on_stage_is_none():
    """Phase 01 parity guarantee: cfg.on_stage defaults to None."""
    cfg = RegionConfig()
    assert cfg.on_stage is None


@pytest.mark.parity
def test_run_pipeline_emits_22_events_in_canonical_order(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """12 stages × {start, done} = 24 events, exact canonical order (Plan 04-01 split)."""
    out: Path = tmp_path_factory.mktemp("on_stage_full_run")
    cfg = replace(load_region("iberia_868"), output_dir=str(out))

    events: list[tuple[str, str]] = []
    cfg.on_stage = lambda stage, evt: events.append((stage, evt))

    run_pipeline(cfg)

    expected: list[tuple[str, str]] = []
    for stage in CANONICAL_STAGES:
        expected.append((stage, "start"))
        expected.append((stage, "done"))

    assert events == expected, (
        f"on_stage event sequence mismatch.\n"
        f"  expected ({len(expected)}): {expected}\n"
        f"  actual   ({len(events)}): {events}"
    )


def test_run_pipeline_propagates_callback_exception(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Exceptions raised inside on_stage MUST surface — Plan 02 SSE wraps them."""
    out: Path = tmp_path_factory.mktemp("on_stage_raise")
    cfg = replace(load_region("iberia_868"), output_dir=str(out))

    class _Boom(RuntimeError):
        pass

    def _raise_on_landmask_start(stage: str, evt: str) -> None:
        if (stage, evt) == ("landmask", "start"):
            raise _Boom("synthetic on_stage failure")

    cfg.on_stage = _raise_on_landmask_start

    with pytest.raises(_Boom):
        run_pipeline(cfg)
