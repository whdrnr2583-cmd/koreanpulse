from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

import koreanpulse.dart as dart_mod
from koreanpulse.cache import FileCache, NullCache
from koreanpulse.dart import (
    DART_HARD_DAILY_LIMIT,
    DartDailyQuotaExceeded,
    DartError,
    MajorHolding,
    _classify_filing_type,
    _is_correction_title,
    _link_corrections,
    _parse_filing,
    daily_usage_snapshot,
    list_filings,
    list_major_holdings,
)


@pytest.fixture(autouse=True)
def _reset_daily_counter():
    """Each test starts with a clean daily counter."""
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""
    yield
    dart_mod._daily_count = 0
    dart_mod._daily_window_kst = ""


@pytest.fixture(autouse=True)
def _isolate_default_cache(tmp_path):
    """`list_major_holdings` has no injectable `cache=` param — it reads
    the module-level default cache. Some other test module (test_server.py,
    via `koreanpulse.server` import) wires that default to a real
    `.data/cache` FileCache as a side effect of module import order during
    pytest collection — isolate it here so these tests never touch that
    real on-disk cache, and don't leak state to tests that run after."""
    dart_mod.set_default_cache(FileCache(root=tmp_path / "default_cache"))
    yield
    dart_mod.set_default_cache(NullCache())


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

    def test_rcept_no_as_int_is_coerced_to_str(self):
        """Non-source fixture: DART's own payloads always send rcept_no as a
        14-digit string, but a proxy/gateway could hand it back as a JSON
        number. `_parse_filing` must coerce rather than crash on `.strip()`.
        """
        row = {
            "corp_code": "01111111",
            "corp_name": "굿컴퍼니",
            "report_nm": "분기보고서(2026.03)",
            "rcept_no": 20260601000001,  # int, not str
            "rcept_dt": "20260601",
        }
        f = _parse_filing(row)
        assert f.receipt_no == "20260601000001"
        assert "20260601000001" in f.dart_url


def _row(corp_code, report_nm, rcept_no, *, corp_name="테스트", rcept_dt="20260503"):
    return {
        "corp_code": corp_code,
        "corp_name": corp_name,
        "report_nm": report_nm,
        "rcept_no": rcept_no,
        "rcept_dt": rcept_dt,
    }


class TestIsCorrectionTitle:
    def test_gijae_jeongjeong_is_correction(self):
        assert _is_correction_title("[기재정정]주요사항보고서(유상증자결정)")

    def test_cheombu_jeongjeong_is_correction(self):
        assert _is_correction_title("[첨부정정]사업보고서(2025.12)")

    def test_normal_title_is_not_correction(self):
        assert not _is_correction_title("주요사항보고서(유상증자결정)")

    def test_non_leading_jeongjeong_is_not_correction(self):
        # '정정' buried in the report name (not a leading bracket tag) must
        # not flag the filing.
        assert not _is_correction_title("정정공시 관련 안내")

    def test_non_correction_bracket_tag_is_not_correction(self):
        # A leading bracket tag without '정정' (e.g. [연장결정]) is not a
        # correction.
        assert not _is_correction_title("[연장결정]주요사항보고서")


class TestLinkCorrections:
    def test_correction_links_to_original_in_same_batch(self):
        original = _parse_filing(
            _row("00111111", "주요사항보고서(유상증자결정)", "20260503000100")
        )
        correction = _parse_filing(
            _row(
                "00111111",
                "[기재정정]주요사항보고서(유상증자결정)",
                "20260510000200",
            )
        )
        filings = [original, correction]
        _link_corrections(filings)
        assert correction.is_correction is True
        assert correction.previous_receipt_no == "20260503000100"
        # The original itself is untouched.
        assert original.is_correction is False
        assert original.previous_receipt_no is None

    def test_correction_without_original_leaves_none(self):
        correction = _parse_filing(
            _row(
                "00111111",
                "[기재정정]주요사항보고서(유상증자결정)",
                "20260510000200",
            )
        )
        # A different, unrelated filing shares the batch but not the report name.
        other = _parse_filing(
            _row("00111111", "분기보고서(2026.03)", "20260504000050")
        )
        filings = [correction, other]
        _link_corrections(filings)
        assert correction.is_correction is True
        assert correction.previous_receipt_no is None

    def test_normal_filing_is_not_flagged_or_linked(self):
        normal = _parse_filing(
            _row("00111111", "주요사항보고서(유상증자결정)", "20260503000100")
        )
        _link_corrections([normal])
        assert normal.is_correction is False
        assert normal.previous_receipt_no is None

    def test_does_not_link_across_corp_codes(self):
        # Same normalized report name but a different company — must not link.
        original = _parse_filing(
            _row("00111111", "주요사항보고서(유상증자결정)", "20260503000100")
        )
        correction = _parse_filing(
            _row(
                "00222222",
                "[기재정정]주요사항보고서(유상증자결정)",
                "20260510000200",
            )
        )
        _link_corrections([original, correction])
        assert correction.previous_receipt_no is None

    def test_links_to_closest_prior_when_multiple(self):
        v1 = _parse_filing(
            _row("00111111", "주요사항보고서(유상증자결정)", "20260501000100")
        )
        v2 = _parse_filing(
            _row(
                "00111111",
                "[기재정정]주요사항보고서(유상증자결정)",
                "20260505000100",
            )
        )
        v3 = _parse_filing(
            _row(
                "00111111",
                "[기재정정]주요사항보고서(유상증자결정)",
                "20260510000100",
            )
        )
        _link_corrections([v1, v2, v3])
        # v3 links to the immediately preceding version (v2), not the original.
        assert v3.previous_receipt_no == "20260505000100"
        # v2 links back to the original v1.
        assert v2.previous_receipt_no == "20260501000100"


