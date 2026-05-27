"""Iberia 868 YAML parity gate — Plan 05-03 (D-14).

Proves that loading via load_region('iberia_868') produces byte-equal lookup
PNGs, SSIM >= 0.98 visual PNGs, and deep-equal JSONs compared to the same
Phase 01 golden fixtures used by test_iberia_868.py.

This gate MUST stay green until Plan 05-05 deletes iberia_config() from
regions.py (D-17 step 3 invariant: both parity tests pass simultaneously).

10 parametrised tests across 3 functions (mirrors test_iberia_868.py exactly):
  - test_lookup_png_byte_equal_yaml (x2): lookup_barony.png, lookup_condado.png
  - test_visual_png_ssim_yaml (x4): visual_condado/visual_barony/mountains_mask/rivers_overlay
  - test_json_deep_equal_yaml (x4): lookup_*_colors, territory_metadata, mountain_river_data

Plus canvas sidecar existence test (mirrors test_canvas_sidecars_exist).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache

pytestmark = pytest.mark.parity


@pytest.fixture(scope="session")
def pipeline_output_yaml(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the v3 pipeline once per session using load_region, return output dir.

    Session-scoped to match the cost profile of test_iberia_868.py — the full
    Iberia pipeline runs once and all 10 parity tests share the output.
    """
    out = tmp_path_factory.mktemp("iberia_868_yaml_actual")
    clear_region_cache()
    # WR-02 fix (Plan 05-14): dataclasses.replace() builds a fresh per-call copy.
    # Direct cfg.output_dir = ... mutates the cached singleton (Pitfall 9 /
    # T-05-04-04) — clear_region_cache_between_tests autouse hides this in
    # serial CI, but pytest-xdist parallel workers would corrupt each other's
    # output_dir. Match the replace() pattern established in
    # test_france_1066_export_contract.py and api/v3/render.py:137-141.
    cfg = replace(load_region("iberia_868"), output_dir=str(out))
    run_pipeline(cfg)
    return out


# --- Lookup PNGs: byte-equal (terrain_lookup.png deferred to Phase 06 per P-2) ---
@pytest.mark.parametrize("name", ["lookup_barony.png", "lookup_condado.png"])
def test_lookup_png_byte_equal_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = np.array(Image.open(pipeline_output_yaml / name))
    golden = np.array(Image.open(golden_dir / name))
    if not np.array_equal(actual, golden):
        diff_path = pipeline_output_yaml / f"DIFF_{name}"
        if actual.shape == golden.shape:
            mismatch = np.any(actual != golden, axis=-1) if actual.ndim == 3 else (actual != golden)
            Image.fromarray((mismatch * 255).astype(np.uint8)).save(diff_path)
        pytest.fail(
            f"{name}: pixel-mismatch (YAML-loaded cfg vs golden).\n"
            f"  golden: {golden_dir / name}\n"
            f"  actual: {pipeline_output_yaml / name}\n"
            f"  diff:   {diff_path}"
        )


# --- Visual PNGs + masks: SSIM >= 0.98 ---
@pytest.mark.parametrize(
    "name",
    ["visual_condado.png", "visual_barony.png", "mountains_mask.png", "rivers_overlay.png"],
)
def test_visual_png_ssim_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = np.array(Image.open(pipeline_output_yaml / name).convert("RGB"))
    golden = np.array(Image.open(golden_dir / name).convert("RGB"))
    score = ssim(actual, golden, channel_axis=2, data_range=255)
    assert score >= 0.98, (
        f"{name}: SSIM {score:.4f} < 0.98 (YAML-loaded cfg vs golden).\n"
        f"  golden: {golden_dir / name}\n"
        f"  actual: {pipeline_output_yaml / name}"
    )


# --- JSONs: deep-equal after recursive key-sort (terrain_types.json deferred per P-2) ---
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
def test_json_deep_equal_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = _normalise(json.loads((pipeline_output_yaml / name).read_text(encoding="utf-8")))
    golden = _normalise(json.loads((golden_dir / name).read_text(encoding="utf-8")))
    assert actual == golden, (
        f"{name}: JSON mismatch (YAML-loaded cfg vs golden).\n"
        f"  hint: diff <(jq -S . {golden_dir / name}) <(jq -S . {pipeline_output_yaml / name})"
    )


