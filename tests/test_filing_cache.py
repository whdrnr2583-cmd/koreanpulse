from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

import koreanpulse.dart as dart_mod
from koreanpulse.cache import FileCache
from koreanpulse.dart import (
    _ttl_for_query,
    daily_usage_snapshot,
    list_filings_cached,
)


SAMPLE_RESPONSE = {
    "status": "000",
    "message": "정상",
    "page_no": 1,
    "page_count": 10,
    "total_count": 1,
    "total_page": 1,
    "list": [
        {
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "stock_code": "005930",
            "corp_cls": "Y",
            "report_nm": "분기보고서(2026.03)",
            "rcept_no": "20260503000123",
            "flr_nm": "삼성전자",
            "rcept_dt": "20260503",
            "rm": "",
        }
    ],
}


@pytest.fixture(autouse=True)
def _reset_daily_counter():
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""
    yield
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""


class TestTtlForQuery:
    def test_today_is_short(self):
        assert _ttl_for_query(date.today()) == 60

    def test_future_also_short(self):
        assert _ttl_for_query(date.today() + timedelta(days=1)) == 60

    def test_recent_past_is_one_hour(self):
        assert _ttl_for_query(date.today() - timedelta(days=3)) == 3600

    def test_old_is_one_day(self):
        assert _ttl_for_query(date.today() - timedelta(days=30)) == 86400

    def test_boundary_at_seven_days(self):
        # Exactly 7 days old → no longer "recent", goes to 24h
        assert _ttl_for_query(date.today() - timedelta(days=7)) == 86400


class TestListFilingsCached:
    @pytest.mark.asyncio
    async def test_first_call_hits_dart_then_caches(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        cache = FileCache(root=tmp_path / "cache")

        call_count = {"n": 0}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r1 = await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )
            r2 = await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )

        assert len(r1) == 1
        assert len(r2) == 1
        assert r1[0].corp_name_ko == r2[0].corp_name_ko == "삼성전자"
        # Second call must be cached → only 1 origin request
        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_burn_daily_quota(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        cache = FileCache(root=tmp_path / "cache")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )
            usage_after_first = daily_usage_snapshot()["calls"]
            await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )
            usage_after_second = daily_usage_snapshot()["calls"]

        assert usage_after_first == 1
        # Cache hit must not increment DART daily counter
        assert usage_after_second == 1

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        cache = FileCache(root=tmp_path / "cache")

        call_count = {"n": 0}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )
            await list_filings_cached(
                cache=cache,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
                force_refresh=True,
            )

        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_different_query_separate_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        cache = FileCache(root=tmp_path / "cache")

        call_count = {"n": 0}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await list_filings_cached(
                cache=cache,
                corp_code="00126380",
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )
            await list_filings_cached(
                cache=cache,
                corp_code="00164779",  # different corp
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )

        # Different corp_code → separate cache entries → both hit origin
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_cache_survives_process_restart(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)

        # First "process": populate cache
        cache1 = FileCache(root=tmp_path / "cache")
        async with httpx.AsyncClient(transport=transport) as client:
            await list_filings_cached(
                cache=cache1,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )

        usage_after_first_process = daily_usage_snapshot()["calls"]

        # Second "process": new cache instance, same root
        cache2 = FileCache(root=tmp_path / "cache")
        async with httpx.AsyncClient(transport=transport) as client:
            r = await list_filings_cached(
                cache=cache2,
                bgn_de=date(2026, 4, 1),
                end_de=date(2026, 4, 1),
                client=client,
            )

        assert len(r) == 1
        # Should NOT have made another origin call
        assert daily_usage_snapshot()["calls"] == usage_after_first_process
