"""EXPORT-01 + Phase 06 export gate: validate -> zip -> MANIFEST.

Plan 06-03 wired validate_export into build_unity_zip. On gate failure,
build_unity_zip raises ValidationFailedError(report) BEFORE writing any
zip artifact (no .tmp leak). The endpoint catches and maps to HTTP 422.

EXPORT-02: explicit 12-file Unity spec; sourced from
`pipeline.contracts.EXPORT_FILE_CONTRACT` to prevent silent drift.

Signature change in Plan 06-03:
  v1: build_unity_zip(project_id) -> Path
  v3: build_unity_zip(project_id, cfg, region_key) -> Path

Verified callers (2026-05-13):
  - backend/medieval_forge/api/export.py:42  DELETED in Plan 06-03 Task 2
  - backend/tests/test_export.py:91          DELETED in Plan 06-03 Task 2
  - backend/medieval_forge/api/v3/export.py  CREATED in Plan 06-03 Task 2
"""
from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..paths import ensure_project_dirs, project_dir
from ..pipeline.contracts import EXPORT_FILE_CONTRACT, RegionConfig
from .schemas import MANIFEST_SCHEMA_VERSION
from .validator import ValidationFailedError, validate_export

logger = logging.getLogger(__name__)

# EXPORT-02: explicit 12-file Unity spec from REQUIREMENTS.md.
# CR-01 fix (Plan 05 review): derive from `contracts.EXPORT_FILE_CONTRACT` so the
# ZIP cannot silently drift from the canonical 12-file contract declared in
# CLAUDE.md §"v3 Pipeline Contract".
UNITY_ZIP_SPEC: tuple[str, ...] = EXPORT_FILE_CONTRACT
assert len(UNITY_ZIP_SPEC) == 12, "Unity contract: 12 files"

# Plan 05-11 closed the terrain pair — terrain_lookup.png + terrain_types.json
# are now real outputs emitted by the pipeline. `mountain_river_data.json`
# stays in the placeholder set: it is sourced from the region's input dir and
# may legitimately be absent for toy datasets.
PLACEHOLDER_FILES: frozenset[str] = frozenset({
    "mountain_river_data.json",
})

# Minimal valid 1x1 transparent PNG (signature + IHDR + IDAT + IEND).
_PLACEHOLDER_PNG: bytes = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
_PLACEHOLDER_JSON: bytes = b"{}\n"


def _placeholder_payload(filename: str) -> bytes:
    if filename.endswith(".png"):
        return _PLACEHOLDER_PNG
    if filename.endswith(".json"):
        return _PLACEHOLDER_JSON
    return b""


def resolve_generated_dir(project_id: str) -> Path:
    """v3 writes to project_dir/output; v1 wrote to project_dir/generated. Prefer v3.

    Phase 06 transition compat: the new endpoint always reads from
    project_dir/output (matches api/v3/generate.py:140). The /generated
    fallback handles any in-flight v1 project still on disk; can be removed
    once the v1 pipeline path is fully retired.

    IMPORTANT: the /output fallback requires BOTH is_dir() AND any(iterdir()) --
    an empty directory (e.g., generate started then crashed) is treated as absent
    and falls back to /generated. This prevents dry-run validating an empty dir
    while the real export would use /generated.
    """
    root = project_dir(project_id)
    output = root / "output"
    if output.is_dir() and any(output.iterdir()):
        return output
    return ensure_project_dirs(project_id)["generated"]


# Internal alias for backward compat within this module
_resolve_generated_dir = resolve_generated_dir


def build_unity_zip(
    project_id: str,
    cfg: RegionConfig,
    region_key: str,
) -> Path:
    """Validate -> assemble -> write. Raises ValidationFailedError on gate failure.

    Args:
        project_id: UUID.
        cfg: RegionConfig (validator reads cfg.ocean_far, cfg.blob_merge_px,
             cfg.map_w, cfg.map_h).
        region_key: persisted on MANIFEST.region_key for Unity consumers.

    Raises:
        FileNotFoundError: pipeline output dir empty (preserved v1 contract;
            endpoint maps to 409).
        ValidationFailedError: export gate failed (D-08 codes in report.errors;
            endpoint maps to 422 with D-08 structured envelope).

    Returns:
        Path to the new .zip file (atomic via .tmp + replace).
    """
    dirs = ensure_project_dirs(project_id)
    generated = _resolve_generated_dir(project_id)
    exports = dirs["exports"]

    # Guard: must have at least one generator output before validating.
    any_generated = any((generated / fname).exists() for fname in UNITY_ZIP_SPEC)
    if not any_generated:
        raise FileNotFoundError(
            f"no generated outputs in {generated} -- generate maps before exporting"
        )

    # Phase 06 GATE: validate before assembling. Raises ValidationFailedError on failure.
    # The validator reads every file once and returns the (report, sha256_by_file)
    # tuple per RESEARCH §Per-Discretion #2 (validator-time hashing).
    report, sha256_by_file = validate_export(generated, cfg)
    if not report.passed:
        raise ValidationFailedError(report)

    # MANIFEST timestamps. v3 pipeline does not currently emit a per-run timestamp,
    # so we use validator-call time as a stand-in for generated_at_utc.
    now_utc = datetime.now(timezone.utc)
    generated_at_utc = now_utc.isoformat()
    exported_at_utc = now_utc.strftime("%Y%m%d-%H%M%S")

    zip_name = f"medieval-forge-{project_id}-{exported_at_utc}.zip"
    zip_path = exports / zip_name
    tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")

    files_manifest: list[dict] = []

    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in UNITY_ZIP_SPEC:
            source_path = generated / fname
            if source_path.exists():
                data = source_path.read_bytes()
                source = "generated"
                sha = sha256_by_file.get(fname, "")
            else:
                data = _placeholder_payload(fname)
                source = "placeholder"
                # Placeholder bytes: hash on the fly (validator didn't see this file).
                sha = hashlib.sha256(data).hexdigest()
            zf.writestr(fname, data)
            files_manifest.append({
                "name": fname,
                "source": source,
                "size_bytes": len(data),
                "sha256": sha,
            })

        manifest_payload = json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "region_key": region_key,
                "project_id": project_id,
                "generated_at_utc": generated_at_utc,
                "exported_at_utc": exported_at_utc,
                "spec_version": 1,
                "phase": 6,
                "validation_report": report.model_dump(),
                "files": files_manifest,
            },
            indent=2,
        )
        zf.writestr("MANIFEST.json", manifest_payload)

    tmp_path.replace(zip_path)
    logger.info(
        "export built: %s (12 files + MANIFEST; gate passed; %d sha256 hashes)",
        zip_path, len(sha256_by_file),
    )
    return zip_path
