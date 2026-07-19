"""Tests for the internal watchlist→alert foundation (feature-flagged P1 slice)."""
from __future__ import annotations

from datetime import date

import pytest

from koreanpulse.alerts import AlertResult, Channel
from koreanpulse.models import Filing
from koreanpulse.watchlist import (
    MAX_ALERTS_PER_COMPANY,
    Watchlist,
    classify_material,
    load_watchlists,
    poll_watchlist,
    run_polling,
    save_watchlists,
)

CHANNEL = "https://discord.com/api/webhooks/1/x"


def make_filing(
    receipt_no: str,
    *,
    corp_code: str = "00126380",
    title: str = "주요사항보고서",
    filing_type: str = "B",
    filer: str | None = None,
    red_flags: list[str] | None = None,
    filed_at: str = "2026-07-15",
    is_correction: bool = False,
) -> Filing:
    return Filing(
        corp_code=corp_code,
        corp_name_ko="삼성전자",
        stock_code="005930",
        filing_type=filing_type,
        filing_type_label_ko="주요사항보고",
        filing_type_label_en="Major events",
        title=title,
        red_flags=red_flags or [],
        receipt_no=receipt_no,
        filed_at=filed_at,
        dart_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}",
        filer_name_ko=filer,
        attribution="Source: DART",
        is_correction=is_correction,
    )


def make_watchlist(**kw) -> Watchlist:
    defaults = dict(id="w1", owner="partner@example.com", corp_codes=["00126380"], channel_url=CHANNEL)
    defaults.update(kw)
    return Watchlist(**defaults)


class Sender:
    def __init__(self, fail_receipts: set[str] | None = None):
        self.sent: list[tuple[str, str]] = []
        self.fail_receipts = fail_receipts or set()

    async def __call__(self, url: str, *, title: str, body: str) -> AlertResult:
        receipt = next((line.split(": ")[1] for line in body.splitlines() if line.startswith("DART receipt:")), "")
        if receipt in self.fail_receipts:
            return AlertResult(ok=False, channel=Channel.DISCORD, status_code=500, error="boom")
        self.sent.append((title, body))
        return AlertResult(ok=True, channel=Channel.DISCORD, status_code=204)


def fetcher(filings_by_corp: dict[str, list[Filing]], fail_corps: set[str] | None = None):
    async def fetch(*, corp_code: str, bgn_de, end_de):
        if fail_corps and corp_code in fail_corps:
            raise RuntimeError("DART 503")
        return filings_by_corp.get(corp_code, [])
    return fetch


MATERIAL = make_filing("r-flag-1", title="회생절차 개시신청", red_flags=["rehabilitation"])
ACTIVIST = make_filing(
    "r-act-1", filing_type="D", title="주식등의대량보유상황보고서(일반)",
    filer="얼라인파트너스자산운용",
)
BORING = make_filing("r-boring-1", title="정기주주총회 소집공고")


class TestClassifyMaterial:
    def test_red_flag_is_material(self):
        ev = classify_material(MATERIAL)
        assert ev is not None and ev.category == "red_flag:rehabilitation"

    def test_allowlist_activist_5pct_is_material(self):
        ev = classify_material(ACTIVIST)
        assert ev is not None and ev.category == "activist:Align Partners"
        assert "얼라인파트너스자산운용" in ev.why

    def test_plain_filing_is_not_material(self):
        assert classify_material(BORING) is None

    def test_unmatched_individual_5pct_is_not_material(self):
        f = make_filing("r-ind-1", filing_type="D", filer="김철수")
        assert classify_material(f) is None


