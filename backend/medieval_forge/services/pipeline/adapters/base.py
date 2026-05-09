"""Shared helpers for adapters: inputs_dir creation + atomic write re-export."""
from __future__ import annotations

from pathlib import Path

from medieval_forge.services.paths import (
    _write_geojson_atomic,
    is_valid_uuid,
    project_dir,
)


def project_inputs_dir(project_id: str) -> Path:
    """Return projects/<uuid>/inputs/, creating it if needed (D-07).

    Raises ValueError if project_id is not a valid UUID (T-PATH).
    """
    if not is_valid_uuid(project_id):
        raise ValueError(f"invalid project_id: {project_id!r}")
    inputs = project_dir(project_id) / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    return inputs


__all__ = ["project_inputs_dir", "_write_geojson_atomic"]
