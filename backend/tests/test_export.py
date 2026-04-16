"""Tests for EXPORT-01 (zip download) and EXPORT-02 (zip contents).

Stubs in Wave 0 of Plan 01-05; implemented in Tasks 2 and 3.
"""
import pytest


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 2 (services.export)")
async def test_build_unity_zip_assembles_12_files(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 2")
async def test_build_unity_zip_rejects_empty_generated_dir(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (api.export)")
async def test_zip_download(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (EXPORT-02 contents)")
async def test_zip_contents(client, tmp_path):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (T-PATH on download)")
async def test_download_invalid_uuid_returns_400(client):
    pass


@pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (refuses pre-generated state)")
async def test_export_refuses_if_not_generated(client):
    pass
