"""Tests for PROJ-01..05 — project CRUD endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_projects_root(tmp_path, monkeypatch):
    """Redirect PROJECTS_ROOT to a tmp dir so tests don't pollute ~/.medieval-forge/."""
    from medieval_forge.services import paths as paths_mod

    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)


def _payload(**overrides):
    base = {
        "name": "Test Project",
        "country_qid": "Q29",
        "period_start": 868,
        "period_end": 1492,
    }
    base.update(overrides)
    return base


async def test_create_project(client):
    resp = await client.post("/api/projects", json=_payload())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Test Project"
    assert data["country_qid"] == "Q29"
    assert data["status"] == "created"
    assert "id" in data and len(data["id"]) == 36


async def test_list_projects(client):
    # Empty initially.
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []
    # Create two.
    await client.post("/api/projects", json=_payload(name="A"))
    await client.post("/api/projects", json=_payload(name="B"))
    resp = await client.get("/api/projects")
    names = [p["name"] for p in resp.json()]
    assert set(names) == {"A", "B"}


async def test_get_project(client):
    created = (await client.post("/api/projects", json=_payload())).json()
    pid = created["id"]
    resp = await client.get(f"/api/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


async def test_get_project_invalid_uuid_returns_400(client):
    resp = await client.get("/api/projects/not-a-uuid")
    assert resp.status_code == 400
    assert "uuid" in resp.json()["detail"].lower()


async def test_get_project_not_found_returns_404(client):
    # Valid UUID format but no row.
    resp = await client.get("/api/projects/550e8400-e29b-41d4-a716-446655440000")
    assert resp.status_code == 404


async def test_update_project(client):
    created = (await client.post("/api/projects", json=_payload())).json()
    pid = created["id"]
    resp = await client.patch(
        f"/api/projects/{pid}",
        json={"name": "Renamed", "period_end": 1500},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["period_end"] == 1500
    assert body["country_qid"] == "Q29"  # unchanged


async def test_delete_project(client):
    from medieval_forge.services.paths import PROJECTS_ROOT

    created = (await client.post("/api/projects", json=_payload())).json()
    pid = created["id"]
    # Folder exists post-create.
    assert (PROJECTS_ROOT / pid).exists()

    resp = await client.delete(f"/api/projects/{pid}")
    assert resp.status_code == 204

    # Row gone.
    resp = await client.get(f"/api/projects/{pid}")
    assert resp.status_code == 404
    # Folder gone.
    assert not (PROJECTS_ROOT / pid).exists()


async def test_create_project_creates_folders(client, tmp_path):
    from medieval_forge.services.paths import PROJECTS_ROOT

    created = (await client.post("/api/projects", json=_payload())).json()
    pid = created["id"]
    root = PROJECTS_ROOT / pid
    assert (root / "raw").is_dir()
    assert (root / "generated").is_dir()
    assert (root / "exports").is_dir()


async def test_country_qid_validation_rejects_bad_format(client):
    # "NOTACOUNTRY" is not a QID, ISO code, or recognized name — must reject with 422
    resp = await client.post("/api/projects", json=_payload(country_qid="NOTACOUNTRY"))
    assert resp.status_code == 422
    body = resp.json()
    assert any("country_qid" in str(err) for err in body["detail"])


# ---------------------------------------------------------------------------
# Multi-country QID validator tests (Task 2 — FIX-MULTI-COUNTRY)
# ---------------------------------------------------------------------------

import pytest
from pydantic import ValidationError as PydanticValidationError
from medieval_forge.schemas import ProjectCreate, ProjectUpdate


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("Q29", "Q29"),                         # single QID passthrough
        ("Espanha", "Q29"),                      # single name resolution
        ("Q29,Q45", "Q29,Q45"),                  # comma-separated QIDs
        ("Q29, Q45", "Q29,Q45"),                 # whitespace tolerant
        ("Espanha,Portugal", "Q29,Q45"),          # names resolved per token
    ],
)
def test_project_create_country_qid_multi(input_value: str, expected: str) -> None:
    p = ProjectCreate(
        name="Test",
        country_qid=input_value,
        period_start=868,
        period_end=1492,
    )
    assert p.country_qid == expected


@pytest.mark.parametrize(
    "input_value",
    [
        "Q29,INVALID",   # one bad token
        "",              # empty string
    ],
)
def test_project_create_country_qid_multi_rejects_bad(input_value: str) -> None:
    with pytest.raises(PydanticValidationError):
        ProjectCreate(
            name="Test",
            country_qid=input_value,
            period_start=868,
            period_end=1492,
        )


def test_project_update_country_qid_multi_accepts_none() -> None:
    p = ProjectUpdate(country_qid=None)
    assert p.country_qid is None


def test_project_update_country_qid_multi_accepts_comma_list() -> None:
    p = ProjectUpdate(country_qid="Q29,Q45")
    assert p.country_qid == "Q29,Q45"


def test_project_update_period_ordering_enforced() -> None:
    """Both bounds present and start >= end must raise."""
    with pytest.raises(PydanticValidationError):
        ProjectUpdate(period_start=1500, period_end=1400)


def test_project_update_period_ordering_single_bound_ok() -> None:
    """Only period_end set — no ordering check, must not raise."""
    p = ProjectUpdate(period_end=1500)
    assert p.period_end == 1500


async def test_patch_project_with_multi_country_qid(client):
    """PATCH /api/projects/{id} with comma-separated country_qid persists correctly."""
    created = (await client.post("/api/projects", json=_payload())).json()
    pid = created["id"]
    resp = await client.patch(
        f"/api/projects/{pid}",
        json={"country_qid": "Q29,Q45", "period_end": 1492},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["country_qid"] == "Q29,Q45"
    assert body["period_end"] == 1492
