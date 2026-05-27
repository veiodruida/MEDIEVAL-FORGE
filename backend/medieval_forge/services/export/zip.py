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
# Plan 07-08 Task 1 (Pattern 11): grep-locked direct symbol imports + module
# alias. The module alias `_overlay_module` lets tests monkeypatch
# `_ZIP_BOUND_FIELDS` at runtime (REVIEWS fix #9 Test 7 — Strict zip-vs-sidecar
# asymmetry). The single-line direct import satisfies the grep acceptance
# criterion `from ..research.overlay import merge_overlay`.
from ..research import overlay as _overlay_module
from ..research.overlay import merge_overlay, load_overlay_if_exists, _ZIP_BOUND_FIELDS  # noqa: F401
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
    *,
    branch_name: str | None = None,
    snapshot_id: str | None = None,
    snapshot_timestamp: "datetime | None" = None,
) -> Path:
    """Validate -> assemble -> write. Raises ValidationFailedError on gate failure.

    Args:
        project_id: UUID.
        cfg: RegionConfig (validator reads cfg.ocean_far, cfg.blob_merge_px,
             cfg.map_w, cfg.map_h).
        region_key: persisted on MANIFEST.region_key for Unity consumers.
        branch_name: D-16 — active branch name; None for non-branch exports.
        snapshot_id: D-16 — latest snapshot UUID; None for non-branch exports.
        snapshot_timestamp: D-16 — snapshot created_at (UTC); None for non-branch exports.

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
    #
    # Pitfall 2 (Plan 07-08): validator runs on RAW pipeline output BEFORE merge.
    # The overlay carries optional fields (kingdom_owner, historical_notes) that
    # the schema accepts but should NEVER be conflated with geometric regressions.
    # Validate-before-merge keeps the gate honest.
    report, sha256_by_file = validate_export(generated, cfg)
    if not report.passed:
        raise ValidationFailedError(report)

    # Plan 07-08 Task 1 (Pattern 11 + D-03/D-04): load the per-project research
    # overlay sidecar if present. `load_overlay_if_exists` returns None when the
    # file is absent (D-12 zero-LLM parity guard); raises ValidationError /
    # JSONDecodeError on schema-invalid or truncated content (REVIEWS fix #10).
    # The exception bubbles up so the export aborts loudly rather than silently
    # corrupting metadata — geometric pipeline output is NEVER touched.
    overlay_path = project_dir(project_id) / "research_overlay.json"
    overlay = load_overlay_if_exists(overlay_path)
    research_overlay_applied = overlay is not None

    # MANIFEST timestamps. v3 pipeline does not currently emit a per-run timestamp,
    # so we use validator-call time as a stand-in for generated_at_utc.
    now_utc = datetime.now(timezone.utc)
    generated_at_utc = now_utc.isoformat()
    exported_at_utc = now_utc.strftime("%Y%m%d-%H%M%S")

    # D-16: append branch+snapshot suffix when branch context is provided
    if branch_name is not None and snapshot_id is not None:
        # Derive a compact seq label from the snapshot UUID (last 8 hex chars)
        seq_label = snapshot_id.replace("-", "")[-8:]
        zip_name = f"medieval-forge-{project_id}-{exported_at_utc}-{branch_name}-seq{seq_label}.zip"
    else:
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

            # Plan 07-08 Task 1 (Pattern 11): merge overlay into territory_metadata.json
            # ONLY at the zip-write boundary. The raw on-disk file is read above
            # (via `data = source_path.read_bytes()`) but the merged result is
            # written only into the zip via `zf.writestr(fname, data)` below —
            # the pipeline output directory is NEVER mutated (Pitfall 1 + WARNING 5).
            #
            # `_overlay_module._ZIP_BOUND_FIELDS` is read DYNAMICALLY from the module
            # so tests can monkeypatch the Strict/Tolerant verdict at runtime
            # (REVIEWS fix #9 — Strict zip-vs-sidecar asymmetry e2e test).
            if (
                fname == "territory_metadata.json"
                and overlay is not None
                and source == "generated"
            ):
                raw_metadata = json.loads(data.decode("utf-8"))
                # Grep contract (acceptance criterion): `merge_overlay(raw_metadata`
                # must appear as a single substring in this file.
                merged_metadata = merge_overlay(raw_metadata, overlay, allowed_fields=_overlay_module._ZIP_BOUND_FIELDS)  # noqa: E501
                data = json.dumps(merged_metadata).encode("utf-8")
                # Rehash because the bytes that land in the zip changed.
                sha = hashlib.sha256(data).hexdigest()
                source = "merged_overlay"

            zf.writestr(fname, data)
            files_manifest.append({
                "name": fname,
                "source": source,
                "size_bytes": len(data),
                "sha256": sha,
            })

        # D-16 (Phase 08 Plan 10): snapshot_timestamp serialized as ISO string or None.
        snapshot_ts_str: str | None = None
        if snapshot_timestamp is not None:
            snapshot_ts_str = snapshot_timestamp.isoformat()

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
                # D-04 + CONTEXT canonical_refs: MANIFEST gains research_overlay_applied.
                "research_overlay_applied": research_overlay_applied,
                # D-16 (Phase 08 Plan 10): branch metadata. None for non-branch exports
                # (Pitfall 4 backward-compat: Optional fields preserve Phase 06 parity).
                "branch_name": branch_name,
                "snapshot_id": snapshot_id,
                "snapshot_timestamp": snapshot_ts_str,
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
