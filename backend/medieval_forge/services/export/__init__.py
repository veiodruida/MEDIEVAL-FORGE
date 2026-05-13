"""services/export/ — Phase 06 subpackage.

Hosts the zip builder (zip.py), pydantic schemas (schemas.py), and the
export validation gate (validator.py — landed in Task 3 of Plan 06-01).

Re-exports preserve every existing caller's `from medieval_forge.services.export
import ...` import path.
"""
from __future__ import annotations

from .zip import (
    build_unity_zip,
    UNITY_ZIP_SPEC,
    PLACEHOLDER_FILES,
)
from .schemas import (
    MANIFEST_SCHEMA_VERSION,
    LookupBaronyColorsSchema,
    LookupCondadoColorsSchema,
    TerrainTypesSchema,
    TerritoryMetadataSchema,
    MountainRiverDataSchema,
    ManifestSchema,
    ManifestFileEntry,
    ValidationReport,
    ValidationErrorEntry,
)

__all__ = [
    # zip (Task 1)
    "build_unity_zip",
    "UNITY_ZIP_SPEC",
    "PLACEHOLDER_FILES",
    # schemas (Task 2)
    "MANIFEST_SCHEMA_VERSION",
    "LookupBaronyColorsSchema",
    "LookupCondadoColorsSchema",
    "TerrainTypesSchema",
    "TerritoryMetadataSchema",
    "MountainRiverDataSchema",
    "ManifestSchema",
    "ManifestFileEntry",
    "ValidationReport",
    "ValidationErrorEntry",
    # validator (appended by Task 3)
]