# --- Canvas sidecars exist + non-empty (mirrors test_canvas_sidecars_exist) ---
def test_canvas_sidecars_exist_yaml(pipeline_output_yaml: Path) -> None:
    sidecars = (
        "territories.geojson",
        "baronies.geojson",
        "condado_colors.json",
        "barony_colors.json",
    )
    for name in sidecars:
        p = pipeline_output_yaml / name
        assert p.is_file(), f"missing canvas sidecar: {name}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data, f"empty canvas sidecar: {name}"

    tj = json.loads((pipeline_output_yaml / "territories.geojson").read_text(encoding="utf-8"))
    assert tj["type"] == "FeatureCollection"
    assert len(tj["features"]) > 0, "territories.geojson has zero features"

    bj = json.loads((pipeline_output_yaml / "baronies.geojson").read_text(encoding="utf-8"))
    assert bj["type"] == "FeatureCollection"
    assert len(bj["features"]) > 0, "baronies.geojson has zero features"

    colors = json.loads((pipeline_output_yaml / "condado_colors.json").read_text(encoding="utf-8"))
    territory_ids = {f["id"] for f in tj["features"]}
    missing_colors = territory_ids - set(colors.keys())
    assert not missing_colors, (
        f"condado_colors.json missing {len(missing_colors)} entries: "
        f"{sorted(missing_colors)[:5]}"
    )


# --- D-16: MANIFEST.validation_report.passed assertion (Plan 06-03) ---

def test_iberia_passes_export_gate(pipeline_output_yaml: Path) -> None:
    """D-16: Iberia 868 YAML cfg must satisfy the Phase 06 export gate.

    Calls validate_export() directly against the pipeline output (no zip,
    no DB, no TestClient). Iberia's golden territory_metadata.json has
    original_idx 1..92 on all 91 emitted condados -> MISSING_ORIGINAL_IDX
    check passes per D-11 REVISED. Asserts passed=True and zero errors.

    Gate regression == parity break; CI catches this the same as a byte-mismatch.
    """
    from medieval_forge.services.export import validate_export
    from medieval_forge.services.pipeline.region_loader import load_region

    cfg = load_region("iberia_868")
    report, sha256_by_file = validate_export(pipeline_output_yaml, cfg)

    if not report.passed:
        error_summary = "\n".join(
            f"  - [{e.code}] {e.file or '-'}: {e.message}" for e in report.errors
        )
        pytest.fail(
            f"Iberia 868 YAML cfg FAILED the Phase 06 export gate "
            f"({len(report.errors)} errors):\n{error_summary}\n"
            f"This is a parity regression -- fix the validator or the pipeline."
        )

    assert report.passed is True
    assert report.errors == []
    # sha256 map covers every file the validator read (~10/12 files; mountain_river optional)
    assert len(sha256_by_file) >= 10, (
        f"validator only hashed {len(sha256_by_file)} files; expected >= 10"
    )


# ---------------------------------------------------------------------------
# Phase 08 Plan 10 (D-16 + Pitfall 4): manifest schema_version=3 + branch fields
# ---------------------------------------------------------------------------


