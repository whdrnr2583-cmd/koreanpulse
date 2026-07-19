"""Unit tests for the koreanpulse OpenBB provider's CompanyFilings fetcher.

All DART network access is mocked (via monkeypatch on `koreanpulse.corp_code`
/ `koreanpulse.dart`, which the fetcher imports locally at call time) — no
network calls, runs anywhere.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import ValidationError

from openbb_koreanpulse import koreanpulse_provider
from openbb_koreanpulse.models.company_filings import (
    KoreanpulseCompanyFilingsData,
    KoreanpulseCompanyFilingsFetcher,
)


# ── Provider registration ──────────────────────────────────────────────────


def test_provider_registration():
    assert koreanpulse_provider.name == "koreanpulse"
    assert koreanpulse_provider.credentials == ["koreanpulse_api_key"]
    assert "CompanyFilings" in koreanpulse_provider.fetcher_dict
    assert (
        koreanpulse_provider.fetcher_dict["CompanyFilings"]
        is KoreanpulseCompanyFilingsFetcher
    )


def test_provider_description_has_no_pricing_or_checkout_strings():
    """Commerce-policy guard: this package must never surface koreanpulse
    pricing/checkout copy — only the DART key + koreanpulse.dev link."""
    text = (koreanpulse_provider.description + (koreanpulse_provider.instructions or "")).lower()
    for banned in ("$", "checkout", "subscribe", "buy.polar", "pricing"):
        assert banned not in text


# ── transform_query ─────────────────────────────────────────────────────


def test_transform_query_requires_symbol():
    with pytest.raises(ValidationError):
        KoreanpulseCompanyFilingsFetcher.transform_query({})


def test_transform_query_normalizes_short_numeric_symbol():
    q = KoreanpulseCompanyFilingsFetcher.transform_query({"symbol": "5930"})
    assert q.symbol == "005930"


def test_transform_query_normalizes_exchange_suffix():
    q = KoreanpulseCompanyFilingsFetcher.transform_query({"symbol": "005930.KS"})
    assert q.symbol == "005930"


def test_transform_query_defaults_date_window():
    q = KoreanpulseCompanyFilingsFetcher.transform_query({"symbol": "005930"})
    assert q.end_date == date.today()
    assert q.start_date == date.today() - timedelta(days=90)


def test_transform_query_respects_explicit_dates():
    q = KoreanpulseCompanyFilingsFetcher.transform_query(
        {"symbol": "005930", "start_date": "2026-01-01", "end_date": "2026-02-01"}
    )
    assert q.start_date == date(2026, 1, 1)
    assert q.end_date == date(2026, 2, 1)


def test_transform_query_limit_capped_at_100():
    with pytest.raises(ValidationError):
        KoreanpulseCompanyFilingsFetcher.transform_query({"symbol": "005930", "limit": 101})


# ── aextract_data ───────────────────────────────────────────────────────


class _FakeCorpEntry:
    def __init__(self, corp_code: str):
        self.corp_code = corp_code


def _query(**overrides):
    params = {"symbol": "005930", **overrides}
    return KoreanpulseCompanyFilingsFetcher.transform_query(params)


@pytest.mark.asyncio
async def test_aextract_data_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    with pytest.raises(OpenBBError, match="Missing DART API key"):
        await KoreanpulseCompanyFilingsFetcher.aextract_data(_query(), credentials=None)


@pytest.mark.asyncio
async def test_aextract_data_injects_credential_into_dart_api_key_env(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)

    async def fake_lookup(stock_code):
        assert stock_code == "005930"
        return _FakeCorpEntry("00126380")

    async def fake_list_filings(*, corp_code, bgn_de, end_de, page_count):
        import os

        # The credential must already be injected by the time DART is called.
        assert os.environ.get("DART_API_KEY") == "dummy-dart-key"
        return []

    monkeypatch.setattr("koreanpulse.corp_code.lookup_by_stock_code", fake_lookup)
    monkeypatch.setattr("koreanpulse.dart.list_filings", fake_list_filings)

    # aextract_data itself must not raise — env injection + DART call both
    # succeed cleanly, it's only transform_data that rejects an empty result.
    data = await KoreanpulseCompanyFilingsFetcher.aextract_data(
        _query(), credentials={"koreanpulse_api_key": "dummy-dart-key"}
    )
    assert data == []


@pytest.mark.asyncio
async def test_aextract_data_unresolvable_symbol_raises(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "dummy")

    async def fake_lookup(stock_code):
        return None

    monkeypatch.setattr("koreanpulse.corp_code.lookup_by_stock_code", fake_lookup)

    with pytest.raises(OpenBBError, match="No DART corp_code found"):
        await KoreanpulseCompanyFilingsFetcher.aextract_data(_query(), credentials=None)


@pytest.mark.asyncio
async def test_aextract_data_happy_path_returns_filing_dicts(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "dummy")

    from koreanpulse.models import Filing

    fake_filing = Filing(
        corp_code="00126380",
        corp_name_ko="삼성전자",
        corp_name_en="Samsung Electronics",
        stock_code="005930",
        market="KOSPI",
        filing_type="A",
        filing_type_label_ko="사업보고서",
        filing_type_label_en="Annual Report",
        title="사업보고서",
        red_flags=[],
        receipt_no="20260715000397",
        filed_at=datetime(2026, 7, 15),
        dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260715000397",
        attribution="Source: DART (Korea Financial Supervisory Service)",
    )

    async def fake_lookup(stock_code):
        return _FakeCorpEntry("00126380")

    async def fake_list_filings(*, corp_code, bgn_de, end_de, page_count):
        assert corp_code == "00126380"
        assert page_count == 100
        return [fake_filing]

    monkeypatch.setattr("koreanpulse.corp_code.lookup_by_stock_code", fake_lookup)
    monkeypatch.setattr("koreanpulse.dart.list_filings", fake_list_filings)

    data = await KoreanpulseCompanyFilingsFetcher.aextract_data(_query(), credentials=None)

    assert isinstance(data, list) and len(data) == 1
    assert data[0]["receipt_no"] == "20260715000397"
    assert data[0]["corp_name_en"] == "Samsung Electronics"


# ── transform_data ──────────────────────────────────────────────────────


def _filing_row(**overrides) -> dict:
    from koreanpulse.models import Filing

    filing = Filing(
        corp_code="00126380",
        corp_name_ko="삼성전자",
        corp_name_en="Samsung Electronics",
        stock_code="005930",
        market="KOSPI",
        filing_type="D",
        filing_type_label_ko="지분공시",
        filing_type_label_en="Shareholding Disclosure",
        title="주식등의대량보유상황보고서(일반)",
        red_flags=["cb_issuance"],
        receipt_no="20260707000434",
        filed_at=datetime(2026, 7, 7),
        dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260707000434",
        attribution="Source: DART (Korea Financial Supervisory Service)",
        is_correction=False,
    )
    return filing.model_dump(mode="json")


def test_transform_data_maps_standard_and_extra_fields():
    row = _filing_row()
    result = KoreanpulseCompanyFilingsFetcher.transform_data(_query(), [row])

    assert len(result) == 1
    item = result[0]
    assert isinstance(item, KoreanpulseCompanyFilingsData)
    # Standard CompanyFilingsData fields
    assert item.filing_date == date(2026, 7, 7)
    assert item.report_type == "Shareholding Disclosure"
    assert item.report_url == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260707000434"
    # koreanpulse extra fields
    assert item.symbol == "005930"
    assert item.corp_name == "삼성전자"
    assert item.corp_name_en == "Samsung Electronics"
    assert item.title == "주식등의대량보유상황보고서(일반)"
    assert item.receipt_no == "20260707000434"
    assert item.red_flags == ["cb_issuance"]
    assert item.is_correction is False
    assert item.previous_receipt_no is None


def test_transform_data_empty_raises_empty_data_error():
    with pytest.raises(EmptyDataError):
        KoreanpulseCompanyFilingsFetcher.transform_data(_query(), [])


def test_transform_data_respects_limit():
    rows = [_filing_row() for _ in range(5)]
    result = KoreanpulseCompanyFilingsFetcher.transform_data(_query(limit=2), rows)
    assert len(result) == 2


def test_transform_data_correction_filing_lineage():
    row = _filing_row()
    row["is_correction"] = True
    row["previous_receipt_no"] = "20260706000111"
    result = KoreanpulseCompanyFilingsFetcher.transform_data(_query(), [row])
    assert result[0].is_correction is True
    assert result[0].previous_receipt_no == "20260706000111"
