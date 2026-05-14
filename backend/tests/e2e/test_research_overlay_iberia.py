"""Plan 07-08 Task 4 — Wave 0 e2e gate for the overlay merge layer.

Covers SC #2 + D-12 zero-overlay byte-equality + WARNING 5 sha256 no-disk-write
regression + REVIEWS fix #9 Strict zip-vs-sidecar asymmetry.

7 cases:
  1. test_iberia_overlay_yields_historical_names_in_zip — overlay merged into
     territory_metadata.json inside the built zip.
  2. test_artifact_endpoint_serves_merged_metadata — same merge via the HTTP
     artifact endpoint (Pattern 12).
  3. test_no_overlay_yields_byte_identical_to_phase_06_baseline — D-12 parity.
  4. test_manifest_research_overlay_applied_true_when_overlay_present — D-04.
  5. test_manifest_research_overlay_applied_false_when_overlay_absent — D-12.
  6. test_artifact_endpoint_does_not_write_to_disk_during_merge — WARNING 5.
  7. test_strict_zip_bound_emits_only_name_while_sidecar_retains_all_three_fields
     — REVIEWS fix #9.

Speed note: the test runs the France 1066 toy pipeline (~5s) for fixture
setup, NOT the full Iberia 868 pipeline (~30s). The plan name carries
"iberia" because the SC #2 wording is Iberia-centric, but the overlay merge
contract is region-agnostic. Iberia-specific parity coverage lives in
tests/parity/test_iberia_868_yaml.py which this plan does NOT modify.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from medieval_forge.main import app
from medieval_forge.services import paths as paths_mod
from medieval_forge.services.export import build_unity_zip
from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.e2e


@dataclass
class _ProjectFixture:
    """Lightweight bundle (Path can't carry custom attrs on Windows)."""

    pdir: Path
    project_id: str
    target_ids: list[str]
    target_id: str  # convenience first id

    def __truediv__(self, other: str) -> Path:
        # Allow `fixture / "output"` to work like Path division.
        return self.pdir / other


# ---------------------------------------------------------------------------
# Module-scoped pipeline output — run France 1066 once, share across tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def france_pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the toy pipeline once per module; return its output directory."""
    out = tmp_path_factory.mktemp("research_overlay_iberia_e2e_pipeline")
    clear_region_cache()
    cfg = replace(load_region("france_1066"), output_dir=str(out))
    run_pipeline(cfg)
    return out


def _stage_project_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    france_pipeline_output: Path,
    project_id: str,
) -> Path:
    """Common helper: monkeypatch PROJECTS_ROOT, copy pipeline output into
    `output/`, create `exports/`. Returns the project_dir Path."""
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    pdir = paths_mod.project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    output_dir = pdir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (pdir / "exports").mkdir(parents=True, exist_ok=True)
    for src in france_pipeline_output.iterdir():
        if src.is_file():
            (output_dir / src.name).write_bytes(src.read_bytes())
    return pdir


@pytest.fixture
def iberia_project_with_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    france_pipeline_output: Path,
) -> _ProjectFixture:
    """Stage a project_dir with output/ + research_overlay.json sidecar.

    The fixture seeds an overlay covering the first 3 condados emitted by the
    pipeline. Returns a `_ProjectFixture` dataclass with `pdir`, `project_id`,
    `target_ids`, and `target_id` (= first id) attached.
    """
    project_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    pdir = _stage_project_dir(tmp_path, monkeypatch, france_pipeline_output, project_id)

    raw_meta = json.loads(
        (pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8")
    )
    assert len(raw_meta["condados"]) >= 3, "fixture sanity: at least 3 condados"
    target_ids = [c["id"] for c in raw_meta["condados"][:3]]

    overlay = {
        target_ids[0]: {
            "name": "Condado de Oviedo",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Founded 791 AD.",
        },
        target_ids[1]: {
            "name": "Condado de León",
            "kingdom_owner": "Reino de León",
            "historical_notes": "Founded 856 AD.",
        },
        target_ids[2]: {
            "name": "Condado de Burgos",
            "kingdom_owner": "Condado de Castilla",
            "historical_notes": "Founded 884 AD.",
        },
    }
    (pdir / "research_overlay.json").write_text(json.dumps(overlay), encoding="utf-8")
    return _ProjectFixture(
        pdir=pdir,
        project_id=project_id,
        target_ids=target_ids,
        target_id=target_ids[0],
    )


@pytest.fixture
def iberia_project_without_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    france_pipeline_output: Path,
) -> _ProjectFixture:
    """Stage a project_dir with output/ but NO research_overlay.json sidecar."""
    project_id = "11111111-2222-3333-4444-555555555555"
    pdir = _stage_project_dir(tmp_path, monkeypatch, france_pipeline_output, project_id)
    raw_meta = json.loads(
        (pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8")
    )
    target_ids = [c["id"] for c in raw_meta["condados"][:3]]
    return _ProjectFixture(
        pdir=pdir,
        project_id=project_id,
        target_ids=target_ids,
        target_id=target_ids[0],
    )


@pytest.fixture
def iberia_project_with_full_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    france_pipeline_output: Path,
) -> _ProjectFixture:
    """Same shape as iberia_project_with_overlay but used by Test 7 (Strict
    verdict). The test seeds its OWN overlay payload after the fixture runs,
    so we leave the sidecar absent here.
    """
    project_id = "22222222-3333-4444-5555-666666666666"
    pdir = _stage_project_dir(tmp_path, monkeypatch, france_pipeline_output, project_id)
    raw_meta = json.loads(
        (pdir / "output" / "territory_metadata.json").read_text(encoding="utf-8")
    )
    target_ids = [c["id"] for c in raw_meta["condados"][:3]]
    return _ProjectFixture(
        pdir=pdir,
        project_id=project_id,
        target_ids=target_ids,
        target_id=target_ids[0],
    )


