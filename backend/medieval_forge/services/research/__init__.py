"""services/research/ — opt-in metadata layer (D-03/D-04).

Pure functions ONLY in this package; orchestration lives in api/v3/research.py
(Plan 07).
"""
from .cache import (
    PROMPT_DIGEST,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    cache_get,
    cache_get_with_generated_at,
    cache_key,
    cache_put,
)
from .matcher import (
    build_pipeline_condado_list,
    llm_output_to_overlay,
)
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
    "PROMPT_DIGEST",
    "PROMPT_VERSION",
    "ResearchOverlay",
    "SCHEMA_VERSION",
    "_ALL_OVERLAY_FIELDS",
    "_ZIP_BOUND_FIELDS",
    "build_pipeline_condado_list",
    "cache_get",
    "cache_get_with_generated_at",
    "cache_key",
    "cache_put",
    "llm_output_to_overlay",
    "load_overlay_if_exists",
    "merge_overlay",
]
