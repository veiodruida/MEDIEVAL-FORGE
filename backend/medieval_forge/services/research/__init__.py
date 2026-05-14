"""services/research/ — opt-in metadata layer (D-03/D-04).

Pure functions ONLY in this package; orchestration lives in api/v3/research.py
(Plan 07).
"""
from .overlay import (
    CondadoOverlayEntry,
    ResearchOverlay,
    _ALL_OVERLAY_FIELDS,
    _ZIP_BOUND_FIELDS,
    load_overlay_if_exists,
    merge_overlay,
)

__all__ = [
    "CondadoOverlayEntry",
    "ResearchOverlay",
    "_ALL_OVERLAY_FIELDS",
    "_ZIP_BOUND_FIELDS",
    "load_overlay_if_exists",
    "merge_overlay",
]