def test_iberia_manifest_schema_version_is_3_and_branch_fields_are_none(
    pipeline_output_yaml: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-16 backward-compat (Pitfall 4): MANIFEST schema_version == 3; branch fields None.

    Non-branch Iberia gold path must emit schema_version=3 and have
    branch_name=None, snapshot_id=None, snapshot_timestamp=None in MANIFEST.json.
    This asserts the Phase 08 Plan 10 additive extension doesn't break the
    existing parity contract.
    """
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.export import build_unity_zip

    project_id = "00000000-0000-0000-0000-08100p10par0"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    pdir = paths_mod.project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "output").mkdir(parents=True, exist_ok=True)
    (pdir / "exports").mkdir(parents=True, exist_ok=True)
    for src in pipeline_output_yaml.iterdir():
        if src.is_file():
            (pdir / "output" / src.name).write_bytes(src.read_bytes())

    from dataclasses import replace as dc_replace
    from medieval_forge.services.pipeline.region_loader import load_region
    cfg = dc_replace(load_region("iberia_868"))
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="iberia_868")

    import zipfile as _zipfile
    with _zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))

    assert manifest["schema_version"] == 3, (
        f"expected schema_version=3, got {manifest['schema_version']!r}"
    )
    assert manifest.get("branch_name") is None, (
        f"expected branch_name=None for non-branch export, got {manifest.get('branch_name')!r}"
    )
    assert manifest.get("snapshot_id") is None, (
        f"expected snapshot_id=None for non-branch export, got {manifest.get('snapshot_id')!r}"
    )
    assert manifest.get("snapshot_timestamp") is None, (
        f"expected snapshot_timestamp=None for non-branch export, "
        f"got {manifest.get('snapshot_timestamp')!r}"
    )


# ---------------------------------------------------------------------------
# Plan 07-11 Task 1 — D-12 zero-LLM parity gate + REVIEWS fix #9 toggle parity
# ---------------------------------------------------------------------------
#
# Four new tests close Phase 07 SC #1 (zero-LLM works) at the parity layer:
#   - test_zero_llm_byte_identical (D-12)
#   - test_iberia_868_raw_metadata_uses_pipeline_slugs
#   - test_manifest_research_overlay_applied_false_for_iberia_baseline
#   - test_zip_diff_limited_to_zip_bound_fields_when_toggling_strict_tolerant
#     (REVIEWS fix #9 — parity-layer downgrade-path lock)
#
# Reuses the session-scoped `pipeline_output_yaml` fixture above so the
# Iberia pipeline still runs only once per session.


def test_zero_llm_byte_identical(
    pipeline_output_yaml: Path, golden_dir: Path
) -> None:
    """D-12 root gate (NON-skippable): Iberia 868 produces byte-identical
    artifacts WITHOUT any LLM/overlay involvement.

    Three assertions:
      (a) No `research_overlay.json` sidecar exists in or alongside the
          pipeline output directory — the geometric pipeline must never
          emit one.
      (b) Lookup PNGs + key JSONs are byte-equal to the committed golden
          (delegates to the same comparison logic as test_lookup_png_byte_equal_yaml
          and test_json_deep_equal_yaml, but as a single SC #1 anchor).
      (c) build_unity_zip on this output produces a MANIFEST with
          `research_overlay_applied == False` and a `territory_metadata.json`
          inside the zip whose sha256 matches the raw on-disk file
          (no overlay merge occurred).

    Phase 07 SC #1 anchor: if this test fails, the zero-LLM contract is broken.
    """
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.export import build_unity_zip

    # (a) No overlay sidecar anywhere near pipeline output.
    assert not (pipeline_output_yaml / "research_overlay.json").exists(), (
        "D-12: pipeline emitted a research_overlay.json into its output dir "
        "— the geometric pipeline must NEVER produce an overlay file"
    )
    assert not (pipeline_output_yaml.parent / "research_overlay.json").exists(), (
        "D-12: research_overlay.json found alongside pipeline output — "
        "geometric path must stay LLM-free"
    )

    # (b) Byte-equality vs golden for the two lookup PNGs (Phase 06 baseline).
    for name in ("lookup_barony.png", "lookup_condado.png"):
        actual = np.array(Image.open(pipeline_output_yaml / name))
        golden = np.array(Image.open(golden_dir / name))
        assert np.array_equal(actual, golden), (
            f"D-12 zero-LLM: {name} differs from Phase 06 golden — "
            f"a non-LLM regression broke parity"
        )

    # (c) build_unity_zip on this output → manifest.research_overlay_applied is False
    # and territory_metadata.json in the zip == raw on-disk bytes (no merge).
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Stage a minimal project_dir at a sandbox PROJECTS_ROOT so build_unity_zip
        # writes its zip somewhere safe. The stage copies pipeline output into
        # project_dir/output/ and creates exports/.
        project_id = "00000000-0000-0000-0000-d12d12d12d12"
        monkey_root = td_path / "projects"
        original_root = paths_mod.PROJECTS_ROOT
        paths_mod.PROJECTS_ROOT = monkey_root
        try:
            pdir = paths_mod.project_dir(project_id)
            pdir.mkdir(parents=True, exist_ok=True)
            output_dir = pdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            (pdir / "exports").mkdir(parents=True, exist_ok=True)
            for src in pipeline_output_yaml.iterdir():
                if src.is_file():
                    (output_dir / src.name).write_bytes(src.read_bytes())
            # Reload cfg fresh to avoid mutating cached singleton.
            cfg = replace(load_region("iberia_868"))
            zip_path = build_unity_zip(project_id, cfg=cfg, region_key="iberia_868")

            import hashlib as _hashlib
            import zipfile as _zipfile

            with _zipfile.ZipFile(zip_path) as zf:
                manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
                meta_in_zip = zf.read("territory_metadata.json")

            assert manifest["research_overlay_applied"] is False, (
                "D-12: MANIFEST.research_overlay_applied is True for Iberia "
                "baseline (no overlay file) — zero-LLM contract broken"
            )

            raw_meta = (output_dir / "territory_metadata.json").read_bytes()
            assert _hashlib.sha256(raw_meta).hexdigest() == _hashlib.sha256(
                meta_in_zip
            ).hexdigest(), (
                "D-12: territory_metadata.json bytes in zip differ from raw "
                "pipeline output — an overlay merge happened on a zero-overlay run"
            )
        finally:
            paths_mod.PROJECTS_ROOT = original_root


def test_iberia_868_raw_metadata_uses_pipeline_slugs(
    pipeline_output_yaml: Path,
) -> None:
    """Pipeline output retains curated slugs/names from territory_data_v3.py
    (no overlay applied at the pipeline boundary).

    Iberia's curated territory_data_v3.py emits human-readable names
    (`Oviedo`, `Pravia`, ...) and slug ids (`oviedo`, `pravia`, ...) directly
    from the pipeline — these are NOT overlay names. Asserts that the raw,
    on-disk metadata uses these pipeline-emitted slugs.
    """
    raw_meta = json.loads(
        (pipeline_output_yaml / "territory_metadata.json").read_text(encoding="utf-8")
    )
    condados = raw_meta["condados"]
    assert len(condados) > 0, "raw metadata has zero condados"

    # Every condado has a non-empty id AND name from the pipeline.
    for c in condados:
        assert c.get("id"), f"condado missing id: {c}"
        assert c.get("name"), f"condado missing name: {c}"
        # original_idx must survive (CLAUDE.md rule 4).
        assert "original_idx" in c, f"condado missing original_idx: {c}"

    # Sample: Iberia's first condado is curated as 'oviedo'/'Oviedo'.
    first = condados[0]
    assert first["id"] == "oviedo", (
        f"Iberia raw metadata first condado.id should be 'oviedo' "
        f"(pipeline-emitted slug from territory_data_v3.py), got {first['id']!r}"
    )


def test_manifest_research_overlay_applied_false_for_iberia_baseline(
    pipeline_output_yaml: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no overlay sidecar is present, MANIFEST.research_overlay_applied is False.

    Mirrors D-04 from the export side: the zip MANIFEST is the canonical
    signal for downstream consumers (Unity / inspector). For Iberia baseline
    (no `research_overlay.json`), this MUST report false so the zero-LLM
    pipeline can be distinguished from an LLM-augmented one.
    """
    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.export import build_unity_zip

    project_id = "00000000-0000-0000-0000-7110000007a1"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    pdir = paths_mod.project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "output").mkdir(parents=True, exist_ok=True)
    (pdir / "exports").mkdir(parents=True, exist_ok=True)
    for src in pipeline_output_yaml.iterdir():
        if src.is_file():
            (pdir / "output" / src.name).write_bytes(src.read_bytes())

    # Sanity: no overlay sidecar.
    assert not (pdir / "research_overlay.json").exists()

    cfg = replace(load_region("iberia_868"))
    zip_path = build_unity_zip(project_id, cfg=cfg, region_key="iberia_868")

    import zipfile as _zipfile

    with _zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))

    assert manifest["research_overlay_applied"] is False