class TestListFilings:
    @pytest.mark.asyncio
    async def test_correction_linking_through_list_filings(self, monkeypatch):
        """End-to-end: a batch containing a correction and its original must
        come back from `list_filings` already linked."""
        monkeypatch.setenv("DART_API_KEY", "test_key")
        response = {
            "status": "000",
            "message": "정상",
            "total_count": 2,
            "list": [
                _row(
                    "00111111",
                    "[기재정정]주요사항보고서(유상증자결정)",
                    "20260510000200",
                    rcept_dt="20260510",
                ),
                _row(
                    "00111111",
                    "주요사항보고서(유상증자결정)",
                    "20260503000100",
                    rcept_dt="20260503",
                ),
            ],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 1),
                end_de=date(2026, 5, 10),
                client=client,
            )
        by_receipt = {f.receipt_no: f for f in filings}
        correction = by_receipt["20260510000200"]
        assert correction.is_correction is True
        assert correction.previous_receipt_no == "20260503000100"
        assert by_receipt["20260503000100"].is_correction is False
        assert by_receipt["20260503000100"].previous_receipt_no is None

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


class TestListFilingsPayloadRobustness:
    """DART can return a 200 with a non-JSON / malformed body on maintenance
    or gateway errors. None of these should leak a raw traceback to the client
    — each must surface as a DartError (or degrade gracefully by skipping the
    bad row). Fixtures here are independent of SAMPLE_RESPONSE."""

    @pytest.mark.asyncio
    async def test_non_json_html_body_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html><body>maintenance</body></html>")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="non-JSON"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_empty_body_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="non-JSON"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_json_array_shape_raises_dart_error(self, monkeypatch):
        """Valid JSON but not the expected object envelope."""
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["unexpected", "array"])

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="unexpected JSON shape"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_malformed_row_missing_rcept_no_is_skipped(self, monkeypatch):
        """One bad row must not crash the whole request — good rows survive."""
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "message": "정상",
            "list": [
                {  # good row
                    "corp_code": "01111111",
                    "corp_name": "굿컴퍼니",
                    "stock_code": "111111",
                    "report_nm": "분기보고서(2026.03)",
                    "rcept_no": "20260601000001",
                    "rcept_dt": "20260601",
                },
                {  # malformed — no rcept_no (would have raised KeyError)
                    "corp_code": "02222222",
                    "corp_name": "배드컴퍼니",
                    "report_nm": "사업보고서",
                    "rcept_dt": "20260601",
                },
            ],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 6, 1), end_de=date(2026, 6, 1), client=client
            )
        assert len(filings) == 1
        assert filings[0].corp_name_ko == "굿컴퍼니"
        assert filings[0].receipt_no == "20260601000001"

    @pytest.mark.asyncio
    async def test_non_dict_row_is_skipped(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "list": [
                "not-a-dict",
                {
                    "corp_code": "03333333",
                    "corp_name": "정상회사",
                    "report_nm": "감사보고서",
                    "rcept_no": "20260601000009",
                    "rcept_dt": "20260601",
                },
            ],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 6, 1), end_de=date(2026, 6, 1), client=client
            )
        assert len(filings) == 1
        assert filings[0].corp_name_ko == "정상회사"

    @pytest.mark.asyncio
    async def test_rcept_no_as_int_is_not_skipped(self, monkeypatch):
        """The malformed-row skip guard must not itself crash on a
        non-string `rcept_no` (e.g. a JSON number) — this is the exact
        failure mode the guard was added to prevent. A row with an int
        rcept_no is well-formed enough to keep, not skip.
        """
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "list": [
                {
                    "corp_code": "04444444",
                    "corp_name": "숫자회사",
                    "report_nm": "감사보고서",
                    "rcept_no": 20260601000010,  # int, not str
                    "rcept_dt": "20260601",
                },
            ],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 6, 1), end_de=date(2026, 6, 1), client=client
            )
        assert len(filings) == 1
        assert filings[0].receipt_no == "20260601000010"


