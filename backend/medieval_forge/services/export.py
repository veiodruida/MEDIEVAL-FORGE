"""EXPORT-01 + EXPORT-02: Unity-ready ZIP assembly.

The 12-file spec (REQUIREMENTS.md EXPORT-02) is now fully emitted by the v3
pipeline after Plan 05-11 closed the terrain pair (terrain_lookup.png +
terrain_types.json). Only `mountain_river_data.json` is conditional — when
the region has no mountain/river inputs the file may be absent and the ZIP
falls back to a `{}` placeholder.

The ZIP includes a MANIFEST.json so consumers (and Phase 6) can distinguish
real content from placeholders.
"""
from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .paths import ensure_project_dirs
from .pipeline.contracts import EXPORT_FILE_CONTRACT

logger = logging.getLogger(__name__)

# EXPORT-02: explicit 12-file Unity spec from REQUIREMENTS.md.
# CR-01 fix (Plan 05 review): derive from `contracts.EXPORT_FILE_CONTRACT` so the
# ZIP cannot silently drift from the canonical 12-file contract declared in
# CLAUDE.md §"v3 Pipeline Contract". Before this fix `UNITY_ZIP_SPEC` listed 11
# entries — `rivers_overlay.png` was missing and the downloaded ZIP shipped 11/12
# contract files. Tests now assert set-equality with EXPORT_FILE_CONTRACT.
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


def build_unity_zip(project_id: str) -> Path:
    """Assemble the project's Unity ZIP. Returns the absolute path to the new file.

    Raises:
        FileNotFoundError: if generated/ has none of the expected files.
    """
    dirs = ensure_project_dirs(project_id)
    generated = dirs["generated"]
    exports = dirs["exports"]

    # Guard: must have at least one generator output before exporting.
    any_generated = any((generated / fname).exists() for fname in UNITY_ZIP_SPEC)
    if not any_generated:
        raise FileNotFoundError(
            f"no generated outputs in {generated} — generate maps before exporting"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    zip_name = f"medieval-forge-{project_id}-{timestamp}.zip"
    zip_path = exports / zip_name
    tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")

    manifest: list[dict] = []

    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in UNITY_ZIP_SPEC:
            source_path = generated / fname
            if source_path.exists():
                data = source_path.read_bytes()
                source = "generated"
            else:
                data = _placeholder_payload(fname)
                source = "placeholder"
            zf.writestr(fname, data)
            manifest.append({
                "name": fname,
                "source": source,
                "size_bytes": len(data),
            })
        manifest_payload = json.dumps(
            {
                "project_id": project_id,
                "exported_at_utc": timestamp,
                "spec_version": 1,
                "phase": 1,
                "note": (
                    "Phase 1 export — 'placeholder' files are stubs that "
                    "Phase 6 (EXPORT-03/04) will replace with real content."
                ),
                "files": manifest,
            },
            indent=2,
        )
        zf.writestr("MANIFEST.json", manifest_payload)

    tmp_path.replace(zip_path)
    logger.info("export built: %s (%d files)", zip_path, len(UNITY_ZIP_SPEC))
    return zip_path
