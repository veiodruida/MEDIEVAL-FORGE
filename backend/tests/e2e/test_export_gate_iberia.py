"""SC-4-Iberia + SC-3: Iberia 868 passes the Phase 06 export gate.

Calls validate_export() directly against the pipeline output. Asserts:
- report.passed == True
- report.errors == []
- Every D-08 code: 0 occurrences (per-code coverage matrix Iberia column)

Distinct from tests/parity/test_iberia_868_yaml.py:test_iberia_passes_export_gate
-- the parity version is part of the parity suite (gates parity regression);
this e2e version is a standalone smoke for the gate at a higher latency.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from medieval_forge.services.export import validate_export
from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def iberia_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run Iberia pipeline once per module -- heavy (~30s)."""
    out = tmp_path_factory.mktemp("iberia_e2e_gate")
    clear_region_cache()
    cfg = replace(load_region("iberia_868"), output_dir=str(out))
    run_pipeline(cfg)
    return out


def test_iberia_passes_export_gate(iberia_output: Path) -> None:
    cfg = load_region("iberia_868")
    report, sha256_by_file = validate_export(iberia_output, cfg)

    if not report.passed:
        error_summary = "\n".join(
            f"  - [{e.code}] {e.file or '-'}: {e.message}" for e in report.errors
        )
        pytest.fail(
            f"Iberia 868 FAILED Phase 06 export gate ({len(report.errors)} errors):\n"
            f"{error_summary}"
        )

    assert report.passed is True
    assert report.errors == []
    # Per-code coverage: every D-08 code = 0 occurrences on a clean Iberia run
    codes = {e.code for e in report.errors}
    assert "MISSING_ORIGINAL_IDX" not in codes
    assert "OCEAN_LEAK" not in codes
    assert "COLOR_COLLISION" not in codes
    assert "TERRITORY_TOO_SMALL" not in codes
    assert "PIXEL_CENTER_OUT_OF_RANGE" not in codes
    assert "SCHEMA_INVALID" not in codes

    # SC-3: MANIFEST contract -- every file the validator read got a sha256
    assert len(sha256_by_file) >= 10  # 10-12 files depending on toy mountain_river
