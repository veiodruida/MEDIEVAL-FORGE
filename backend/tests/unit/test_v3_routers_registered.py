"""Smoke test: confirm Plan 03-02 v3 routes are registered on `app`.

Uses `app.routes` introspection (no httpx, no boot). Also asserts the
Phase 02 v3 ingest route is still present (regression guard) and that
the v3 namespace `__init__.py` re-exports all four routers.
"""
from __future__ import annotations

from medieval_forge.main import app


def _route_paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def test_generate_post_route_is_registered():
    assert "/api/v3/projects/{project_id}/generate" in _route_paths()


def test_generate_stream_route_is_registered():
    assert "/api/v3/projects/{project_id}/generate/stream" in _route_paths()


def test_status_route_is_registered():
    assert "/api/v3/projects/{project_id}/status" in _route_paths()


def test_artifacts_route_is_registered():
    assert "/api/v3/projects/{project_id}/artifacts/{file_name}" in _route_paths()


def test_phase02_v3_ingest_route_still_registered():
    """Regression guard: Plan 03-02 must not unregister the Phase 02 route."""
    assert "/api/v3/projects/{project_id}/ingest" in _route_paths()


def test_v3_init_reexports_all_four_routers():
    """Acceptance criterion: __init__.py re-exports the routers under
    canonical names (ingest_router, generate_router, status_router,
    artifacts_router)."""
    from medieval_forge.api import v3

    assert hasattr(v3, "ingest_router")
    assert hasattr(v3, "generate_router")
    assert hasattr(v3, "status_router")
    assert hasattr(v3, "artifacts_router")
    # Each must be a FastAPI APIRouter instance (duck-typed via .routes attr).
    assert all(
        hasattr(getattr(v3, name), "routes")
        for name in (
            "ingest_router",
            "generate_router",
            "status_router",
            "artifacts_router",
        )
    )
