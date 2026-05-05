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

from koreanpulse._enrich import fill_corp_name_en
from koreanpulse.cache import FileCache
from koreanpulse.models import Filing, ForeignHolderFiling
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