def test_zip_diff_limited_to_zip_bound_fields_when_toggling_strict_tolerant(
    pipeline_output_yaml: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEWS fix #9 (parity-layer downgrade-path lock).

    Re-export the same Iberia project twice — once with the Strict verdict
    (`_ZIP_BOUND_FIELDS = {"name"}`), once with the Tolerant verdict
    (`_ZIP_BOUND_FIELDS = {"name", "kingdom_owner", "historical_notes"}`) —
    seeded with the same `research_overlay.json` containing all 3 fields
    for 3 condados.

    Asserts:
      (a) Every file in the zip EXCEPT `territory_metadata.json` and
          `MANIFEST.json` is byte-identical between Strict and Tolerant
          (geometric outputs untouched by zip-bound verdict toggle).
      (b) Inside `territory_metadata.json`: geometric invariants
          (original_idx, pixel_count, pixel_center, lon, lat, duchy, kingdom)
          match for every condado between Strict and Tolerant; `name` matches
          in both (emitted under both verdicts); under Strict the optional
          fields (`kingdom_owner`, `historical_notes`) are absent / never
          leak into the zip for overlay-covered condados.
      (c) Both MANIFESTs have `research_overlay_applied == True`.
    """
    import hashlib as _hashlib
    import zipfile as _zipfile

    from medieval_forge.services import paths as paths_mod
    from medieval_forge.services.export import build_unity_zip
    from medieval_forge.services.research import overlay as overlay_module

    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    def _stage(project_id: str) -> Path:
        pdir = paths_mod.project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "output").mkdir(parents=True, exist_ok=True)
        (pdir / "exports").mkdir(parents=True, exist_ok=True)
        for src in pipeline_output_yaml.iterdir():
            if src.is_file():
                (pdir / "output" / src.name).write_bytes(src.read_bytes())
        return pdir

    # Pick the first 3 condado ids from the raw pipeline output and seed an
    # overlay covering all 3 fields for each.
    raw_meta = json.loads(
        (pipeline_output_yaml / "territory_metadata.json").read_text(encoding="utf-8")
    )
    target_ids = [c["id"] for c in raw_meta["condados"][:3]]
    overlay_payload = {
        target_ids[0]: {
            "name": "Condado de Oviedo",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Founded 791 AD.",
        },
        target_ids[1]: {
            "name": "Condado de Pravia",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Capital under Silo (774-783).",
        },
        target_ids[2]: {
            "name": "Condado de Gijón",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Coastal stronghold.",
        },
    }

    # ---- Strict run -------------------------------------------------------
    monkeypatch.setattr(
        overlay_module, "_ZIP_BOUND_FIELDS", frozenset({"name"})
    )
    project_id_strict = "00000000-0000-0000-0000-571171071100"
    pdir_strict = _stage(project_id_strict)
    (pdir_strict / "research_overlay.json").write_text(
        json.dumps(overlay_payload), encoding="utf-8"
    )
    cfg = replace(load_region("iberia_868"))
    zip_a = build_unity_zip(project_id_strict, cfg=cfg, region_key="iberia_868")

    # ---- Tolerant run -----------------------------------------------------
    monkeypatch.setattr(
        overlay_module,
        "_ZIP_BOUND_FIELDS",
        frozenset({"name", "kingdom_owner", "historical_notes"}),
    )
    project_id_tol = "00000000-0000-0000-0000-707071071100"
    pdir_tol = _stage(project_id_tol)
    (pdir_tol / "research_overlay.json").write_text(
        json.dumps(overlay_payload), encoding="utf-8"
    )
    zip_b = build_unity_zip(project_id_tol, cfg=cfg, region_key="iberia_868")

    # ---- Assertions -------------------------------------------------------
    with _zipfile.ZipFile(zip_a) as za, _zipfile.ZipFile(zip_b) as zb:
        files_a = sorted(za.namelist())
        files_b = sorted(zb.namelist())
        assert files_a == files_b, (
            f"REVIEWS fix #9: zip file list differs: A={files_a} B={files_b}"
        )

        # (a) Geometric outputs byte-identical under verdict toggle.
        for fname in files_a:
            if fname in ("territory_metadata.json", "MANIFEST.json"):
                continue
            sha_a = _hashlib.sha256(za.read(fname)).hexdigest()
            sha_b = _hashlib.sha256(zb.read(fname)).hexdigest()
            assert sha_a == sha_b, (
                f"REVIEWS fix #9: geometric output {fname} differs between "
                f"Strict and Tolerant — verdict toggle leaked into geometry"
            )

        # (b) territory_metadata.json: invariants + name match; Strict has no
        # kingdom_owner/historical_notes for the overlay-targeted condados.
        meta_a = json.loads(za.read("territory_metadata.json"))
        meta_b = json.loads(zb.read("territory_metadata.json"))
        assert len(meta_a["condados"]) == len(meta_b["condados"]), (
            "REVIEWS fix #9: condado count differs between Strict and Tolerant"
        )
        by_id_a = {c["id"]: c for c in meta_a["condados"]}
        by_id_b = {c["id"]: c for c in meta_b["condados"]}
        for cid in by_id_a:
            ca = by_id_a[cid]
            cb = by_id_b[cid]
            for invariant in (
                "original_idx",
                "pixel_count",
                "pixel_center",
                "lon",
                "lat",
                "duchy",
                "kingdom",
            ):
                if invariant in ca or invariant in cb:
                    assert ca.get(invariant) == cb.get(invariant), (
                        f"REVIEWS fix #9: {invariant} differs for condado {cid} "
                        f"between Strict and Tolerant"
                    )
            # name emitted in both verdicts (overlay sets it under Strict too).
            assert ca["name"] == cb["name"]
            # For the overlay-targeted condados the Strict zip must NOT leak
            # kingdom_owner or historical_notes.
            if cid in overlay_payload:
                if ca.get("kingdom_owner") is not None:
                    pytest.fail(
                        f"REVIEWS fix #9: Strict zip leaked kingdom_owner "
                        f"for condado {cid}: {ca.get('kingdom_owner')!r}"
                    )
                if ca.get("historical_notes") is not None:
                    pytest.fail(
                        f"REVIEWS fix #9: Strict zip leaked historical_notes "
                        f"for condado {cid}: {ca.get('historical_notes')!r}"
                    )

        # (c) Both manifests acknowledge overlay applied.
        man_a = json.loads(za.read("MANIFEST.json"))
        man_b = json.loads(zb.read("MANIFEST.json"))
        assert man_a["research_overlay_applied"] is True
        assert man_b["research_overlay_applied"] is True
