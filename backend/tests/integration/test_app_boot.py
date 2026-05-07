"""Phase 00 SC-6 invariant: FastAPI app still boots and `/` returns 200.

Particularly important after Plan 01-03 deletes the v1 generator stack
(api/generate, services/generator, lib/map_generator). The SPA catch-all
in main.py keeps `/` serving 200 even though the frontend stepper UI is
non-functional (Phase 03 owns the frontend rewrite per D-08).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from medieval_forge.main import app


@pytest.mark.integration
def test_root_returns_200() -> None:
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200, (
            "Phase 00 SC-6 invariant: GET / must return 200 after generator delete; "
            f"got {r.status_code}"
        )
