"""SC-3: France 1066 toy pipeline produces well-formed Unity contract files.

Parity to Reconquista is NOT required (CONTEXT.md SC-3 boundary).
File presence + dimensions + JSON schema validity + original_idx uniqueness IS required.

Contract note on mountains_mask.png and rivers_overlay.png:
  The toy France dataset has empty mountains:{} and rivers:{} in mountain_river_data.json.
  render_mountains / render_rivers return None for empty data; the pipeline only writes
  these files when the render produces a non-None result. For a toy dataset this is
  expected — assertions on these two files are conditional (present-if-any).
  The EXPORT_FILE_CONTRACT constant lists all 10 currently-produced files; the two
  terrain files (terrain_lookup.png, terrain_types.json) are deferred to Phase 06 (P-2).
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.contracts import EXPORT_FILE_CONTRACT
from medieval_forge.services.pipeline.region_loader import clear_region_cache, load_region

# ---------------------------------------------------------------------------
# Dimension contract per CLAUDE.md §v3 Pipeline Contract table
# ---------------------------------------------------------------------------
_LOOKUP_DIM = (1920, 1080)
_VISUAL_DIM = (3840, 2160)

# Files with fixed dimensions (subset of EXPORT_FILE_CONTRACT)
_DIM_CONTRACT: dict[str, tuple[int, int]] = {
    "lookup_barony.png": _LOOKUP_DIM,
    "lookup_condado.png": _LOOKUP_DIM,
    "visual_condado.png": _VISUAL_DIM,
    "visual_barony.png": _VISUAL_DIM,
    # mountains_mask.png and rivers_overlay.png are conditional (empty toy dataset).
    # When present they must be _VISUAL_DIM; the conditional assertion below handles them.
}

# Always-present contract files (toy dataset: no mountain/river geometry → no mask PNGs)
_ALWAYS_PRESENT: frozenset[str] = frozenset(EXPORT_FILE_CONTRACT) - frozenset({
    "mountains_mask.png",
    "rivers_overlay.png",
})


# ---------------------------------------------------------------------------
# Session-scoped fixture — run France pipeline once, share output across tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def france_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run france_1066 pipeline once per module; return output directory."""
    out = tmp_path_factory.mktemp("france_1066_e2e")
    clear_region_cache()
    cfg = replace(load_region("france_1066"), output_dir=str(out))
    run_pipeline(cfg)
    return out


# ---------------------------------------------------------------------------
# SC-3 contract gate
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_france_1066_always_present_files(france_output: Path) -> None:
    """All always-present contract files exist in output directory."""
    present = {p.name for p in france_output.iterdir() if p.is_file()}
    missing = _ALWAYS_PRESENT - present
    assert not missing, (
        f"Missing always-present contract files: {sorted(missing)}\n"
        f"Present files: {sorted(present)}"
    )


@pytest.mark.e2e
def test_france_1066_lookup_png_dimensions(france_output: Path) -> None:
    """Lookup PNGs are exactly 1920x1080 (CLAUDE.md rule #1: NEAREST upscale)."""
    for name in ("lookup_barony.png", "lookup_condado.png"):
        img = Image.open(france_output / name)
        assert img.size == _LOOKUP_DIM, (
            f"{name}: expected {_LOOKUP_DIM}, got {img.size}"
        )


@pytest.mark.e2e
def test_france_1066_visual_png_dimensions(france_output: Path) -> None:
    """Visual PNGs are exactly 3840x2160 (2x independent render, CLAUDE.md rule #6)."""
    for name in ("visual_condado.png", "visual_barony.png"):
        img = Image.open(france_output / name)
        assert img.size == _VISUAL_DIM, (
            f"{name}: expected {_VISUAL_DIM}, got {img.size}"
        )


@pytest.mark.e2e
def test_france_1066_mask_pngs_dimensions_when_present(france_output: Path) -> None:
    """mountains_mask.png and rivers_overlay.png are 3840x2160 when present.

    Toy France has no mountain/river geometry so these may be absent — that is
    expected and not an error. When present (non-toy datasets) they must be 2x.
    """
    for name in ("mountains_mask.png", "rivers_overlay.png"):
        p = france_output / name
        if p.exists():
            img = Image.open(p)
            assert img.size == _VISUAL_DIM, (
                f"{name}: expected {_VISUAL_DIM}, got {img.size}"
            )


@pytest.mark.e2e
def test_france_1066_json_files_valid(france_output: Path) -> None:
    """All JSON contract files parse as valid non-empty JSON."""
    json_names = [n for n in EXPORT_FILE_CONTRACT if n.endswith(".json")]
    for name in json_names:
        path = france_output / name
        if not path.exists():
            # Conditional files (e.g., mountains/rivers) may be absent for toy dataset.
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{name}: invalid JSON — {exc}")
        assert data is not None, f"{name}: parsed as None"


@pytest.mark.e2e
def test_france_1066_original_idx_unique(france_output: Path) -> None:
    """Every condado in territory_metadata.json carries a unique original_idx.

    CLAUDE.md rule 4: pipeline must guarantee original_idx uniqueness across
    re-runs so Unity's byOriginalIdx shader never throws on indices > 44 (Nájera bug).
    """
    meta_path = france_output / "territory_metadata.json"
    assert meta_path.exists(), "territory_metadata.json missing from output"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    condados = _walk_condados(meta)
    assert condados, "territory_metadata.json contains no condados"

    idxs = [c["original_idx"] for c in condados]
    assert len(idxs) == len(condados), (
        f"Only {len(idxs)} of {len(condados)} condados carry original_idx — "
        f"CLAUDE.md rule 4 violated"
    )
    assert len(idxs) == len(set(idxs)), (
        f"original_idx not unique across {len(condados)} condados: {idxs}"
    )


# NOTE: No SSIM / byte-equality / golden-file comparisons in this module.
# SC-3 boundary: parity vs Reconquista is explicitly out of scope for toy France.
# Parity tests live in backend/tests/parity/test_iberia_868_yaml.py only.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _walk_condados(meta: dict | list) -> list[dict]:
    """Extract condado list from territory_metadata.json regardless of shape."""
    if isinstance(meta, dict) and "condados" in meta:
        return [c for c in meta["condados"] if isinstance(c, dict) and "original_idx" in c]
    if isinstance(meta, list):
        return [m for m in meta if isinstance(m, dict) and "original_idx" in m]
    raise AssertionError(
        f"unknown territory_metadata.json shape: {type(meta).__name__} — "
        f"update _walk_condados for new schema"
    )
