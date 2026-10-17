"""koreanpulse_about must not present the paused hosted endpoint as live."""

import pytest

from koreanpulse import server


@pytest.mark.asyncio
async def test_about_marks_hosted_endpoint_paused(monkeypatch):
    async def _no_index():
        return 0

    monkeypatch.setattr(server, "ensure_index_loaded", _no_index)
    about = await server.koreanpulse_about()

    status = about["endpoint_status"]
    assert "paused since 2026-09-21" in status
    assert "stdio" in status
