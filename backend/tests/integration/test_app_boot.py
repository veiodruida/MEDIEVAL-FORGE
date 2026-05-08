"""Phase 00 SC-6 invariant: FastAPI app still boots after the v1 generator
stack delete (Plan 01-03 commit a9c2032).

The SPA catch-all in ``main.py`` returns either:
  * 200 when the frontend has been built (``static/index.html`` exists), or
  * 503 with a "Frontend not built yet" JSON body when not built.

Both prove FastAPI is up; the Phase 00 SC-6 contract is "the app BOOTS",
not "the SPA shell is necessarily compiled in CI". A cleared/missing
``static/`` directory is the expected state on a fresh checkout (the
frontend bundle is built by ``npm run build`` and emitted into
``backend/medieval_forge/static/`` as a separate step).

This test asserts both outcomes are acceptable; it fails only if the app
fails to import or returns 500 (unhandled server error).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from medieval_forge.main import app


@pytest.mark.integration
def test_app_boots_and_root_returns_known_status() -> None:
    """FastAPI boots and `/` returns either 200 (frontend built) or 503
    (frontend not built). Anything else (404/500/connection error) means
    the app failed to boot or the SPA catch-all regressed."""
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code in (200, 503), (
            "Phase 00 SC-6 invariant: GET / must return 200 (built) or 503 "
            f"(not built) after generator delete; got {r.status_code} "
            f"with body: {r.text[:200]}"
        )
        if r.status_code == 503:
            # Sanity-check the 503 path is the SPA-not-built one, NOT a
            # generic server failure.
            body = r.json()
            assert "Frontend not built" in body.get("detail", ""), (
                f"503 must be the SPA-not-built placeholder; got: {body}"
            )
