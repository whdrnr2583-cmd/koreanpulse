"""Tool-level behaviour of the MCP entry points: paging/scan correctness,
input validation, empty/partial/degraded result reporting.

DART is simulated by a fake `list_filings_cached` that honours `page_no` /
`page_count` over an in-memory dataset exactly like list.json does (newest
first, `query_total_count` = size of the unfiltered result), so these tests
fail if a tool sizes the DART page by `limit` and filters afterwards.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest

import koreanpulse.server as server_mod
from koreanpulse.corp_code import CorpEntry
from koreanpulse.models import Article, Filing
from koreanpulse.server import (
    lookup_corp_code,
    monitor_activist_investors,
    monitor_foreign_holders,
    search_korean_industry_news,
    track_korean_filings,
)


def _f(i: int, *, filer: str = "개인투자자", red_flags: Optional[list[str]] = None,
       corp: str = "00000001", title: str = "주식등의대량보유상황보고서(일반)") -> Filing:
    return Filing(
        corp_code=corp,
        corp_name_ko="회사",
        filing_type="D",
        filing_type_label_ko="지분공시",
        filing_type_label_en="Shareholding",
        title=title,
        receipt_no=f"2026100{i:07d}",
        filed_at=datetime(2026, 10, 1),
        dart_url="https://dart.fss.or.kr/x",
        attribution="DART",
        filer_name_ko=filer,
        red_flags=red_flags or [],
    )


class FakeDart:
    """Stands in for `list_filings_cached` over a fixed newest-first dataset."""

    def __init__(self, rows: list[Filing], *, fail_codes: tuple[str, ...] = ()) -> None:
        self.rows = rows
        self.calls: list[dict] = []
        self.fail_codes = fail_codes

    async def __call__(self, *, cache, corp_code, bgn_de, end_de, pblntf_ty, page_count, page_no=1):
        self.calls.append({"corp_code": corp_code, "page_no": page_no, "page_count": page_count,
                           "pblntf_ty": pblntf_ty})
        if corp_code in self.fail_codes:
            raise RuntimeError("DART 800: maintenance")
        pool = [r for r in self.rows if corp_code is None or r.corp_code == corp_code]
        start = (page_no - 1) * page_count
        page = [r.model_copy(update={"query_total_count": len(pool)}) for r in pool[start:start + page_count]]
        return page


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("KOREANPULSE_REQUIRE_LICENSE", raising=False)
    monkeypatch.delenv("KOREANPULSE_MAX_SCAN_PAGES", raising=False)

    async def _ok(license_key, *, cost_units=1):
        return None

    monkeypatch.setattr(server_mod, "validate_license_or_raise", _ok)


def _install(monkeypatch, rows, **kw) -> FakeDart:
    fake = FakeDart(rows, **kw)
    monkeypatch.setattr(server_mod, "list_filings_cached", fake)
    return fake


class TestMonitorScansBeyondTheNewestPage:
    """Regression: the allowlist used to run on only the newest `limit`
    shareholding filings of ALL companies, so a BlackRock/KCGI filing a few
    hundred rows deep was reported as 'no match' — a false all-clear."""

    @pytest.mark.asyncio
    async def test_foreign_holder_hidden_behind_300_unrelated_filings_is_found(self, monkeypatch):
        rows = [_f(i) for i in range(300)] + [_f(300, filer="블랙록 펀드 어드바이저스")]
        fake = _install(monkeypatch, rows)
        result = await monitor_foreign_holders(translate=False, enrich_holdings=False, limit=50)
        assert [r.holder_label for r in result] == ["BlackRock"]
        assert [c["page_count"] for c in fake.calls] == [100, 100, 100, 100]
        assert [c["page_no"] for c in fake.calls] == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_activist_only_hidden_deep_is_found(self, monkeypatch):
        rows = [_f(i) for i in range(250)] + [_f(250, filer="KCGI")]
        _install(monkeypatch, rows)
        result = await monitor_activist_investors(
            activist_only=True, translate=False, enrich_holdings=False, limit=20
        )
        assert [r.activist_label for r in result] == ["KCGI"]

    @pytest.mark.asyncio
    async def test_scan_stops_once_enough_matches_are_found(self, monkeypatch):
        rows = [_f(i, filer="블랙록") for i in range(450)]
        fake = _install(monkeypatch, rows)
        result = await monitor_foreign_holders(translate=False, enrich_holdings=False, limit=5)
        assert len(fake.calls) == 1            # first page already holds > 5 matches
        assert isinstance(result, dict) and result["next_page"] == 2
        assert len(result["filings"]) == 5

    @pytest.mark.asyncio
    async def test_scan_cap_is_reported_not_hidden(self, monkeypatch):
        monkeypatch.setenv("KOREANPULSE_MAX_SCAN_PAGES", "2")
        rows = [_f(i) for i in range(500)] + [_f(500, filer="블랙록")]
        _install(monkeypatch, rows)
        result = await monitor_foreign_holders(translate=False, enrich_holdings=False)
        assert result["filings"] == []
        joined = " ".join(result["notes"])
        assert "INCOMPLETE SCAN" in joined and "200 of 501" in joined

    @pytest.mark.asyncio
    async def test_complete_scan_with_no_match_says_so(self, monkeypatch):
        _install(monkeypatch, [_f(i) for i in range(30)])
        result = await monitor_foreign_holders(translate=False, enrich_holdings=False)
        assert result["filings"] == []
        assert "INCOMPLETE" not in " ".join(result["notes"])
        assert "no allowlisted holder filed" in " ".join(result["notes"])
        assert result["window_kst"]["to"] == server_mod._kst_today().isoformat()

    @pytest.mark.asyncio
    async def test_second_page_of_matches(self, monkeypatch):
        rows = [_f(i, filer="블랙록") for i in range(7)]
        _install(monkeypatch, rows)
        p2 = await monitor_foreign_holders(
            translate=False, enrich_holdings=False, limit=5, page=2
        )
        # last page, nothing to caveat: the plain list shape
        assert [r.receipt_no for r in p2] == [r.receipt_no for r in rows[5:]]

    @pytest.mark.asyncio
    async def test_unknown_origin_is_rejected_not_silently_empty(self, monkeypatch):
        _install(monkeypatch, [])
        with pytest.raises(ValueError, match="origin"):
            await monitor_foreign_holders(origin="usa", translate=False)

    @pytest.mark.asyncio
    async def test_origin_filter_still_applies(self, monkeypatch):
        rows = [_f(0, filer="블랙록"), _f(1, filer="슈로더")]
        _install(monkeypatch, rows)
        result = await monitor_foreign_holders(origin="UK", translate=False, enrich_holdings=False)
        assert [r.holder_label for r in result] == ["Schroders"]

    @pytest.mark.asyncio
    async def test_non_allowlisted_activist_rows_are_flagged_false(self, monkeypatch):
        _install(monkeypatch, [_f(0, filer="개인투자자"), _f(1, filer="얼라인파트너스")])
        result = await monitor_activist_investors(translate=False, enrich_holdings=False)
        assert [r.is_likely_activist for r in result] == [False, True]


class TestMaterialOnlyDoesNotMissOlderRows:
    @pytest.mark.asyncio
    async def test_red_flag_row_beyond_the_limit_window_is_found(self, monkeypatch):
        rows = [_f(i, corp="00000009", title="사업보고서") for i in range(120)]
        rows.append(_f(120, corp="00000009", red_flags=["cb_issuance"]))
        _install(monkeypatch, rows)
        result = await track_korean_filings(
            company_corp_code="00000009", material_only=True, limit=30, translate=False
        )
        assert [f.receipt_no for f in result] == [rows[-1].receipt_no]


class TestTrackFilingsReporting:
    @pytest.mark.asyncio
    async def test_empty_result_explains_itself(self, monkeypatch):
        _install(monkeypatch, [])
        result = await track_korean_filings(company_corp_code="00126380", translate=False)
        assert result["filings"] == []
        assert "No filings found" in result["notes"][0]
        assert set(result["window_kst"]) == {"from", "to"}

    @pytest.mark.asyncio
    async def test_truncation_points_at_next_page(self, monkeypatch):
        rows = [_f(i, corp="00000001", title="사업보고서") for i in range(75)]
        fake = _install(monkeypatch, rows)
        result = await track_korean_filings(limit=30, translate=False)
        assert len(result["filings"]) == 30
        assert result["next_page"] == 2 and result["total_matches"] == 75
        again = await track_korean_filings(limit=30, translate=False, page=3)
        assert isinstance(again, list) and len(again) == 15
        assert fake.calls[-1]["page_no"] == 3

    @pytest.mark.asyncio
    async def test_batch_partial_failure_is_marked_incomplete(self, monkeypatch):
        rows = [_f(0, corp="00000001", title="사업보고서")]
        _install(monkeypatch, rows, fail_codes=("00000002",))
        result = await track_korean_filings(
            company_corp_codes=["00000001", "00000002"], translate=False
        )
        assert [f.corp_code for f in result["filings"]] == ["00000001"]
        assert result["errors"][0]["corp_code"] == "00000002"
        assert result["notes"][0].startswith("INCOMPLETE")

    @pytest.mark.asyncio
    async def test_batch_total_failure_raises(self, monkeypatch):
        _install(monkeypatch, [], fail_codes=("00000001", "00000002"))
        with pytest.raises(RuntimeError, match="DART 800"):
            await track_korean_filings(company_corp_codes=["00000001", "00000002"], translate=False)

    @pytest.mark.asyncio
    async def test_since_time_of_day_does_not_drop_same_day_filings(self, monkeypatch):
        """Filings are date-granular (midnight KST). A checkpoint of 09:00 on
        the day must not exclude that day's later filings."""
        today = server_mod._kst_today()
        row = _f(0, title="사업보고서").model_copy(
            update={"filed_at": datetime(today.year, today.month, today.day)}
        )
        _install(monkeypatch, [row])
        result = await track_korean_filings(
            since=f"{today.isoformat()}T09:00:00", translate=False
        )
        assert [f.receipt_no for f in result] == [row.receipt_no]


class TestInputValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad,needle",
        [
            ("005930", "resolve_stock_code"),
            ("삼성전자", "lookup_corp_code"),
            ("1234", "exactly 8 digits"),
            ("0012638O", "lookup_corp_code"),
        ],
    )
    async def test_bad_corp_code_message_names_the_right_tool(self, monkeypatch, bad, needle):
        _install(monkeypatch, [])
        with pytest.raises(ValueError, match=needle):
            await track_korean_filings(company_corp_code=bad, translate=False)

    @pytest.mark.asyncio
    async def test_bad_corp_code_in_batch_and_monitors(self, monkeypatch):
        _install(monkeypatch, [])
        with pytest.raises(ValueError, match="company_corp_codes"):
            await track_korean_filings(company_corp_codes=["00126380", "x"], translate=False)
        with pytest.raises(ValueError, match="company_corp_code"):
            await monitor_foreign_holders(company_corp_code="005930", translate=False)
        with pytest.raises(ValueError, match="company_corp_code"):
            await monitor_activist_investors(company_corp_code="005930", translate=False)

    @pytest.mark.asyncio
    async def test_filing_type_validated_and_uppercased(self, monkeypatch):
        fake = _install(monkeypatch, [])
        with pytest.raises(ValueError, match="A-J"):
            await track_korean_filings(filing_type="shareholding", translate=False)
        await track_korean_filings(filing_type="d", translate=False)
        assert fake.calls[0]["pblntf_ty"] == "D"

    @pytest.mark.asyncio
    async def test_limit_and_days_are_clamped(self, monkeypatch):
        fake = _install(monkeypatch, [])
        await track_korean_filings(limit=0, days=-5, translate=False)
        await track_korean_filings(limit=10_000, translate=False)
        assert [c["page_count"] for c in fake.calls] == [1, 100]