@pytest_asyncio.fixture
async def http_client(monkeypatch, tmp_path):
    """ASGI client. Tests that need PROJECTS_ROOT staged use the project fixture
    which monkeypatches paths_mod itself; this client just opens the ASGI loop."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_zip_payload(zip_path: Path) -> tuple[dict, dict]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        meta = json.loads(zf.read("territory_metadata.json").decode("utf-8"))
        manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
    return meta, manifest


def _find_condado(meta: dict, cid: str) -> dict:
    return next(c for c in meta["condados"] if c["id"] == cid)


# ---------------------------------------------------------------------------
# Test 1 — Iberia overlay produces historical names in the zip
# ---------------------------------------------------------------------------


def test_iberia_overlay_yields_historical_names_in_zip(
    iberia_project_with_overlay: _ProjectFixture,
) -> None:
    pdir = iberia_project_with_overlay
    cfg = load_region("france_1066")
    zip_path = build_unity_zip(pdir.project_id, cfg=cfg, region_key="france_1066")

    meta_in_zip, _manifest = _read_zip_payload(zip_path)
    oviedo = _find_condado(meta_in_zip, pdir.target_ids[0])
    assert oviedo["name"] == "Condado de Oviedo"
    leon = _find_condado(meta_in_zip, pdir.target_ids[1])
    assert leon["name"] == "Condado de León"
    burgos = _find_condado(meta_in_zip, pdir.target_ids[2])
    assert burgos["name"] == "Condado de Burgos"


# ---------------------------------------------------------------------------
# Test 2 — artifact endpoint serves merged metadata
# ---------------------------------------------------------------------------


async def test_artifact_endpoint_serves_merged_metadata(
    iberia_project_with_overlay: _ProjectFixture,
    http_client: AsyncClient,
) -> None:
    pdir = iberia_project_with_overlay
    r = await http_client.get(
        f"/api/v3/projects/{pdir.project_id}/artifacts/territory_metadata.json"
    )
    assert r.status_code == 200
    body = r.json()
    oviedo = _find_condado(body, pdir.target_ids[0])
    assert oviedo["name"] == "Condado de Oviedo"
    assert oviedo["kingdom_owner"] == "Reino de Asturias"
    assert oviedo["historical_notes"] == "Founded 791 AD."


# ---------------------------------------------------------------------------
# Test 3 — D-12: no overlay yields byte-identical territory_metadata in zip
# ---------------------------------------------------------------------------


def test_no_overlay_yields_byte_identical_to_phase_06_baseline(
    iberia_project_without_overlay: _ProjectFixture,
) -> None:
    """D-12: zero-LLM path. The territory_metadata.json bytes inside the zip
    equal the raw on-disk pipeline output (no merge applied).
    """
    pdir = iberia_project_without_overlay
    cfg = load_region("france_1066")
    zip_path = build_unity_zip(pdir.project_id, cfg=cfg, region_key="france_1066")

    raw_on_disk = (pdir / "output" / "territory_metadata.json").read_bytes()
    with zipfile.ZipFile(zip_path, "r") as zf:
        meta_in_zip = zf.read("territory_metadata.json")
    assert meta_in_zip == raw_on_disk, (
        "D-12 broken: zero-overlay zip does not match raw pipeline output byte-for-byte"
    )


# ---------------------------------------------------------------------------
# Test 4 — MANIFEST.research_overlay_applied is True when overlay present
# ---------------------------------------------------------------------------


def test_manifest_research_overlay_applied_true_when_overlay_present(
    iberia_project_with_overlay: _ProjectFixture,
) -> None:
    pdir = iberia_project_with_overlay
    cfg = load_region("france_1066")
    zip_path = build_unity_zip(pdir.project_id, cfg=cfg, region_key="france_1066")
    _meta, manifest = _read_zip_payload(zip_path)
    assert manifest["research_overlay_applied"] is True


# ---------------------------------------------------------------------------
# Test 5 — MANIFEST.research_overlay_applied is False when overlay absent
# ---------------------------------------------------------------------------


def test_manifest_research_overlay_applied_false_when_overlay_absent(
    iberia_project_without_overlay: _ProjectFixture,
) -> None:
    pdir = iberia_project_without_overlay
    cfg = load_region("france_1066")
    zip_path = build_unity_zip(pdir.project_id, cfg=cfg, region_key="france_1066")
    _meta, manifest = _read_zip_payload(zip_path)
    assert manifest["research_overlay_applied"] is False


# ---------------------------------------------------------------------------
# Test 6 (WARNING 5) — artifact endpoint NEVER writes to disk during merge
# ---------------------------------------------------------------------------


async def test_artifact_endpoint_does_not_write_to_disk_during_merge(
    iberia_project_with_overlay: _ProjectFixture,
    http_client: AsyncClient,
) -> None:
    """WARNING 5: capture sha256 of output/territory_metadata.json BEFORE the
    GET and AFTER the GET. Equal → endpoint is read-only (Pitfall 1 enforced).
    """
    pdir = iberia_project_with_overlay
    raw_path = pdir / "output" / "territory_metadata.json"
    sha_before = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    resp = await http_client.get(
        f"/api/v3/projects/{pdir.project_id}/artifacts/territory_metadata.json"
    )
    assert resp.status_code == 200
    _ = resp.json()  # consume the body

    sha_after = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert sha_before == sha_after, (
        "WARNING 5: artifact endpoint mutated pipeline output on disk"
    )


# ---------------------------------------------------------------------------
# Test 7 (REVIEWS fix #9) — Strict zip-vs-sidecar asymmetry
# ---------------------------------------------------------------------------


def test_strict_zip_bound_emits_only_name_while_sidecar_retains_all_three_fields(
    iberia_project_with_full_overlay: _ProjectFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict verdict simulation: build_unity_zip reads `_ZIP_BOUND_FIELDS`
    dynamically from the overlay module (via module-alias import), so this
    monkeypatch trims the zip to {"name"} only. The sidecar on disk must STILL
    carry all three fields — the downgrade path is asymmetric.
    """
    from medieval_forge.services.research import overlay as overlay_module

    pdir = iberia_project_with_full_overlay
    # Seed sidecar with ALL THREE fields.
    overlay_data = {
        pdir.target_id: {
            "name": "Condado de Oviedo",
            "kingdom_owner": "Reino de Asturias",
            "historical_notes": "Founded 791 AD.",
        }
    }
    sidecar_path = pdir / "research_overlay.json"
    sidecar_path.write_text(json.dumps(overlay_data), encoding="utf-8")

    # Force Strict verdict.
    monkeypatch.setattr(overlay_module, "_ZIP_BOUND_FIELDS", frozenset({"name"}))

    cfg = load_region("france_1066")
    zip_path = build_unity_zip(pdir.project_id, cfg=cfg, region_key="france_1066")

    meta_in_zip, _manifest = _read_zip_payload(zip_path)
    oviedo_zip = _find_condado(meta_in_zip, pdir.target_id)
    assert oviedo_zip["name"] == "Condado de Oviedo"
    assert oviedo_zip.get("kingdom_owner") in (None, ""), (
        f"REVIEWS fix #9: Strict leaked kingdom_owner into zip: {oviedo_zip}"
    )
    assert oviedo_zip.get("historical_notes") in (None, ""), (
        f"REVIEWS fix #9: Strict leaked historical_notes into zip: {oviedo_zip}"
    )

    # Sidecar on disk STILL has all three (Strict drops from zip, not from sidecar).
    sidecar_reload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_reload[pdir.target_id]["name"] == "Condado de Oviedo"
    assert sidecar_reload[pdir.target_id]["kingdom_owner"] == "Reino de Asturias"
    assert sidecar_reload[pdir.target_id]["historical_notes"] == "Founded 791 AD."
