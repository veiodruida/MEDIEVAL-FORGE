"""Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard.

Stubs in Wave 0 of Plan 01-04; implemented in Tasks 3, 4, 5.
"""
import pytest


@pytest.mark.skip(reason="Implemented by Plan 01-04 Task 3 (services.generator)")
def test_inject_territory_module_creates_sys_modules_entry():
    pass


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
