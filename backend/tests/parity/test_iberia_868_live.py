"""Live-input parity vs the SAME golden as test_iberia_868.py (D-11).

Two paths, one expected output (D-09 + D-11):
  - Phase 01 path: iberia_config() vendored ProjectDataset → run_pipeline → assert vs golden/
  - Phase 02 live path: ProjectDataset built from committed live-ingestion snapshot
                         → run_pipeline → assert vs THE SAME golden/

Live-parity strategy is the WAIVER LOOP (Plan 03 <approach> block):
  if any test fails, run scripts/refresh_live_snapshot.py and re-commit.
  SSIM thresholds are NEVER relaxed — they match test_iberia_868.py exactly.

Mirror of test_iberia_868.py with one substitution: the pipeline_output
fixture is renamed live_pipeline_output and overrides cfg.dataset.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.contracts import ProjectDataset
from medieval_forge.services.pipeline.regions import iberia_config

pytestmark = pytest.mark.parity

# backend/tests/parity/test_iberia_868_live.py -> repo root (parents[3]) — matches conftest convention.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_SNAPSHOT_DIR = REPO_ROOT / "tests" / "fixtures" / "iberia_868" / "live-ingestion"
VENDORED_MOUNTAIN_RIVER = REPO_ROOT / "data" / "regions" / "iberia_868" / "inputs" / "mountain_river_data.json"


@pytest.fixture(scope="session")
def live_pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the pipeline once with ProjectDataset built from the committed live snapshot."""
    pt_path = LIVE_SNAPSHOT_DIR / "pt_concelhos_live.geojson"
    es_path = LIVE_SNAPSHOT_DIR / "es_municipalities_live.geojson"
    if not pt_path.exists() or not es_path.exists():
        pytest.fail(
            f"Live-ingestion snapshot missing — run\n"
            f"    py -3.14 scripts/refresh_live_snapshot.py --region iberia_868\n"
            f"  to create:\n    {pt_path}\n    {es_path}\n"
            f"Then commit with: docs(parity): refresh live snapshot"
        )

    cfg = iberia_config()
    cfg.dataset = ProjectDataset(
        pt_geojson=pt_path,
        es_input=es_path,
        mountain_river_json=VENDORED_MOUNTAIN_RIVER,  # D-13: terrain stub uses vendored
    )
    out = tmp_path_factory.mktemp("iberia_868_live_actual")
    cfg.output_dir = str(out)
    run_pipeline(cfg)
    return out


# --- Lookup PNGs: byte-equal (mirrors test_iberia_868.py — same threshold) ---
@pytest.mark.parametrize("name", ["lookup_barony.png", "lookup_condado.png"])
def test_live_lookup_png_byte_equal(live_pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = np.array(Image.open(live_pipeline_output / name))
    golden = np.array(Image.open(golden_dir / name))
    if not np.array_equal(actual, golden):
        diff_path = live_pipeline_output / f"DIFF_{name}"
        if actual.shape == golden.shape:
            mismatch = np.any(actual != golden, axis=-1) if actual.ndim == 3 else (actual != golden)
            Image.fromarray((mismatch * 255).astype(np.uint8)).save(diff_path)
        pytest.fail(
            f"LIVE {name}: pixel-mismatch.\n"
            f"  golden: {golden_dir / name}\n"
            f"  actual: {live_pipeline_output / name}\n"
            f"  diff:   {diff_path}\n"
            f"Waiver loop: snapshot may be stale — see Plan 03 <approach>."
        )


# --- Visual PNGs + masks: SSIM >= 0.98 (mirrors test_iberia_868.py — same threshold) ---
@pytest.mark.parametrize(
    "name",
    ["visual_condado.png", "visual_barony.png", "mountains_mask.png", "rivers_overlay.png"],
)
def test_live_visual_png_ssim(live_pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = np.array(Image.open(live_pipeline_output / name).convert("RGB"))
    golden = np.array(Image.open(golden_dir / name).convert("RGB"))
    score = ssim(actual, golden, channel_axis=2, data_range=255)
    assert score >= 0.98, (
        f"LIVE {name}: SSIM {score:.4f} < 0.98.\n"
        f"  golden: {golden_dir / name}\n"
        f"  actual: {live_pipeline_output / name}\n"
        f"Waiver loop: snapshot may be stale — see Plan 03 <approach>."
    )


# --- JSONs: deep-equal after recursive key-sort (mirrors test_iberia_868.py exactly) ---
def _normalise(obj):
    if isinstance(obj, dict):
        return {k: _normalise(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalise(x) for x in obj]
    return obj


@pytest.mark.parametrize(
    "name",
    [
        "lookup_barony_colors.json",
        "lookup_condado_colors.json",
        "territory_metadata.json",
        "mountain_river_data.json",
    ],
)
def test_live_json_deep_equal(live_pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = _normalise(json.loads((live_pipeline_output / name).read_text(encoding="utf-8")))
    golden = _normalise(json.loads((golden_dir / name).read_text(encoding="utf-8")))
    assert actual == golden, (
        f"LIVE {name}: JSON mismatch.\n"
        f"  hint: diff <(jq -S . {golden_dir / name}) <(jq -S . {live_pipeline_output / name})\n"
        f"Waiver loop: snapshot may be stale — see Plan 03 <approach>."
    )
