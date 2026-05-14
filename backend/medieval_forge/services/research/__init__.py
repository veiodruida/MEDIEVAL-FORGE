"""services/research/ — opt-in metadata layer (D-03/D-04).

Pure functions ONLY in this package, EXCEPT for `runner.py` which orchestrates
the SSE producer/consumer pair shared with `api/v3/research.py` (Plan 07-07b).
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
from .runner import (
    SingleFlightError,
    _RUN_QUEUES,
    _RUN_STOP_EVENTS,
    _RUN_TASKS,
    get_stream,
    start_research,
    stop_research,
)

__all__ = [
    "CondadoOverlayEntry",
    "PROMPT_DIGEST",
    "PROMPT_VERSION",
    "ResearchOverlay",
    "SCHEMA_VERSION",
    "SingleFlightError",
    "_ALL_OVERLAY_FIELDS",
    "_RUN_QUEUES",
    "_RUN_STOP_EVENTS",
    "_RUN_TASKS",
    "_ZIP_BOUND_FIELDS",
    "build_pipeline_condado_list",
    "cache_get",
    "cache_get_with_generated_at",
    "cache_key",
    "cache_put",
    "get_stream",
    "llm_output_to_overlay",
    "load_overlay_if_exists",
    "merge_overlay",
    "start_research",
    "stop_research",
]