class TestListFilingsTransportErrors:
    """Network / HTTP-status failures must surface as a structured DartError,
    not a raw httpx exception — symmetric with corp_code._download_corp_code
    which wraps the same failure mode in CorpCodeError. Fixtures are synthetic
    (MockTransport), not real DART responses."""

    @pytest.mark.asyncio
    async def test_http_500_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="upstream boom")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="HTTP 500"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_http_429_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="slow down")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="HTTP 429"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="request failed after retries"):
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )

    @pytest.mark.asyncio
    async def test_raw_httpx_error_does_not_leak(self, monkeypatch):
        """The wrapped DartError must not itself be an httpx exception —
        callers that only know DartError must catch everything."""
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="maintenance")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError) as excinfo:
                await list_filings(
                    bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
                )
        assert not isinstance(excinfo.value, httpx.HTTPError)


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


class TestListFilingsQueryMetadata:
    """2026-07-12 — Filing.query_total_count / data_fetched_at additive
    fields, threaded through from a live `list_filings` fetch."""

    @pytest.mark.asyncio
    async def test_total_count_and_fetched_at_set_on_live_fetch(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        before = datetime.now(timezone.utc)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
            )
        after = datetime.now(timezone.utc)

        assert len(filings) == 2
        for f in filings:
            assert f.query_total_count == SAMPLE_RESPONSE["total_count"]
            assert f.data_fetched_at is not None
            assert before <= f.data_fetched_at <= after

    @pytest.mark.asyncio
    async def test_missing_total_count_coerces_to_none(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "list": [SAMPLE_RESPONSE["list"][0]],
        }  # no total_count key at all

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
            )
        assert filings[0].query_total_count is None

    @pytest.mark.asyncio
    async def test_non_numeric_total_count_coerces_to_none(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "total_count": "not-a-number",
            "list": [SAMPLE_RESPONSE["list"][0]],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            filings = await list_filings(
                bgn_de=date(2026, 5, 3), end_de=date(2026, 5, 3), client=client
            )
        assert filings[0].query_total_count is None

    def test_old_cache_json_without_query_metadata_round_trips_to_none(self):
        """A cache entry written before these fields existed has neither
        key in its serialized JSON — `Filing.model_validate` must default
        both to None rather than raising."""
        from koreanpulse.models import Filing

        old_cache_dict = {
            "corp_code": "00126380",
            "corp_name_ko": "삼성전자",
            "stock_code": "005930",
            "filing_type": "A",
            "filing_type_label_ko": "정기공시",
            "filing_type_label_en": "Periodic Disclosure",
            "title": "사업보고서",
            "red_flags": [],
            "receipt_no": "20260503000123",
            "filed_at": "2026-05-03T00:00:00",
            "dart_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260503000123",
            "attribution": "DART",
            # no query_total_count / data_fetched_at / holding_pct keys
        }
        f = Filing.model_validate(old_cache_dict)
        assert f.query_total_count is None
        assert f.data_fetched_at is None
        assert f.holding_pct is None
        assert f.holding_pct_change is None
        assert f.holder_reporter_ko is None


# Sample DART majorstock.json response — field names per DART's OpenAPI docs
# (repror = reporter, stkrt = current holding %, stkrt_irds = change vs the
# prior report). Only these 3 fields are parsed by `list_major_holdings`.
SAMPLE_MAJORSTOCK_RESPONSE = {
    "status": "000",
    "message": "정상",
    "list": [
        {
            "rcept_no": "20260601000111",
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "repror": "국민연금공단",
            "stkqy": "100000000",
            "stkqy_irds": "1000000",
            "stkrt": "8.51",
            "stkrt_irds": "0.10",
            "report_resn": "지분율 변동",
        },
        {
            "rcept_no": "20260601000112",
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "repror": "얼라인파트너스자산운용",
            "stkqy": "5000000",
            "stkqy_irds": "500000",
            "stkrt": "5.20",
            "stkrt_irds": "0.30",
            "report_resn": "지분율 변동",
        },
    ],
}

MAJORSTOCK_EMPTY = {"status": "013", "message": "조회된 데이터가 없습니다."}
MAJORSTOCK_ERROR = {"status": "020", "message": "사용한도를 초과하였습니다."}


class TestListMajorHoldings:
    @pytest.mark.asyncio
    async def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        with pytest.raises(DartError, match="DART_API_KEY"):
            await list_major_holdings("00126380")

    @pytest.mark.asyncio
    async def test_successful_response_parses_only_3_fields(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/majorstock.json"
            assert request.url.params["corp_code"] == "00126380"
            return httpx.Response(200, json=SAMPLE_MAJORSTOCK_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            holdings = await list_major_holdings("00126380", client=client)

        assert len(holdings) == 2
        assert holdings[0] == MajorHolding(
            repror="국민연금공단", stkrt=8.51, stkrt_irds=0.10
        )
        assert holdings[1] == MajorHolding(
            repror="얼라인파트너스자산운용", stkrt=5.20, stkrt_irds=0.30
        )

    @pytest.mark.asyncio
    async def test_status_013_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=MAJORSTOCK_EMPTY)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            assert await list_major_holdings("00999999", client=client) == []

    @pytest.mark.asyncio
    async def test_non_000_013_status_raises_dart_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=MAJORSTOCK_ERROR)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="020"):
                await list_major_holdings("00126380", client=client)

    @pytest.mark.asyncio
    async def test_row_missing_repror_is_skipped(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "list": [
                {"corp_code": "00126380", "stkrt": "5.0"},  # no repror
                {
                    "corp_code": "00126380",
                    "repror": "굿펀드",
                    "stkrt": "6.0",
                    "stkrt_irds": "-0.5",
                },
            ],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            holdings = await list_major_holdings("00126380", client=client)
        assert len(holdings) == 1
        assert holdings[0].repror == "굿펀드"
        assert holdings[0].stkrt_irds == -0.5

    @pytest.mark.asyncio
    async def test_non_dict_row_is_skipped(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {"status": "000", "list": ["not-a-dict", {"repror": "정상"}]}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            holdings = await list_major_holdings("00126380", client=client)
        assert len(holdings) == 1
        assert holdings[0].repror == "정상"

    @pytest.mark.asyncio
    async def test_unparseable_stkrt_coerces_to_none_not_raise(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        body = {
            "status": "000",
            "list": [{"repror": "이상한펀드", "stkrt": "n/a", "stkrt_irds": None}],
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            holdings = await list_major_holdings("00126380", client=client)
        assert holdings[0].stkrt is None
        assert holdings[0].stkrt_irds is None

    @pytest.mark.asyncio
    async def test_http_status_error_leaks_only_status_code(self, monkeypatch):
        """Mirrors list_filings' error pattern exactly — HTTPStatusError
        must never carry `crtfc_key` (query-string) into the error text."""
        secret_key = "SUPER_SECRET_DART_KEY_99999"
        monkeypatch.setenv("DART_API_KEY", secret_key)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="maintenance")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError, match="HTTP 503") as exc_info:
                await list_major_holdings("00126380", client=client)
        assert secret_key not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transport_error_leaks_only_exception_type_name(self, monkeypatch):
        """The non-HTTPStatusError branch must surface only
        `type(exc).__name__` — no key, no URL, not even the raw exception
        message (stricter than list_filings' current `{exc}` interpolation,
        per this task's explicit instruction)."""
        secret_key = "SUPER_SECRET_DART_KEY_99999"
        monkeypatch.setenv("DART_API_KEY", secret_key)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(
                f"connection refused for corp_code=00126380&crtfc_key={secret_key}"
            )

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(DartError) as exc_info:
                await list_major_holdings("00126380", client=client)
        assert secret_key not in str(exc_info.value)
        assert "ConnectError" in str(exc_info.value)
        assert not isinstance(exc_info.value, httpx.HTTPError)

    @pytest.mark.asyncio
    async def test_bumps_daily_counter(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SAMPLE_MAJORSTOCK_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await list_major_holdings("00126380", client=client)
        assert daily_usage_snapshot()["calls"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_skips_network_and_daily_counter(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        call_count = {"n": 0}

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, json=SAMPLE_MAJORSTOCK_RESPONSE)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r1 = await list_major_holdings("00126380", client=client)
            r2 = await list_major_holdings("00126380", client=client)

        assert call_count["n"] == 1  # second call served from cache
        assert r1 == r2
        assert daily_usage_snapshot()["calls"] == 1
