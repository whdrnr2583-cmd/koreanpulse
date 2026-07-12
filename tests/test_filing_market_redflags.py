"""Synthetic-fixture tests for the `market` and `red_flags` filing fields.

Non-source fixtures: hand-built DART-shaped rows, not captured API payloads,
so a passing suite means the mapping logic is exercised, not that we happened
to replay a live response.
"""
from __future__ import annotations

from koreanpulse.dart import (
    _parse_filing,
    market_from_corp_cls,
    tag_red_flags,
)


def _row(*, title: str = "분기보고서(2026.03)", corp_cls=None) -> dict:
    row = {
        "corp_code": "01234567",
        "corp_name": "테스트기업",
        "stock_code": "123456",
        "report_nm": title,
        "rcept_no": "20260701000001",
        "rcept_dt": "20260701",
    }
    if corp_cls is not None:
        row["corp_cls"] = corp_cls
    return row


class TestMarketFromCorpCls:
    def test_kospi(self):
        assert market_from_corp_cls("Y") == "KOSPI"

    def test_kosdaq(self):
        assert market_from_corp_cls("K") == "KOSDAQ"

    def test_konex(self):
        assert market_from_corp_cls("N") == "KONEX"

    def test_other(self):
        assert market_from_corp_cls("E") == "OTHER"

    def test_absent_is_none(self):
        assert market_from_corp_cls(None) is None

    def test_empty_string_is_none(self):
        assert market_from_corp_cls("") is None

    def test_unknown_code_is_none(self):
        assert market_from_corp_cls("Z") is None

    def test_lowercase_and_whitespace_normalized(self):
        assert market_from_corp_cls(" y ") == "KOSPI"


class TestMarketOnParsedFiling:
    def test_kospi_surfaced(self):
        assert _parse_filing(_row(corp_cls="Y")).market == "KOSPI"

    def test_kosdaq_surfaced(self):
        assert _parse_filing(_row(corp_cls="K")).market == "KOSDAQ"

    def test_konex_surfaced(self):
        assert _parse_filing(_row(corp_cls="N")).market == "KONEX"

    def test_other_surfaced(self):
        assert _parse_filing(_row(corp_cls="E")).market == "OTHER"

    def test_missing_corp_cls_is_none(self):
        assert _parse_filing(_row()).market is None


class TestTagRedFlags:
    def test_cb_issuance(self):
        assert tag_red_flags("전환사채권발행결정") == ["cb_issuance"]

    def test_controlling_shareholder_change(self):
        assert tag_red_flags("최대주주변경") == ["controlling_shareholder_change"]

    def test_rehabilitation(self):
        assert tag_red_flags("회생절차개시신청") == ["rehabilitation"]

    def test_clean_audit_opinion_not_flagged(self):
        # A clean ('적정') opinion is healthy — must NOT be tagged as a red
        # flag (previously the bare '감사의견' keyword falsely fired here).
        assert tag_red_flags("감사보고서(감사의견 적정)") == []

    def test_audit_opinion_from_uigyeongeojeol(self):
        assert tag_red_flags("감사의견 의견거절") == ["audit_opinion"]

    def test_audit_opinion_disclaimer(self):
        assert tag_red_flags("감사의견거절") == ["audit_opinion"]

    def test_audit_opinion_qualified(self):
        assert tag_red_flags("감사보고서(감사의견 한정)") == ["audit_opinion"]

    def test_audit_opinion_adverse(self):
        assert tag_red_flags("감사보고서(감사의견 부적정)") == ["audit_opinion"]

    def test_disclosure_violation(self):
        assert tag_red_flags("불성실공시법인지정") == ["disclosure_violation"]

    def test_rights_issue(self):
        assert tag_red_flags("유상증자결정") == ["rights_issue"]

    def test_capital_reduction(self):
        assert tag_red_flags("감자결정") == ["capital_reduction"]

    def test_no_match_returns_empty(self):
        assert tag_red_flags("분기보고서(2026.03)") == []

    def test_empty_title_returns_empty(self):
        assert tag_red_flags("") == []

    def test_composite_multiple_tags_in_order(self):
        # Both a rights issue and a capital reduction referenced in one title.
        title = "주요사항보고서(유상증자 및 감자 결정)"
        assert tag_red_flags(title) == ["rights_issue", "capital_reduction"]

    def test_amended_prefix_still_tags(self):
        assert tag_red_flags("[기재정정]전환사채권발행결정") == ["cb_issuance"]


class TestTagRedFlagsExpanded2026_07_12:
    """Red-flag keyword expansion (task A2) — 7 new keyword/tag pairs added
    after the original 9. `test_clean_audit_opinion_not_flagged` above must
    keep passing unchanged — none of these new keywords touch '적정'."""

    def test_management_designation(self):
        assert tag_red_flags("관리종목지정") == ["management_designation"]

    def test_delisting_risk(self):
        assert tag_red_flags("상장폐지결정") == ["delisting_risk"]

    def test_trading_halt(self):
        assert tag_red_flags("거래정지안내") == ["trading_halt"]

    def test_reverse_split(self):
        assert tag_red_flags("주식병합결정") == ["reverse_split"]

    def test_short_term_borrowing(self):
        assert tag_red_flags("단기차입금증가결정") == ["short_term_borrowing"]

    def test_going_concern_from_gyesok_gieop(self):
        assert tag_red_flags("계속기업 존속능력에 대한 불확실성") == ["going_concern"]

    def test_going_concern_from_jonsok_neungnyeok_alone(self):
        assert tag_red_flags("존속능력 불확실성 관련 안내") == ["going_concern"]

    def test_clean_audit_opinion_still_not_flagged(self):
        # Regression guard for the task's explicit "가드 유지" requirement.
        assert tag_red_flags("감사보고서(감사의견 적정)") == []


class TestRedFlagsOnParsedFiling:
    def test_red_flags_surfaced(self):
        f = _parse_filing(_row(title="전환사채권발행결정", corp_cls="K"))
        assert f.red_flags == ["cb_issuance"]
        assert f.market == "KOSDAQ"

    def test_clean_filing_has_empty_red_flags(self):
        assert _parse_filing(_row()).red_flags == []