class _Unconfigured:
    configured = False


class _Flaky:
    configured = True

    async def translate_ko_to_en(self, text, *, labels=None):
        if "실패" in text:
            raise RuntimeError("provider down")
        return f"EN:{text}"

    async def translate_corp_name(self, name, *, labels=None):
        return "Corp"


class TestDegradedTranslationIsReported:
    @pytest.mark.asyncio
    async def test_no_backend_configured_is_stated_once(self, monkeypatch):
        _install(monkeypatch, [_f(0, title="사업보고서"), _f(1, title="반기보고서")])
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Unconfigured())
        result = await track_korean_filings(translate=True)
        assert all(f.title_en is None for f in result["filings"])
        assert len([n for n in result["notes"] if "no translation backend" in n]) == 1

    @pytest.mark.asyncio
    async def test_partial_translation_failure_is_counted(self, monkeypatch):
        _install(monkeypatch, [_f(0, title="사업보고서"), _f(1, title="실패 보고서")])
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Flaky())
        result = await track_korean_filings(translate=True)
        assert "1 of 2 titles could not be translated" in " ".join(result["notes"])
        assert sorted(f.title_en or "" for f in result["filings"]) == ["", "EN:사업보고서"]

    @pytest.mark.asyncio
    async def test_clean_translation_keeps_bare_list(self, monkeypatch):
        _install(monkeypatch, [_f(0, title="사업보고서")])
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Flaky())
        result = await track_korean_filings(translate=True)
        assert isinstance(result, list) and result[0].title_en == "EN:사업보고서"


