"""Phase 08 Plan 06a — integration tests for POST /api/v3/projects/{id}/editor/validate.

Covers REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, TOPO-01, TOPO-02, T-08-06a-02, T-08-06a-03
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-06a-PLAN.md
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from medieval_forge.main import app


VALID_PROJECT_ID = str(uuid.uuid4())


@pytest.fixture
def valid_square_coords():
    """(lon, lat) ring — no closing duplicate — simple square."""
    return [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


@pytest.fixture
def figure_eight_coords():
    """Self-intersecting figure-8 polygon coords."""
    return [(0.0, 0.0), (2.0, 2.0), (2.0, 0.0), (0.0, 2.0)]


@pytest.fixture
def right_neighbour_coords():
    """Adjacent to valid_square_coords on the right side."""
    return [(1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0)]


@pytest.fixture
def far_square_coords():
    """Polygon far away — disjoint from valid_square_coords and right_neighbour."""
    return [(10.0, 10.0), (11.0, 10.0), (11.0, 11.0), (10.0, 11.0)]


@pytest.mark.asyncio
class TestValidateEndpoint:
    async def test_validate_returns_ok_for_valid_polygon(self, valid_square_coords):
        """EDIT-VERTEX-01: POST /editor/validate with valid polygon returns valid=True, code=None."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "poly-1",
                            "coords": valid_square_coords,
                            "neighbour_ids": [],
                        }
                    ],
                    "neighbour_lookup": {},
                },
            )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["polygon_id"] == "poly-1"
        assert results[0]["valid"] is True
        assert results[0]["code"] is None

    async def test_validate_returns_error_code_for_self_intersecting_polygon(
        self, figure_eight_coords
    ):
        """TOPO-01: self-intersecting polygon returns valid=False, code='SELF_INTERSECT'."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "bad-poly",
                            "coords": figure_eight_coords,
                            "neighbour_ids": [],
                        }
                    ],
                    "neighbour_lookup": {},
                },
            )
        assert resp.status_code == 200
        results = resp.json()
        assert results[0]["valid"] is False
        assert results[0]["code"] == "SELF_INTERSECT"

    async def test_validate_returns_neighbour_gap_when_polygon_disjoint(
        self, far_square_coords, right_neighbour_coords
    ):
        """TOPO-01: polygon disjoint from previously-touching neighbour returns NEIGHBOUR_GAP."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "moved-poly",
                            "coords": far_square_coords,
                            "neighbour_ids": ["neighbour-1"],
                        }
                    ],
                    "neighbour_lookup": {
                        "neighbour-1": right_neighbour_coords,
                    },
                },
            )
        assert resp.status_code == 200
        results = resp.json()
        assert results[0]["valid"] is False
        assert results[0]["code"] == "NEIGHBOUR_GAP"

    async def test_validate_returns_422_for_malformed_body(self):
        """T-08-06a-03: malformed body (missing required field) returns HTTP 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={"not_polygons": "garbage"},
            )
        assert resp.status_code == 422

    async def test_validate_returns_400_for_invalid_project_uuid(self, valid_square_coords):
        """T-08-06a-02: non-UUID project_id returns 400."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v3/projects/not-a-uuid/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "poly-1",
                            "coords": valid_square_coords,
                            "neighbour_ids": [],
                        }
                    ],
                    "neighbour_lookup": {},
                },
            )
        assert resp.status_code == 400

    async def test_validate_batch_returns_results_for_multiple_polygons(
        self, valid_square_coords, right_neighbour_coords
    ):
        """T-08-06a-02: batch of polygons returns per-polygon results in same order."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "poly-a",
                            "coords": valid_square_coords,
                            "neighbour_ids": [],
                        },
                        {
                            "polygon_id": "poly-b",
                            "coords": right_neighbour_coords,
                            "neighbour_ids": [],
                        },
                    ],
                    "neighbour_lookup": {},
                },
            )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2
        assert results[0]["polygon_id"] == "poly-a"
        assert results[1]["polygon_id"] == "poly-b"
        assert results[0]["valid"] is True
        assert results[1]["valid"] is True

    async def test_validate_returns_self_intersect_for_less_than_3_coords(self):
        """T-08-06a-03: polygon with fewer than 3 coords treated as invalid (SELF_INTERSECT)."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v3/projects/{VALID_PROJECT_ID}/editor/validate",
                json={
                    "polygons": [
                        {
                            "polygon_id": "degenerate",
                            "coords": [(0.0, 0.0), (1.0, 1.0)],
                            "neighbour_ids": [],
                        }
                    ],
                    "neighbour_lookup": {},
                },
            )
        assert resp.status_code == 200
        results = resp.json()
        assert results[0]["valid"] is False
        assert results[0]["code"] == "SELF_INTERSECT"