@pytest.mark.asyncio
class TestPollWatchlist:
    async def test_first_poll_delivers_material_filings(self):
        wl = make_watchlist()
        sender = Sender()
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL, ACTIVIST, BORING]}), send=sender,
        )
        assert sorted(res.delivered) == ["r-act-1", "r-flag-1"]
        assert len(sender.sent) == 2
        assert res.checkpoint_advanced and wl.last_checked == "2026-07-17"
        body = sender.sent[0][1]
        assert "DART receipt:" in body and "Not investment advice" in body
        assert "dart.fss.or.kr" in body and "Why matched:" in body

    async def test_second_poll_with_no_new_data_delivers_nothing(self):
        wl = make_watchlist()
        sender = Sender()
        filings = {"00126380": [MATERIAL]}
        await poll_watchlist(wl, today=date(2026, 7, 17), fetch=fetcher(filings), send=sender)
        res2 = await poll_watchlist(wl, today=date(2026, 7, 17), fetch=fetcher(filings), send=sender)
        assert res2.delivered == [] and res2.skipped_duplicates == 1
        assert len(sender.sent) == 1

    async def test_one_new_filing_on_second_poll(self):
        wl = make_watchlist()
        sender = Sender()
        await poll_watchlist(wl, today=date(2026, 7, 16), fetch=fetcher({"00126380": [MATERIAL]}), send=sender)
        new = make_filing("r-new-1", title="유상증자 결정", red_flags=["rights_issue"], filed_at="2026-07-17")
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL, new]}), send=sender,
        )
        assert res.delivered == ["r-new-1"] and res.skipped_duplicates == 1

    async def test_translation_failure_still_delivers_korean(self):
        wl = make_watchlist()
        sender = Sender()

        async def bad_translate(text: str) -> str:
            raise RuntimeError("provider down")

        res = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL]}), send=sender, translate=bad_translate,
        )
        assert res.delivered == ["r-flag-1"]
        assert "회생절차" in sender.sent[0][1]
        assert "English:" not in sender.sent[0][1]

    async def test_delivery_failure_keeps_receipt_pending_and_checkpoint_frozen(self):
        wl = make_watchlist()
        failing = Sender(fail_receipts={"r-flag-1"})
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": [MATERIAL]}), send=failing,
        )
        assert res.failed == ["r-flag-1"] and res.delivered == []
        assert not res.checkpoint_advanced and wl.last_checked is None
        # next poll retries and succeeds exactly once
        ok = Sender()
        res2 = await poll_watchlist(
            wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": [MATERIAL]}), send=ok,
        )
        assert res2.delivered == ["r-flag-1"] and len(ok.sent) == 1

    async def test_partial_company_fetch_failure_is_surfaced_not_skipped(self):
        wl = make_watchlist(corp_codes=["00126380", "00999999"])
        sender = Sender()
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL]}, fail_corps={"00999999"}), send=sender,
        )
        assert res.delivered == ["r-flag-1"]
        assert "00999999" in res.errors and "DART 503" in res.errors["00999999"]
        assert not res.checkpoint_advanced  # window re-covered next poll

    async def test_duplicate_filing_never_delivered_twice(self):
        wl = make_watchlist()
        sender = Sender()
        for _ in range(3):
            await poll_watchlist(
                wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": [ACTIVIST]}), send=sender,
            )
        assert len(sender.sent) == 1

    async def test_correction_filing_is_a_distinct_receipt_and_delivers_once(self):
        wl = make_watchlist()
        sender = Sender()
        correction = make_filing(
            "r-flag-2", title="[기재정정] 회생절차 개시신청",
            red_flags=["rehabilitation"], is_correction=True, filed_at="2026-07-16",
        )
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL, correction]}), send=sender,
        )
        # DART corrections carry a new receipt number: delivered once each,
        # never re-delivered.
        assert sorted(res.delivered) == ["r-flag-1", "r-flag-2"]
        res2 = await poll_watchlist(
            wl, today=date(2026, 7, 17),
            fetch=fetcher({"00126380": [MATERIAL, correction]}), send=sender,
        )
        assert res2.delivered == [] and res2.skipped_duplicates == 2

    async def test_per_company_alert_cap(self):
        wl = make_watchlist()
        sender = Sender()
        flood = [
            make_filing(f"r-{i}", title="회생절차 개시신청", red_flags=["rehabilitation"])
            for i in range(MAX_ALERTS_PER_COMPANY + 3)
        ]
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": flood}), send=sender,
        )
        assert len(res.delivered) == MAX_ALERTS_PER_COMPANY
        # the overflow is not lost — next poll delivers the rest
        res2 = await poll_watchlist(
            wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": flood}), send=sender,
        )
        assert len(res2.delivered) == 3

    async def test_disabled_watchlist_is_not_polled(self):
        wl = make_watchlist(enabled=False)
        sender = Sender()
        res = await poll_watchlist(
            wl, today=date(2026, 7, 17), fetch=fetcher({"00126380": [MATERIAL]}), send=sender,
        )
        assert res.delivered == [] and sender.sent == []


class TestStoreAndFlag:
    def test_watchlist_caps_at_ten_corp_codes(self):
        with pytest.raises(ValueError):
            make_watchlist(corp_codes=[f"{i:08d}" for i in range(11)])

    def test_save_and_load_roundtrip(self, tmp_path):
        p = tmp_path / "wl.json"
        wl = make_watchlist()
        wl.delivered_receipts["00126380"] = ["r-1"]
        save_watchlists([wl], p)
        loaded = load_watchlists(p)
        assert len(loaded) == 1
        assert loaded[0].delivered_receipts == {"00126380": ["r-1"]}

    @pytest.mark.asyncio
    async def test_run_polling_requires_feature_flag(self, monkeypatch, tmp_path):
        monkeypatch.delenv("KOREANPULSE_WATCHLIST_ENABLED", raising=False)
        with pytest.raises(RuntimeError, match="disabled"):
            await run_polling(tmp_path / "wl.json")
