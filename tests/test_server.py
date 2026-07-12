"""Enrichment-helper unit tests.

`fill_corp_name_en` lives in `koreanpulse._enrich` rather than
`koreanpulse.server` so it can be tested without the FastMCP runtime
(which `server.py` imports at module load). The MCP tool entry points
themselves are integration-tested via `examples/quickstart.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest

import koreanpulse._enrich as enrich_mod
import koreanpulse.corp_code as corp_code_mod
import koreanpulse.server as server_mod
from koreanpulse._enrich import fill_corp_name_en, fill_holding_pct
from koreanpulse.cache import FileCache
from koreanpulse.corp_code import CorpEntry
from koreanpulse.dart import MajorHolding
from koreanpulse.models import Article, Filing, ForeignHolderFiling
from koreanpulse.server import resolve_stock_code, search_korean_industry_news
from koreanpulse.translate import Translator


def _filing(
    *, code: str, name_ko: str, en: Optional[str] = None, title: str = "사업보고서"
) -> Filing:
    return Filing(
        corp_code=code,
        corp_name_ko=name_ko,
        corp_name_en=en,
        stock_code=None,
        filing_type="A",
        filing_type_label_ko="정기공시",
        filing_type_label_en="Periodic",
        title=title,
        receipt_no=f"rcpt_{code}",
        filed_at=datetime(2026, 5, 5, 9, 0, 0),
        dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=rcpt",
        attribution="DART",
    )


class _FakeTranslator:
    """Minimal stand-in for `Translator` — records calls and returns
    deterministic English names for known fixtures."""

    def __init__(self, mapping: Optional[dict[str, str]] = None) -> None:
        self.mapping = mapping or {}
        self.calls: list[str] = []

    async def translate_corp_name(
        self, name_ko: str, *, labels: Optional[dict] = None
    ) -> str:
        self.calls.append(name_ko)
        return self.mapping.get(name_ko, f"[Romanised] {name_ko}")


class TestFillCorpNameEn:
    @pytest.mark.asyncio
    async def test_fills_english_name_from_translator(self):
        tr = _FakeTranslator({"삼성전자": "Samsung Electronics"})
        f = _filing(code="00126380", name_ko="삼성전자")
        await fill_corp_name_en([f], tr, op="test")  # type: ignore[arg-type]
        assert f.corp_name_en == "Samsung Electronics"
        assert tr.calls == ["삼성전자"]

    @pytest.mark.asyncio
    async def test_skips_when_already_filled(self):
        tr = _FakeTranslator({"삼성전자": "Samsung Electronics"})
        f = _filing(code="00126380", name_ko="삼성전자", en="Samsung Electronics")
        await fill_corp_name_en([f], tr, op="test")  # type: ignore[arg-type]
        # Should not have called the translator at all
        assert tr.calls == []
        assert f.corp_name_en == "Samsung Electronics"

    @pytest.mark.asyncio
    async def test_intra_batch_dedup_by_corp_code(self):
        """Same corp_code across multiple filings → only one LLM call."""
        tr = _FakeTranslator({"삼성전자": "Samsung Electronics"})
        f1 = _filing(code="00126380", name_ko="삼성전자", title="사업보고서")
        f2 = _filing(code="00126380", name_ko="삼성전자", title="주요사항보고서")
        f3 = _filing(code="00126380", name_ko="삼성전자", title="공정공시")
        await fill_corp_name_en([f1, f2, f3], tr, op="test")  # type: ignore[arg-type]
        assert all(f.corp_name_en == "Samsung Electronics" for f in (f1, f2, f3))
        assert tr.calls == ["삼성전자"]  # exactly once

    @pytest.mark.asyncio
    async def test_different_corps_each_get_one_call(self):
        tr = _FakeTranslator(
            {"삼성전자": "Samsung Electronics", "셀트리온": "Celltrion"}
        )
        f1 = _filing(code="00126380", name_ko="삼성전자")
        f2 = _filing(code="00421045", name_ko="셀트리온")
        await fill_corp_name_en([f1, f2], tr, op="test")  # type: ignore[arg-type]
        assert f1.corp_name_en == "Samsung Electronics"
        assert f2.corp_name_en == "Celltrion"
        assert sorted(tr.calls) == ["삼성전자", "셀트리온"]

    @pytest.mark.asyncio
    async def test_empty_corp_name_skipped(self):
        tr = _FakeTranslator()
        f = _filing(code="00000000", name_ko="")
        await fill_corp_name_en([f], tr, op="test")  # type: ignore[arg-type]
        assert tr.calls == []
        assert f.corp_name_en is None

    @pytest.mark.asyncio
    async def test_translator_failure_does_not_block(self, caplog):
        """If the translator raises, the helper logs and continues —
        a bad LLM response must never break the response shape."""

        class Boom(_FakeTranslator):
            async def translate_corp_name(
                self, name_ko: str, *, labels: Optional[dict] = None
            ) -> str:
                self.calls.append(name_ko)
                raise RuntimeError("simulated llm 503")

        tr = Boom()
        f = _filing(code="00126380", name_ko="삼성전자")
        await fill_corp_name_en([f], tr, op="test")  # type: ignore[arg-type]
        assert f.corp_name_en is None  # not filled, but no exception raised
        assert tr.calls == ["삼성전자"]

    @pytest.mark.asyncio
    async def test_works_on_foreign_holder_filings(self):
        """ForeignHolderFiling extends Filing — same helper must work on
        its rows without special-casing."""
        tr = _FakeTranslator({"삼성전자": "Samsung Electronics"})
        fhf = ForeignHolderFiling(
            corp_code="00126380",
            corp_name_ko="삼성전자",
            stock_code="005930",
            filing_type="D",
            filing_type_label_ko="지분공시",
            filing_type_label_en="Shareholding",
            title="주식등의대량보유상황보고서",
            receipt_no="rcpt_x",
            filed_at=datetime(2026, 5, 5, 9, 0, 0),
            dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=rcpt_x",
            attribution="DART",
            holder_label="BlackRock",
            holder_origin="us",
        )
        await fill_corp_name_en([fhf], tr, op="test")  # type: ignore[arg-type]
        assert fhf.corp_name_en == "Samsung Electronics"

class TestFillCorpNameEnWithRealTranslator:
    """Integration with the real Translator class — verifies the helper
    couples cleanly with the FileCache so the second call hits cache."""

    @pytest.mark.asyncio
    async def test_second_call_hits_cache(self, tmp_path, monkeypatch):
        # Use a real Translator with a FileCache; mock `_call_llm` to count
        # actual provider hits (cache miss) vs hits (cache hit).
        cache = FileCache(root=tmp_path / "cache")
        translator = Translator(cache=cache, provider="openai", api_key="dummy")

        n_calls = {"count": 0}

        async def fake_call_llm(*, system, user, max_tokens, labels):  # noqa: ANN001
            n_calls["count"] += 1
            return f"[stub] {user}"

        monkeypatch.setattr(translator, "_call_llm", fake_call_llm)

        # First batch: one unique corp, one LLM call expected
        f1 = _filing(code="00126380", name_ko="삼성전자")
        await fill_corp_name_en([f1], translator, op="test")
        assert n_calls["count"] == 1
        assert f1.corp_name_en == "[stub] 삼성전자"

        # Second batch: same corp, must hit FileCache → no new LLM call
        f2 = _filing(code="00126380", name_ko="삼성전자", title="다른 공시")
        await fill_corp_name_en([f2], translator, op="test")
        assert n_calls["count"] == 1  # still 1
        assert f2.corp_name_en == "[stub] 삼성전자"


class TestResolveStockCodePreferredStockHint:
    """2026-07-12 — `resolve_stock_code` returns bare `None` for an
    unresolved code today, even when the code is shaped like a Korean
    preferred-stock ticker (e.g. 005935 for 삼성전자우) whose common-stock
    sibling *is* resolvable (005930). This adds an additive hint for that
    case without fabricating a preferred-stock corp_code/name — resolved
    lookups and genuinely-unresolvable codes are unaffected."""

    @pytest.fixture(autouse=True)
    def _seed(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_REQUIRE_LICENSE", raising=False)
        entries = [CorpEntry("00126380", "삼성전자", "005930", "20260101")]
        corp_code_mod._INDEX = entries
        corp_code_mod._BY_NAME = {e.corp_name: e for e in entries}
        corp_code_mod._BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
        corp_code_mod._BY_CORP = {e.corp_code: e for e in entries}
        yield
        corp_code_mod._INDEX = []
        corp_code_mod._BY_NAME = {}
        corp_code_mod._BY_STOCK = {}
        corp_code_mod._BY_CORP = {}

    @pytest.mark.asyncio
    async def test_preferred_stock_code_gets_common_stock_hint(self):
        result = await resolve_stock_code("005935")
        assert result == {
            "related_common_stock": {
                "stock_code": "005930",
                "corp_name": "삼성전자",
                "note": "preferred-stock ticker; corp registry only maps common stock",
            }
        }

    @pytest.mark.asyncio
    async def test_genuinely_unresolvable_code_has_no_hint(self):
        # 999995 doesn't resolve, and its zeroed-last-digit candidate
        # (999990) doesn't either — must fall back to plain None, not a
        # fabricated hint.
        assert await resolve_stock_code("999995") is None
        assert await corp_code_mod.lookup_by_stock_code("999990") is None

    @pytest.mark.asyncio
    async def test_normal_resolved_code_unchanged(self):
        result = await resolve_stock_code("005930")
        assert isinstance(result, CorpEntry)
        assert result.corp_name == "삼성전자"
        assert result.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_code_already_ending_in_zero_gets_no_hint_attempt(self):
        # Ends in '0' already — not preferred-stock-shaped, so no hint
        # branch should even fire; a genuinely unresolved '0'-ending code
        # just returns None.
        assert await resolve_stock_code("999990") is None

    @pytest.mark.asyncio
    async def test_non_numeric_code_has_no_hint(self):
        assert await resolve_stock_code("ABCDEF") is None


class TestFillHoldingPct:
    """2026-07-12 — paid-tier majorstock enrichment
    (`monitor_activist_investors` / `monitor_foreign_holders`). Tested
    against `koreanpulse._enrich.fill_holding_pct` directly, monkeypatching
    the module's `list_major_holdings` reference — same isolation pattern
    as `_FakeTranslator` above."""

    @pytest.mark.asyncio
    async def test_exact_match_fills_all_3_fields(self, monkeypatch):
        async def fake_list_major_holdings(corp_code, *, client=None):
            assert corp_code == "00126380"
            return [MajorHolding(repror="얼라인파트너스자산운용", stkrt=5.2, stkrt_irds=0.3)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f = _filing(code="00126380", name_ko="삼성전자")
        f.filer_name_ko = "얼라인파트너스자산운용"
        await fill_holding_pct([f], op="test")
        assert f.holding_pct == 5.2
        assert f.holding_pct_change == 0.3
        assert f.holder_reporter_ko == "얼라인파트너스자산운용"

    @pytest.mark.asyncio
    async def test_contains_fallback_match(self, monkeypatch):
        """No exact string match, but the majorstock `repror` is a
        substring of the filer name (or vice versa) — falls back."""

        async def fake_list_major_holdings(corp_code, *, client=None):
            return [MajorHolding(repror="KCGI", stkrt=7.0, stkrt_irds=-0.2)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f = _filing(code="00126380", name_ko="삼성전자")
        f.filer_name_ko = "KCGI 제일호 사모투자합자회사"
        await fill_holding_pct([f], op="test")
        assert f.holding_pct == 7.0
        assert f.holder_reporter_ko == "KCGI"

    @pytest.mark.asyncio
    async def test_no_match_leaves_fields_none(self, monkeypatch):
        async def fake_list_major_holdings(corp_code, *, client=None):
            return [MajorHolding(repror="전혀다른펀드", stkrt=1.0, stkrt_irds=0.0)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f = _filing(code="00126380", name_ko="삼성전자")
        f.filer_name_ko = "얼라인파트너스자산운용"
        await fill_holding_pct([f], op="test")
        assert f.holding_pct is None
        assert f.holding_pct_change is None
        assert f.holder_reporter_ko is None

    @pytest.mark.asyncio
    async def test_empty_majorstock_result_leaves_fields_none(self, monkeypatch):
        async def fake_list_major_holdings(corp_code, *, client=None):
            return []

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f = _filing(code="00126380", name_ko="삼성전자")
        f.filer_name_ko = "얼라인파트너스자산운용"
        await fill_holding_pct([f], op="test")
        assert f.holding_pct is None

    @pytest.mark.asyncio
    async def test_raise_in_one_corp_lookup_is_isolated_others_still_enrich(
        self, monkeypatch
    ):
        """A DART/network failure for one corp_code must not block
        enrichment of other corp_codes in the same batch — non-throwing."""

        async def fake_list_major_holdings(corp_code, *, client=None):
            if corp_code == "00000001":
                raise RuntimeError("simulated DART 503")
            return [MajorHolding(repror="굿펀드", stkrt=9.9, stkrt_irds=1.1)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        bad = _filing(code="00000001", name_ko="배드컴퍼니")
        bad.filer_name_ko = "굿펀드"
        good = _filing(code="00000002", name_ko="굿컴퍼니")
        good.filer_name_ko = "굿펀드"

        # Must not raise despite the bad corp_code's lookup failing.
        await fill_holding_pct([bad, good], op="test")

        assert bad.holding_pct is None
        assert good.holding_pct == 9.9

    @pytest.mark.asyncio
    async def test_dedups_by_corp_code_one_call_per_unique_corp(self, monkeypatch):
        calls: list[str] = []

        async def fake_list_major_holdings(corp_code, *, client=None):
            calls.append(corp_code)
            return [MajorHolding(repror="펀드", stkrt=3.0, stkrt_irds=0.0)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f1 = _filing(code="00126380", name_ko="삼성전자", title="공시1")
        f1.filer_name_ko = "펀드"
        f2 = _filing(code="00126380", name_ko="삼성전자", title="공시2")
        f2.filer_name_ko = "펀드"
        await fill_holding_pct([f1, f2], op="test")

        assert calls == ["00126380"]  # exactly once despite 2 rows
        assert f1.holding_pct == 3.0
        assert f2.holding_pct == 3.0

    @pytest.mark.asyncio
    async def test_caps_at_8_distinct_corp_codes(self, monkeypatch):
        calls: list[str] = []

        async def fake_list_major_holdings(corp_code, *, client=None):
            calls.append(corp_code)
            return []

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        filings = []
        for i in range(12):  # 12 distinct corp_codes, cap is 8
            f = _filing(code=f"{i:08d}", name_ko=f"회사{i}")
            f.filer_name_ko = "펀드"
            filings.append(f)
        await fill_holding_pct(filings, op="test")

        assert len(calls) == 8
        assert calls == [f"{i:08d}" for i in range(8)]

    @pytest.mark.asyncio
    async def test_empty_filer_name_no_match_attempted(self, monkeypatch):
        called = {"n": 0}

        async def fake_list_major_holdings(corp_code, *, client=None):
            called["n"] += 1
            return [MajorHolding(repror="펀드", stkrt=1.0, stkrt_irds=0.0)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        f = _filing(code="00126380", name_ko="삼성전자")
        f.filer_name_ko = None
        await fill_holding_pct([f], op="test")
        assert f.holding_pct is None  # no filer name → can't match, stays None
        assert called["n"] == 1  # corp_code lookup itself still happens

    @pytest.mark.asyncio
    async def test_works_on_foreign_holder_filings(self, monkeypatch):
        """ForeignHolderFiling extends Filing — same helper must work on
        its rows without special-casing, matching `fill_corp_name_en`'s
        existing coverage of both row types."""

        async def fake_list_major_holdings(corp_code, *, client=None):
            return [MajorHolding(repror="블랙록", stkrt=6.6, stkrt_irds=0.05)]

        monkeypatch.setattr(enrich_mod, "list_major_holdings", fake_list_major_holdings)
        fhf = ForeignHolderFiling(
            corp_code="00126380",
            corp_name_ko="삼성전자",
            stock_code="005930",
            filing_type="D",
            filing_type_label_ko="지분공시",
            filing_type_label_en="Shareholding",
            title="주식등의대량보유상황보고서",
            receipt_no="rcpt_x",
            filed_at=datetime(2026, 5, 5, 9, 0, 0),
            dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=rcpt_x",
            attribution="DART",
            holder_label="BlackRock",
            holder_origin="us",
            filer_name_ko="블랙록",
        )
        await fill_holding_pct([fhf], op="test")
        assert fhf.holding_pct == 6.6
        assert fhf.holder_reporter_ko == "블랙록"


def _article(*, industries: Optional[list[str]] = None) -> Article:
    return Article(
        title_ko="삼성전자 HBM 공급 확대",
        title_en="",
        source_key="etnews",
        source_name="전자신문",
        url="https://www.etnews.com/article/1",
        published_at=datetime(2026, 7, 8, 10, 0, 0),
        summary_en="",
        industries=industries or ["semiconductor"],
        attribution="Source: 전자신문 (etnews.com)",
    )


class TestSearchKoreanIndustryNewsUnsupportedIndustries:
    """2026-07-12 — additive `unsupported_industries` surface. An
    unrecognized `industries` tag must never raise — it's dropped from the
    filter (existing `fetch_industry_news` set-intersection behavior,
    unchanged) and reported back so the caller can retry with a supported
    tag, without breaking the bare-list response shape for the common case."""

    @pytest.fixture(autouse=True)
    def _no_license_gate(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_REQUIRE_LICENSE", raising=False)

    @pytest.mark.asyncio
    async def test_all_valid_industries_returns_bare_list(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None):
            return [_article()]

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(
            industries=["semiconductor", "battery"], translate=False
        )
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_industries_arg_returns_bare_list(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None):
            return [_article()]

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(translate=False)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_one_unsupported_industry_surfaces_dict_not_raise(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None):
            return [_article()]

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(
            industries=["semiconductor", "cryptocurrency"], translate=False
        )
        assert isinstance(result, dict)
        assert result["unsupported_industries"] == ["cryptocurrency"]
        assert "semiconductor" in result["supported_industries"]
        assert len(result["articles"]) == 1

    @pytest.mark.asyncio
    async def test_all_unsupported_industries_returns_empty_articles_not_error(
        self, monkeypatch
    ):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None):
            # Real fetch_industry_news set-intersection semantics: an
            # all-unsupported filter never matches any article's tags.
            return []

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(
            industries=["not_a_real_industry"], translate=False
        )
        assert isinstance(result, dict)
        assert result["unsupported_industries"] == ["not_a_real_industry"]
        assert result["articles"] == []

    @pytest.mark.asyncio
    async def test_supported_industries_list_matches_16_sectors(self, monkeypatch):
        async def fake_fetch(*, industries=None, source_keys=None, limit=30, client=None):
            return []

        monkeypatch.setattr(server_mod, "fetch_industry_news", fake_fetch)
        result = await search_korean_industry_news(
            industries=["bogus"], translate=False
        )
        assert len(result["supported_industries"]) == 16
        assert "semiconductor" in result["supported_industries"]
        assert "energy" in result["supported_industries"]