class TestLookupCorpCodeEmptyResult:
    @pytest.fixture(autouse=True)
    def _index(self):
        import koreanpulse.corp_code as cc

        cc._install([CorpEntry("00126380", "삼성전자", "005930", "20260101")])
        yield
        cc._install([])
        cc._LOADED_AT = 0.0

    @pytest.mark.asyncio
    async def test_english_miss_explains_the_index_is_korean(self):
        result = await lookup_corp_code("Acme Widgets")
        assert result["matches"] == []
        assert "Korean" in " ".join(result["notes"])

    @pytest.mark.asyncio
    async def test_digits_point_to_the_right_tool(self):
        result = await lookup_corp_code("005930")
        assert "resolve_stock_code" in " ".join(result["notes"])

    @pytest.mark.asyncio
    async def test_hit_is_a_bare_list_and_english_alias_works(self):
        result = await lookup_corp_code("Samsung Electronics")
        assert [e.corp_code for e in result] == ["00126380"]

    @pytest.mark.asyncio
    async def test_blank_query_is_a_clear_error(self):
        with pytest.raises(ValueError, match="query"):
            await lookup_corp_code("   ")


def _article(title="HBM 공급", source="etnews") -> Article:
    return Article(
        title_ko=title, title_en="", source_key=source, source_name="전자신문",
        url="https://x/1", published_at=datetime(2026, 10, 20), summary_en="",
        industries=["semiconductor"], attribution="Source: x",
    )


class TestNewsReporting:
    @pytest.mark.asyncio
    async def test_failed_source_is_reported_as_incomplete(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None, failures=None):
            failures.append("zdnet")
            return [_article()]

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(translate=False)
        assert "INCOMPLETE" in result["notes"][0] and "zdnet" in result["notes"][0]
        assert len(result["articles"]) == 1

    @pytest.mark.asyncio
    async def test_only_unknown_sources_is_an_error(self, monkeypatch):
        with pytest.raises(ValueError, match="unknown source"):
            await search_korean_industry_news(sources=["bloomberg"], translate=False)

    @pytest.mark.asyncio
    async def test_industry_tags_are_case_insensitive(self, monkeypatch):
        seen = {}

        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None, failures=None):
            seen["industries"] = industries
            return [_article()]

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(industries=["Semiconductor "], translate=False)
        assert isinstance(result, list)
        assert seen["industries"] == ["semiconductor"]

    @pytest.mark.asyncio
    async def test_empty_news_explains_feed_window(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None, failures=None):
            return []

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(translate=False)
        assert result["articles"] == [] and "most recent items" in result["notes"][0]


class TestStartupWarnings:
    def test_missing_dart_key_is_called_out_without_leaking_values(self, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Unconfigured())
        warnings = server_mod._startup_warnings()
        assert any("DART_API_KEY is not set" in w for w in warnings)
        assert any("OPENAI_API_KEY" in w for w in warnings)

    def test_placeholder_key_is_called_out(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "your-40-char-dart-key-here")
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Flaky())
        warnings = server_mod._startup_warnings()
        assert len(warnings) == 1 and "placeholder" in warnings[0]
        assert "your-40" not in warnings[0]

    def test_clean_config_is_silent(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "a" * 40)
        monkeypatch.setattr(server_mod, "_get_translator", lambda: _Flaky())
        assert server_mod._startup_warnings() == []


class TestKeyHygiene:
    def test_http_client_loggers_are_not_at_info(self):
        """DART request URLs carry crtfc_key; httpx logs URLs at INFO."""
        import logging

        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.NOTSET)   # as basicConfig(INFO) leaves it
        server_mod._quiet_http_loggers()
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING

    @pytest.mark.asyncio
    async def test_dart_key_never_reaches_a_tool_error(self, monkeypatch):
        """End to end through the real client: a transport failure must not
        put the request URL (and so the key) into the message the agent sees."""
        import httpx

        import koreanpulse.dart as dart_mod

        monkeypatch.setenv("DART_API_KEY", "SUPERSECRETKEY0123456789")
        monkeypatch.setattr(server_mod, "list_filings_cached", dart_mod.list_filings_cached)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        real = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda *a, **k: real(transport=httpx.MockTransport(handler), timeout=5.0),
        )
        with pytest.raises(Exception) as ei:
            await track_korean_filings(translate=False, days=1)
        assert "SUPERSECRET" not in str(ei.value)
        assert "SUPERSECRET" not in repr(ei.value.__cause__)
