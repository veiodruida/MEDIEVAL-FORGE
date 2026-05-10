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
    # Phase 04: run_pipeline gains optional project_id=None for cache population
    # (D-13: prior arrays available for /render cancel revert). The parameter is
    # optional with a None default so all existing Phase 01 callers are unaffected.
    assert "cfg" in params, f"run_pipeline must accept 'cfg' as first arg; got {params}"
    ann = sig.parameters["cfg"].annotation
    assert ann is RegionConfig or ann == "RegionConfig", (
        f"cfg parameter must be annotated as RegionConfig; got {ann!r}"
    )
    if "project_id" in params:
        # project_id must be optional (default None) — preserves Phase 01 CLI parity
        p = sig.parameters["project_id"]
        assert p.default is None, (
            f"project_id must default to None (Phase 01 CLI compat); got {p.default!r}"
        )


def test_region_config_is_dataclass() -> None:
    assert is_dataclass(RegionConfig), (
        "RegionConfig must be @dataclass per RESEARCH §2.b "
        "(drift from inicio is the hard cost; pydantic earns nothing Phase 01 needs)"
    )
