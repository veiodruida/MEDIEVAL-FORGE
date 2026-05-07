"""Surface-level checks for the v3 pipeline module.

Verifies that `run_pipeline` exists with the single-cfg signature mandated
by D-03/D-14 (RegionConfig is the only mutable input), and that
`RegionConfig` is a dataclass per RESEARCH §2.b.
"""
from __future__ import annotations

import inspect
from dataclasses import is_dataclass

from medieval_forge.services.pipeline import RegionConfig, run_pipeline


def test_run_pipeline_signature() -> None:
    sig = inspect.signature(run_pipeline)
    params = list(sig.parameters.keys())
    assert params == ["cfg"], f"expected single cfg arg, got {params}"
    ann = sig.parameters["cfg"].annotation
    assert ann is RegionConfig or ann == "RegionConfig", (
        f"cfg parameter must be annotated as RegionConfig; got {ann!r}"
    )


def test_region_config_is_dataclass() -> None:
    assert is_dataclass(RegionConfig), (
        "RegionConfig must be @dataclass per RESEARCH §2.b "
        "(drift from inicio is the hard cost; pydantic earns nothing Phase 01 needs)"
    )
