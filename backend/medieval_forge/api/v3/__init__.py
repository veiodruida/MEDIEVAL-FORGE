"""v3 API namespace (Phase 02+). Coexists with v1 routers under /api/.

Routers exported:
  ingest_router    — Phase 02: GET /v3/projects/{id}/ingest (SSE)
  generate_router  — Phase 03 Plan 02: POST /v3/projects/{id}/generate +
                     GET /v3/projects/{id}/generate/stream (SSE)
  status_router    — Phase 03 Plan 02: GET /v3/projects/{id}/status
  artifacts_router — Phase 03 Plan 02: GET /v3/projects/{id}/artifacts/{file_name}
"""
from .ingest import router as ingest_router
from .generate import router as generate_router
from .status import router as status_router
from .artifacts import router as artifacts_router

__all__ = [
    "ingest_router",
    "generate_router",
    "status_router",
    "artifacts_router",
]
