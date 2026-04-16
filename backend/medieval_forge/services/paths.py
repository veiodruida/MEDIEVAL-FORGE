"""Filesystem path helpers + T-PATH boundary enforcement.

All filesystem access for project data goes through these helpers.
Per RESEARCH.md Security Domain: validate UUID format AND verify the
resolved path is within DATA_DIR/projects/.
"""
from __future__ import annotations

import re
import uuid as _uuid_mod
from pathlib import Path

from medieval_forge.database import DATA_DIR

PROJECTS_ROOT: Path = DATA_DIR / "projects"

# Strict UUID v4 lowercase pattern (matches uuid.UUID(version=4) string form).
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def is_valid_uuid(value: str) -> bool:
    """Return True iff `value` is a syntactically valid UUID string."""
    if not isinstance(value, str) or not _UUID_RE.match(value):
        return False
    try:
        _uuid_mod.UUID(value)
    except (ValueError, TypeError):
        return False
    return True


def project_dir(project_id: str) -> Path:
    """Return the project's root directory after T-PATH validation.

    Raises:
        ValueError: if project_id is not a valid UUID OR if the resolved
                    path escapes PROJECTS_ROOT.
    """
    if not is_valid_uuid(project_id):
        raise ValueError(f"invalid project_id: {project_id!r}")

    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    candidate = (PROJECTS_ROOT / project_id).resolve()
    root = PROJECTS_ROOT.resolve()
    # Python 3.9+: is_relative_to handles edge cases like trailing separators.
    if not candidate.is_relative_to(root):
        raise ValueError(f"project_id resolves outside PROJECTS_ROOT: {project_id!r}")
    return candidate


def ensure_project_dirs(project_id: str) -> dict[str, Path]:
    """Create raw/, generated/, exports/ subfolders for the project."""
    root = project_dir(project_id)
    subdirs = {
        "root": root,
        "raw": root / "raw",
        "generated": root / "generated",
        "exports": root / "exports",
    }
    for p in subdirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return subdirs
