"""Enrichment-helper unit tests.

`fill_corp_name_en` lives in `koreanpulse._enrich` rather than
`koreanpulse.server` so it can be tested without the FastMCP runtime
(which `server.py` imports at module load). The MCP tool entry points
themselves are integration-tested via `examples/quickstart.py`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
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
from koreanpulse.server import (
    resolve_stock_code,
    search_korean_industry_news,
    track_korean_filings,
)
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


def _batch_filing(
    *,
    code: str,
    filed_at: datetime,
    red_flags: Optional[list[str]] = None,
    title: str = "사업보고서",
) -> Filing:
    return Filing(
        corp_code=code,
        corp_name_ko=f"회사{code}",
        stock_code=None,
        filing_type="A",
        filing_type_label_ko="정기공시",
        filing_type_label_en="Periodic",
        title=title,
        red_flags=red_flags or [],
        receipt_no=f"rcpt_{code}_{filed_at:%Y%m%d}",
        filed_at=filed_at,
        dart_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=rcpt",
        attribution="DART",
    )


class TestTrackKoreanFilingsBatchScan:
    """2026-07-14 — experimental agent-oriented batch-scan capability on
    the existing `track_korean_filings` tool (3 new optional args:
    `company_corp_codes`, `since`, `material_only`). All default such that
    a legacy single-company/days/no-args call is byte-for-byte unchanged."""

    @pytest.fixture(autouse=True)
    def _no_license_gate(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_REQUIRE_LICENSE", raising=False)

    def _fake_source(self, monkeypatch, by_code: dict[str, list[Filing]]):
        """Install a fake `list_filings_cached` that returns per-corp_code
        fixtures and records the kwargs of every call it received."""
        calls: list[dict] = []

        async def fake_list_filings_cached(*, cache, corp_code, bgn_de, end_de, pblntf_ty, page_count):
            calls.append(
                {
                    "corp_code": corp_code,
                    "bgn_de": bgn_de,
                    "end_de": end_de,
                    "pblntf_ty": pblntf_ty,
                    "page_count": page_count,
                }
            )
            return list(by_code.get(corp_code, []))

        monkeypatch.setattr(server_mod, "list_filings_cached", fake_list_filings_cached)
        return calls

    @pytest.mark.asyncio
    async def test_batch_returns_merged_and_sorted_newest_first(self, monkeypatch):
        by_code = {
            "00000001": [_batch_filing(code="00000001", filed_at=datetime(2026, 5, 3))],
            "00000002": [_batch_filing(code="00000002", filed_at=datetime(2026, 5, 5))],
            "00000003": [_batch_filing(code="00000003", filed_at=datetime(2026, 5, 4))],
        }
        calls = self._fake_source(monkeypatch, by_code)

        result = await track_korean_filings(
            company_corp_codes=["00000001", "00000002", "00000003"],
            translate=False,
        )

        # One fan-out call per corp_code.
        assert sorted(c["corp_code"] for c in calls) == [
            "00000001",
            "00000002",
            "00000003",
        ]
        # Merged + sorted newest-first across companies.
        assert [f.corp_code for f in result] == ["00000002", "00000003", "00000001"]

    @pytest.mark.asyncio
    async def test_limit_is_per_company_so_a_heavy_filer_cannot_crowd_out_a_quiet_one(
        self, monkeypatch
    ):
        """Regression — 2026-07-14 live smoke test.

        A merged-then-truncated `limit` silently dropped NAVER entirely from a
        [Samsung, SK hynix, NAVER] batch: the two heavy filers filled the whole
        limit and the quiet company vanished, indistinguishable from "filed
        nothing". That is a false all-clear — the worst output a portfolio
        monitor can produce. `limit` must apply PER COMPANY.
        """
        # Heavy filer: 5 recent filings. Quiet filer: 1 older filing.
        heavy = [
            _batch_filing(code="00000001", filed_at=datetime(2026, 5, 10 + i))
            for i in range(5)
        ]
        quiet = [_batch_filing(code="00000002", filed_at=datetime(2026, 5, 1))]
        self._fake_source(monkeypatch, {"00000001": heavy, "00000002": quiet})

        result = await track_korean_filings(
            company_corp_codes=["00000001", "00000002"],
            limit=3,
            translate=False,
        )

        returned = {f.corp_code for f in result}
        # The quiet company MUST survive — its filing is older than every one
        # of the heavy filer's, so a merged truncation would have dropped it.
        assert "00000002" in returned, "quiet company was crowded out of the batch"
        # limit is per-company: 3 from the heavy filer + the quiet one's 1.
        assert sum(1 for f in result if f.corp_code == "00000001") == 3
        assert sum(1 for f in result if f.corp_code == "00000002") == 1
        # Still globally sorted newest-first across the merged set.
        assert [f.filed_at for f in result] == sorted(
            [f.filed_at for f in result], reverse=True
        )

    @pytest.mark.asyncio
    async def test_legacy_single_company_limit_still_truncates_the_result_set(
        self, monkeypatch
    ):
        """The per-company limit change must not alter the legacy path: a
        single-company call still returns at most `limit` rows."""
        rows = [
            _batch_filing(code="00000001", filed_at=datetime(2026, 5, 10 + i))
            for i in range(5)
        ]
        self._fake_source(monkeypatch, {"00000001": rows})

        result = await track_korean_filings(
            company_corp_code="00000001", limit=3, translate=False
        )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_plural_list_takes_precedence_over_singular(self, monkeypatch):
        by_code = {
            "00000009": [_batch_filing(code="00000009", filed_at=datetime(2026, 5, 5))],
        }
        calls = self._fake_source(monkeypatch, by_code)

        result = await track_korean_filings(
            company_corp_code="00000001",  # singular — must be ignored
            company_corp_codes=["00000009"],
            translate=False,
        )
        assert [c["corp_code"] for c in calls] == ["00000009"]
        assert [f.corp_code for f in result] == ["00000009"]

    @pytest.mark.asyncio
    async def test_more_than_10_corp_codes_raises_validation_error(self, monkeypatch):
        self._fake_source(monkeypatch, {})
        with pytest.raises(ValueError, match="at most 10"):
            await track_korean_filings(
                company_corp_codes=[f"{i:08d}" for i in range(11)],
                translate=False,
            )

    @pytest.mark.asyncio
    async def test_exactly_10_corp_codes_is_allowed(self, monkeypatch):
        codes = [f"{i:08d}" for i in range(10)]
        self._fake_source(monkeypatch, {c: [] for c in codes})
        # Must not raise at the boundary.
        result = await track_korean_filings(company_corp_codes=codes, translate=False)
        assert result == []

    @pytest.mark.asyncio
    async def test_since_filters_and_overrides_days_window(self, monkeypatch):
        by_code = {
            None: [
                _batch_filing(code="00000001", filed_at=datetime(2026, 5, 3)),
                _batch_filing(code="00000002", filed_at=datetime(2026, 5, 5)),
            ]
        }
        calls = self._fake_source(monkeypatch, by_code)

        result = await track_korean_filings(
            days=7,
            since="2026-05-04",
            translate=False,
        )
        # `since` becomes the DART window start, not today-7.
        assert calls[0]["bgn_de"] == date(2026, 5, 4)
        # Only filings at/after the cutoff survive.
        assert [f.filed_at for f in result] == [datetime(2026, 5, 5)]

    @pytest.mark.asyncio
    async def test_since_accepts_datetime_with_timezone(self, monkeypatch):
        by_code = {
            None: [_batch_filing(code="00000001", filed_at=datetime(2026, 5, 5))]
        }
        self._fake_source(monkeypatch, by_code)
        # Z-suffixed UTC datetime must parse (normalized to KST wall-clock).
        result = await track_korean_filings(
            since="2026-05-01T00:00:00Z", translate=False
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_malformed_since_raises_validation_error(self, monkeypatch):
        self._fake_source(monkeypatch, {})
        with pytest.raises(ValueError, match="ISO-8601"):
            await track_korean_filings(since="not-a-date", translate=False)

    @pytest.mark.asyncio
    async def test_material_only_filters_to_nonempty_red_flags(self, monkeypatch):
        by_code = {
            None: [
                _batch_filing(code="00000001", filed_at=datetime(2026, 5, 5), red_flags=[]),
                _batch_filing(
                    code="00000002",
                    filed_at=datetime(2026, 5, 4),
                    red_flags=["cb_issuance"],
                ),
            ]
        }
        self._fake_source(monkeypatch, by_code)

        result = await track_korean_filings(material_only=True, translate=False)
        assert [f.corp_code for f in result] == ["00000002"]
        assert all(f.red_flags for f in result)

    @pytest.mark.asyncio
    async def test_material_only_across_batch(self, monkeypatch):
        by_code = {
            "00000001": [
                _batch_filing(code="00000001", filed_at=datetime(2026, 5, 5), red_flags=[]),
            ],
            "00000002": [
                _batch_filing(
                    code="00000002",
                    filed_at=datetime(2026, 5, 4),
                    red_flags=["rights_issue"],
                ),
            ],
        }
        self._fake_source(monkeypatch, by_code)
        result = await track_korean_filings(
            company_corp_codes=["00000001", "00000002"],
            material_only=True,
            translate=False,
        )
        assert [f.corp_code for f in result] == ["00000002"]

    @pytest.mark.asyncio
    async def test_legacy_single_company_path_unchanged(self, monkeypatch):
        """No new args → single call with the days window, no sort/filter,
        DART's native order preserved, truncated to `limit`."""
        native_order = [
            _batch_filing(code="00000001", filed_at=datetime(2026, 5, 3)),
            _batch_filing(code="00000001", filed_at=datetime(2026, 5, 5)),
        ]
        calls = self._fake_source(monkeypatch, {"00000001": native_order})

        result = await track_korean_filings(
            company_corp_code="00000001", days=7, translate=False
        )
        # Exactly one call, using the days window (today-7 .. today).
        assert len(calls) == 1
        assert calls[0]["corp_code"] == "00000001"
        assert calls[0]["end_de"] == server_mod._kst_today()
        # Order untouched (no re-sort on the legacy path).
        assert [f.filed_at for f in result] == [
            datetime(2026, 5, 3),
            datetime(2026, 5, 5),
        ]

    @pytest.mark.asyncio
    async def test_legacy_no_args_path_unchanged(self, monkeypatch):
        calls = self._fake_source(
            monkeypatch,
            {None: [_batch_filing(code="00000001", filed_at=datetime(2026, 5, 5))]},
        )
        result = await track_korean_filings(translate=False)
        assert len(calls) == 1
        assert calls[0]["corp_code"] is None
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_instrumentation_fires_on_batch_path(self, monkeypatch, caplog):
        codes = ["00000001", "00000002"]
        self._fake_source(monkeypatch, {c: [] for c in codes})
        with caplog.at_level(logging.INFO, logger="koreanpulse.server"):
            await track_korean_filings(company_corp_codes=codes, translate=False)
        batch_logs = [r for r in caplog.records if r.getMessage().startswith("agent_batch_scan")]
        assert len(batch_logs) == 1
        msg = batch_logs[0].getMessage()
        assert "corp_code_count=2" in msg
        assert "cutoff=days" in msg
        assert "material_only=False" in msg
        assert "license_key_present=False" in msg

    @pytest.mark.asyncio
    async def test_instrumentation_fires_on_since_path(self, monkeypatch, caplog):
        self._fake_source(monkeypatch, {None: []})
        with caplog.at_level(logging.INFO, logger="koreanpulse.server"):
            await track_korean_filings(
                since="2026-05-01", material_only=True, license_key="k", translate=False
            )
        batch_logs = [r for r in caplog.records if r.getMessage().startswith("agent_batch_scan")]
        assert len(batch_logs) == 1
        msg = batch_logs[0].getMessage()
        assert "cutoff=since" in msg
        assert "material_only=True" in msg
        assert "license_key_present=True" in msg

    @pytest.mark.asyncio
    async def test_instrumentation_does_not_fire_on_legacy_path(self, monkeypatch, caplog):
        self._fake_source(
            monkeypatch,
            {"00000001": [_batch_filing(code="00000001", filed_at=datetime(2026, 5, 5))]},
        )
        with caplog.at_level(logging.INFO, logger="koreanpulse.server"):
            await track_korean_filings(company_corp_code="00000001", translate=False)
        batch_logs = [r for r in caplog.records if r.getMessage().startswith("agent_batch_scan")]
        assert batch_logs == []

    @pytest.mark.asyncio
    async def test_single_element_list_does_not_fire_instrumentation(self, monkeypatch, caplog):
        """A 1-element `company_corp_codes` (no `since`) uses the fan-out
        code path but is not the 'agent batch-scan' signal we measure."""
        self._fake_source(monkeypatch, {"00000001": []})
        with caplog.at_level(logging.INFO, logger="koreanpulse.server"):
            await track_korean_filings(company_corp_codes=["00000001"], translate=False)
        batch_logs = [r for r in caplog.records if r.getMessage().startswith("agent_batch_scan")]
        assert batch_logs == []


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
