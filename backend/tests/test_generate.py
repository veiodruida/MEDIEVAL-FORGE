"""Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_projects_root(tmp_path, monkeypatch):
    from medieval_forge.services import paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")


def test_inject_territory_module_creates_sys_modules_entry():
    import importlib
    import sys

    from medieval_forge.services import generator

    name = "_mf_territory_test_unit"
    data = {
        "kingdoms": {"K1": {"name": "Kingdom One"}},
        "duchies": {"D1": {"name": "Duchy"}},
        "condados": {"C1": {"name": "County"}},
    }
    try:
        mod = generator._inject_territory_module(name, data)
        # importlib.import_module finds it (this is the call inside map_generator.load_territory_data).
        loaded = importlib.import_module(name)
        assert loaded is mod
        assert loaded.KINGDOMS == data["kingdoms"]
        assert loaded.DUCHIES == data["duchies"]
        assert loaded.CONDADOS == data["condados"]
    finally:
        generator._cleanup_territory_module(name)
    assert name not in sys.modules


@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (api.generate)")
async def test_trigger_generation(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (T-DOS overlap guard)")
async def test_trigger_generation_rejects_when_already_generating(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4")
async def test_png_fileresponse(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (T-PATH whitelist)")
async def test_preview_rejects_non_whitelisted_filename(client):
    pass


@pytest.mark.slow
@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (slow integration with real map_generator)")
async def test_png_outputs(client, tmp_path):
    pass


@pytest.mark.slow
@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (GEN-04 performance assertion)")
async def test_generation_time(client, tmp_path):
    pass
