from __future__ import annotations

from datetime import date

import httpx
import pytest

import koreanpulse.dart as dart_mod
from koreanpulse.dart import (
    DART_HARD_DAILY_LIMIT,
    DartDailyQuotaExceeded,
    DartError,
    _classify_filing_type,
    _parse_filing,
    daily_usage_snapshot,
    list_filings,
)


@pytest.fixture(autouse=True)
def _reset_daily_counter():
    """Each test starts with a clean daily counter."""
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""
    yield
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""


# Sample DART API response (real format observed live 2026-05-04 — pblntf_ty is NOT included).
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
            "report_nm": "주요사항보고서(자기주식취득결정)",
            "rcept_no": "20260503000123",
            "flr_nm": "삼성전자",
            "rcept_dt": "20260503",
            "rm": "",
        },
        {
            "corp_code": "00164779",
            "corp_name": "SK하이닉스",
            "stock_code": "000660",
            "corp_cls": "Y",
            "report_nm": "분기보고서(2026.03)",
            "rcept_no": "20260503000456",
            "flr_nm": "SK하이닉스",
            "rcept_dt": "20260503",
            "rm": "",
        },
    ],
}

EMPTY_RESPONSE = {"status": "013", "message": "조회된 데이터가 없습니다."}

ERROR_RESPONSE = {"status": "020", "message": "사용한도를 초과하였습니다."}


class TestClassifyFilingType:
    def test_periodic(self):
        assert _classify_filing_type("사업보고서(2025.12)") == "A"
        assert _classify_filing_type("분기보고서(2026.03)") == "A"
        assert _classify_filing_type("반기보고서(2025.06)") == "A"

    def test_major_event(self):
        assert _classify_filing_type("주요사항보고서(자기주식취득결정)") == "B"
        assert _classify_filing_type("회사합병결정") == "B"
        assert _classify_filing_type("타법인주식및출자증권취득결정") == "B"

    def test_shareholding(self):
        assert _classify_filing_type("주식등의대량보유상황보고서") == "D"
        assert (
            _classify_filing_type("임원ㆍ주요주주특정증권등소유상황보고서") == "D"
        )

    def test_exchange_disclosure(self):
        assert _classify_filing_type("현금ㆍ현물배당결정") == "I"
        assert _classify_filing_type("특수관계인에대한출자") == "I"
        assert _classify_filing_type("공정공시") == "I"

    def test_amended_prefix_stripped(self):
        # [기재정정] prefix shouldn't bury the real type
        assert (
            _classify_filing_type("[기재정정]주요사항보고서(자기주식취득결정)")
            == "B"
        )
        assert (
            _classify_filing_type(
                "[기재정정]연결재무제표기준영업(잠정)실적(공정공시)"
            )
            == "A"
        )

    def test_unknown_falls_back_to_E(self):
        assert _classify_filing_type("완전 새로운 형식의 공시") == "E"


class TestParseFiling:
    def test_basic_parse_uses_title_inference(self):
        # No pblntf_ty in row — must infer from title
        row = SAMPLE_RESPONSE["list"][0]
        f = _parse_filing(row)
        assert f.corp_code == "00126380"
        assert f.corp_name_ko == "삼성전자"
        assert f.stock_code == "005930"
        # Inferred from "주요사항보고서" prefix
        assert f.filing_type == "B"
        assert f.filing_type_label_en == "Major Event Report"
        assert f.title == "주요사항보고서(자기주식취득결정)"
        assert f.receipt_no == "20260503000123"
        assert "20260503000123" in f.dart_url

    def test_periodic_filing_inferred(self):
        row = SAMPLE_RESPONSE["list"][1]
        f = _parse_filing(row)
        assert f.filing_type == "A"
        assert f.filing_type_label_en == "Periodic Disclosure"

    def test_requested_type_overrides_title(self):
        # If caller filtered by pblntf_ty, trust their intent
        row = SAMPLE_RESPONSE["list"][0]
        f = _parse_filing(row, requested_type="C")
        assert f.filing_type == "C"
        assert f.filing_type_label_en == "Securities Issuance Disclosure"


class TestListFilings:
    @pytest.mark.asyncio
    async def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        with pytest.raises(DartError, match="DART_API_KEY"):
            await list_filings(bgn_de=date.today(), end_de=date.today())

    @pytest.mark.asyncio
    async def test_successful_response(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/list.json"
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 3),
                end_de=date(2026, 5, 3),
                client=client,
            )
        assert len(filings) == 2
        assert filings[0].corp_name_ko == "삼성전자"
        assert filings[1].corp_name_ko == "SK하이닉스"

    @pytest.mark.asyncio
    async def test_empty_response(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=EMPTY_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 3),
                end_de=date(2026, 5, 3),
                client=client,
            )
        assert filings == []

    @pytest.mark.asyncio
    async def test_error_response(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ERROR_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="020"):
                await list_filings(
                    bgn_de=date(2026, 5, 3),
                    end_de=date(2026, 5, 3),
                    client=client,
                )


class TestDailyQuotaGuard:
    @pytest.mark.asyncio
    async def test_quota_blocks_when_full(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        # Simulate already at soft quota for the *current* KST window so the
        # bump function doesn't auto-reset on first call.
        from datetime import datetime
        from koreanpulse.dart import _KST
        dart_mod._daily_count = int(DART_HARD_DAILY_LIMIT * 0.8)
        dart_mod._daily_window_kst = datetime.now(_KST).date().isoformat()

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartDailyQuotaExceeded):
                await list_filings(
                    bgn_de=date(2026, 5, 3),
                    end_de=date(2026, 5, 3),
                    client=client,
                )

    @pytest.mark.asyncio
    async def test_quota_increments_on_success(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await list_filings(bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client)

        snap = daily_usage_snapshot()
        assert snap["calls"] == 1
        assert snap["soft_quota"] == int(DART_HARD_DAILY_LIMIT * 0.8)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DART_DAILY_QUOTA", "10000")
        from koreanpulse.dart import _read_daily_quota
        assert _read_daily_quota() == 10_000

    def test_env_override_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("DART_DAILY_QUOTA", "not_a_number")
        from koreanpulse.dart import _read_daily_quota
        assert _read_daily_quota() == int(DART_HARD_DAILY_LIMIT * 0.8)
